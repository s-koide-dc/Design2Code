import unittest
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from scripts.design.review_design_generation_snapshot import build_review_snapshot
from src.config.config_manager import ConfigManager
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.code_verification.execution_verifier import ExecutionVerifier
from src.design_parser.structured_parser import StructuredDesignParser

class TestRuntimeExecution(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cm = ConfigManager()
        self.cm.method_store_path = os.path.join(self.temp_dir.name, "method_store.json")
        self.cm.storage_dir = os.path.join(self.temp_dir.name, "vectors")
        with open(os.path.join("resources", "method_store.json"), "r", encoding="utf-8") as source:
            with open(self.cm.method_store_path, "w", encoding="utf-8") as target:
                target.write(source.read())
        self.synthesizer = CodeSynthesizer(self.cm)
        self.verifier = ExecutionVerifier(self.cm)
        self.original_store_path = self.cm.method_store_path

        # 1. テスト用のメソッドを注入 (CsvHelper利用)
        self._inject_test_methods()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _inject_test_methods(self):
        new_methods = [
            {
                "name": "ToCsv",
                "class": "Common.Serialization.CsvUtil",
                "namespace": "Common.Serialization",
                "return_type": "string",
                "params": [{"name": "records", "type": "IEnumerable<dynamic>"}],
                "code": "Common.Serialization.CsvUtil.ToCsv({records})",
                "usings": ["CsvHelper", "System.Globalization", "System.IO", "System.Collections.Generic"],
                "dependencies": ["CsvHelper"],
                "code_body": """
namespace Common.Serialization {
    public class CsvUtil {
        public static string ToCsv(IEnumerable<dynamic> records) {
            using var writer = new StringWriter();
            using var csv = new CsvWriter(writer, CultureInfo.InvariantCulture);
            csv.WriteRecords(records);
            return writer.ToString();
        }
    }
}""",
                "id": "csv_util_to_csv"
            },
            {
                "name": "CreateSampleData",
                "class": "Data.Factory",
                "namespace": "Data",
                "return_type": "IEnumerable<dynamic>",
                "params": [],
                "code": "Data.Factory.CreateSampleData()",
                "code_body": """namespace Data { public class Factory { public static System.Collections.Generic.IEnumerable<dynamic> CreateSampleData() { return new System.Collections.Generic.List<dynamic> { new { Name = \"Alice\", Age = 20 } }; } } }""",
                "id": "data_factory_create"
            }
        ]

        # 公開APIを通してメタデータと索引を一貫して更新する
        for method in new_methods:
            self.synthesizer.method_store.add_method(method)
        self.synthesizer = CodeSynthesizer(
            self.cm,
            method_store=self.synthesizer.method_store,
        )

    def _build_review_snapshot_for_runtime(self, design_path: str) -> dict:
        output_dir = Path(self.temp_dir.name) / "review_snapshots" / Path(design_path).stem
        args = SimpleNamespace(
            design=design_path,
            output_dir=str(output_dir),
            retry=False,
            allow_fallback=False,
            assist_endpoint_url=None,
            assist_model_id="local-assist",
            assist_timeout_seconds=60,
            assist_max_new_tokens=384,
            fail_on_maintainability=False,
            assist_policy="on_blocked_only",
        )
        snapshot = build_review_snapshot(args)
        self.assertEqual(0, snapshot["exit_code"], snapshot["payload"])
        payload = snapshot["payload"]
        self.assertTrue(payload["verification"]["valid"], payload)
        self.assertTrue(payload["quality"]["valid"], payload)
        return payload

    def test_app_mode_echo_generated_code_runtime_behavior(self):
        payload = self._build_review_snapshot_for_runtime(
            "scenarios/AppModeEchoMinimal.design.md",
        )
        test_code = """
using System;
using System.IO;
using System.Text.Json;
using Xunit;

public class AppModeEchoRuntimeTest
{
    [Fact]
    public void EchoesConfiguredAppMode()
    {
        var previous = Environment.GetEnvironmentVariable("APP_MODE");
        var writer = new StringWriter();
        var originalOut = Console.Out;
        try
        {
            Environment.SetEnvironmentVariable("APP_MODE", "runtime-test");
            Console.SetOut(writer);

            var result = new GeneratedProcessor().AppModeEchoMinimal();

            Assert.True(result);
            Assert.Contains("runtime-test", writer.ToString());
        }
        finally
        {
            Console.SetOut(originalOut);
            Environment.SetEnvironmentVariable("APP_MODE", previous);
        }
    }
}
"""
        runtime_result = self.verifier.verify_runtime(
            payload["generated_code"],
            test_code,
            dependencies=[],
        )
        self.assertTrue(runtime_result["success"], runtime_result)
        self.assertEqual(1, runtime_result["summary"]["passed"])

    def test_csv_sales_aggregation_generated_code_runtime_behavior(self):
        payload = self._build_review_snapshot_for_runtime(
            "scenarios/CsvSalesAggregation.design.md",
        )
        test_code = """
using System;
using System.IO;
using System.Text.Json;
using Xunit;

public class CsvSalesAggregationRuntimeTest
{
    [Fact]
    public void AggregatesSalesByProductAndWritesOutput()
    {
        var root = Path.Combine(Path.GetTempPath(), "csv-sales-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var inputPath = Path.Combine(root, "sales.csv");
            var outputPath = Path.Combine(root, "totals.csv");
            File.WriteAllText(inputPath, "A,10" + Environment.NewLine + "B,5" + Environment.NewLine + "A,20");

            var result = new GeneratedProcessor().CsvSalesAggregation(inputPath, outputPath);

            Assert.Equal(outputPath, result);
            var output = File.ReadAllText(outputPath);
            Assert.Contains("A,30", output);
            Assert.Contains("B,5", output);
        }
        finally
        {
            if (Directory.Exists(root))
                Directory.Delete(root, recursive: true);
        }
    }
}
"""
        runtime_result = self.verifier.verify_runtime(
            payload["generated_code"],
            test_code,
            dependencies=[],
        )
        self.assertTrue(runtime_result["success"], runtime_result)
        self.assertEqual(1, runtime_result["summary"]["passed"])

    def test_complex_linq_search_generated_code_runtime_behavior(self):
        payload = self._build_review_snapshot_for_runtime(
            "scenarios/ComplexLinqSearch.design.md",
        )
        test_code = """
using System;
using System.IO;
using System.Text.Json;
using Xunit;

public class ComplexLinqSearchRuntimeTest
{
    [Fact]
    public void FiltersUsersByNamePrefixAndPriceBeforeDisplay()
    {
        var previous = Directory.GetCurrentDirectory();
        var root = Path.Combine(Path.GetTempPath(), "complex-linq-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var writer = new StringWriter();
        var originalOut = Console.Out;
        try
        {
            Directory.SetCurrentDirectory(root);
            var users = new[]
            {
                new { Id = 1, Name = "Alice", Age = 30, Email = "a@example.test", Points = 10, Price = 600m, LastLoginAt = DateTime.Parse("2026-01-01T00:00:00") },
                new { Id = 2, Name = "Bob", Age = 25, Email = "b@example.test", Points = 20, Price = 900m, LastLoginAt = DateTime.Parse("2026-01-02T00:00:00") },
                new { Id = 3, Name = "Anne", Age = 28, Email = "c@example.test", Points = 30, Price = 400m, LastLoginAt = DateTime.Parse("2026-01-03T00:00:00") },
            };
            File.WriteAllText("users.json", JsonSerializer.Serialize(users));
            Console.SetOut(writer);

            var result = new GeneratedProcessor().ComplexLinqSearch();

            Assert.True(result);
            var output = writer.ToString();
            Assert.Contains("Alice", output);
            Assert.DoesNotContain("Bob", output);
            Assert.DoesNotContain("Anne", output);
        }
        finally
        {
            Console.SetOut(originalOut);
            Directory.SetCurrentDirectory(previous);
            if (Directory.Exists(root))
                Directory.Delete(root, recursive: true);
        }
    }
}
"""
        runtime_result = self.verifier.verify_runtime(
            payload["generated_code"],
            test_code,
            dependencies=[],
        )
        self.assertTrue(runtime_result["success"], runtime_result)
        self.assertEqual(1, runtime_result["summary"]["passed"])

    def test_product_api_filtered_catalog_generated_code_runtime_behavior(self):
        payload = self._build_review_snapshot_for_runtime(
            "scenarios/ProductApiFilteredCatalog.design.md",
        )
        test_code = """
using System;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Xunit;

public sealed class ProductCatalogHandler : HttpMessageHandler
{
    public Uri? RequestUri { get; private set; }
    public HttpMethod? Method { get; private set; }
    public HttpStatusCode StatusCode { get; set; } = HttpStatusCode.OK;
    public string? RawBody { get; set; }

    protected override Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        RequestUri = request.RequestUri;
        Method = request.Method;
        var products = new[]
        {
            new { Id = 1, Name = "Alpha", Price = 100, Quantity = 3, Stock = 3, Category = "Hardware", DiscountPrice = 90m },
            new { Id = 2, Name = "Beta", Price = 200, Quantity = 4, Stock = 4, Category = "Hardware", DiscountPrice = 180m },
            new { Id = 3, Name = "Atlas", Price = 150, Quantity = 0, Stock = 0, Category = "Hardware", DiscountPrice = 140m },
        };
        var response = new HttpResponseMessage(StatusCode)
        {
            Content = new StringContent(RawBody ?? JsonSerializer.Serialize(products))
        };
        return Task.FromResult(response);
    }
}

public class ProductApiFilteredCatalogRuntimeTest
{
    [Fact]
    public async Task FetchesProductsAndDisplaysOnlyMatchingRows()
    {
        var handler = new ProductCatalogHandler();
        using var client = new HttpClient(handler);
        var processor = new GeneratedProcessor(client);
        var writer = new StringWriter();
        var originalOut = Console.Out;
        try
        {
            Console.SetOut(writer);

            var result = await processor.ProductApiFilteredCatalog();

            Assert.True(result);
            Assert.Equal(HttpMethod.Get, handler.Method);
            Assert.Equal("https://api.example.com/products", handler.RequestUri?.ToString());
            var output = writer.ToString();
            Assert.Contains("Alpha", output);
            Assert.DoesNotContain("Beta", output);
            Assert.DoesNotContain("Atlas", output);
        }
        finally
        {
            Console.SetOut(originalOut);
        }
    }

    [Fact]
    public async Task ReturnsFalseWhenHttpRequestFails()
    {
        var handler = new ProductCatalogHandler
        {
            StatusCode = HttpStatusCode.InternalServerError
        };
        using var client = new HttpClient(handler);
        var processor = new GeneratedProcessor(client);

        var result = await processor.ProductApiFilteredCatalog();

        Assert.False(result);
        Assert.Equal(HttpMethod.Get, handler.Method);
    }

    [Fact]
    public async Task ReturnsFalseWhenJsonCannotBeParsed()
    {
        var handler = new ProductCatalogHandler
        {
            RawBody = "{not valid json"
        };
        using var client = new HttpClient(handler);
        var processor = new GeneratedProcessor(client);

        var result = await processor.ProductApiFilteredCatalog();

        Assert.False(result);
        Assert.Equal(HttpMethod.Get, handler.Method);
    }
}
"""
        runtime_result = self.verifier.verify_runtime(
            payload["generated_code"],
            test_code,
            dependencies=[],
        )
        self.assertTrue(runtime_result["success"], runtime_result)
        self.assertEqual(3, runtime_result["summary"]["passed"])

    def test_customer_api_with_entity_spec_generated_code_runtime_behavior(self):
        payload = self._build_review_snapshot_for_runtime(
            "scenarios/CustomerApiWithEntitySpec.design.md",
        )
        test_code = """
using System;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Xunit;

public sealed class CustomerCatalogHandler : HttpMessageHandler
{
    public Uri? RequestUri { get; private set; }
    public HttpMethod? Method { get; private set; }

    protected override Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        RequestUri = request.RequestUri;
        Method = request.Method;
        var customers = new[]
        {
            new { Id = 1, Name = "Alice", Email = "alice@example.test", Points = 150 },
            new { Id = 2, Name = "Bob", Email = "bob@example.test", Points = 300 },
            new { Id = 3, Name = "Anne", Email = "anne@example.test", Points = 80 },
        };
        var response = new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent(JsonSerializer.Serialize(customers))
        };
        return Task.FromResult(response);
    }
}

public class CustomerApiWithEntitySpecRuntimeTest
{
    [Fact]
    public async Task UsesInlineEntitySpecForPocoAndFiltersResponse()
    {
        var handler = new CustomerCatalogHandler();
        using var client = new HttpClient(handler);
        var processor = new GeneratedProcessor(client);
        var writer = new StringWriter();
        var originalOut = Console.Out;
        try
        {
            Console.SetOut(writer);

            var result = await processor.CustomerApiWithEntitySpec();

            Assert.True(result);
            Assert.Equal(HttpMethod.Get, handler.Method);
            Assert.Equal("https://customer.example.com/api/customers", handler.RequestUri?.ToString());
            var output = writer.ToString();
            Assert.Contains("Alice", output);
            Assert.DoesNotContain("Bob", output);
            Assert.DoesNotContain("Anne", output);
        }
        finally
        {
            Console.SetOut(originalOut);
        }
    }
}
"""
        runtime_result = self.verifier.verify_runtime(
            payload["generated_code"],
            test_code,
            dependencies=[],
        )
        self.assertTrue(runtime_result["success"], runtime_result)
        self.assertEqual(1, runtime_result["summary"]["passed"])

    def test_synthesize_and_run_test(self):
        print("\n--- Test: Runtime Execution Verification ---")

        steps = ["CreateSampleData", "ToCsv"]
        result = self.synthesizer.synthesize("ExportUserCsv", steps)

        source_code = result["code"]
        print("Synthesized Code Length:", len(source_code))

        # 2. テストコードの作成 (xUnit)
        test_code = """
using Xunit;
using System.Threading.Tasks;

public class RuntimeTest
{
    [Fact]
    public void ExportUserCsv_ShouldContainAlice()
    {
        // Arrange
        var processor = new GeneratedProcessor();

        # Act
        var result = processor.ExportUserCsv();

        # Assert
        Assert.NotNull(result);
        Assert.Contains("Alice", result);
        Assert.Contains("20", result);
        System.Console.WriteLine("CSV Result: " + result);
    }
}
"""
        # Pythonのf-stringやトリプルクォート内の # はコメント扱いになるので注意
        # ここではプレーンな文字列として扱う
        test_code = test_code.replace("# Act", "// Act").replace("# Assert", "// Assert")

        # 3. 実行検証
        deps = [{"name": d} for d in result["dependencies"]]
        runtime_result = self.verifier.verify_runtime(source_code, test_code, dependencies=deps)

        print("Test Summary:", runtime_result.get("summary"))
        if not runtime_result["success"]:
            print("Test Failed!")
            print("Stdout:", runtime_result.get("stdout"))
            print("Stderr:", runtime_result.get("stderr"))
            for fail in runtime_result.get("failures", []):
                print(f"  - {fail['test_name']}: {fail['message']}")

        self.assertTrue(runtime_result["success"], "Runtime execution failed.")
        self.assertEqual(runtime_result["summary"]["passed"], 1)

    def test_side_effect_execution_requires_external_sandbox(self):

        # 危険な操作を含むコード
        source_code = """
using System.IO;
public class GeneratedProcessor {
    public void DangerousAction() {
        File.WriteAllText("danger.txt", "should not exist");
    }
}
"""
        test_code = """
using Xunit;
public class SideEffectTest {
    [Fact]
    public void TestDangerousAction() {
        var p = new GeneratedProcessor();
        p.DangerousAction();
        // ここで例外が出なければ（モックされていれば）成功
    }
}
"""
        # 副作用フラグをTrueにして実行
        runtime_result = self.verifier.verify_runtime(source_code, test_code, has_side_effects=True)

        self.assertFalse(runtime_result["success"])
        self.assertEqual(
            "SIDE_EFFECT_EXECUTION_BLOCKED",
            runtime_result.get("error_type"),
        )

    def test_return_default_uses_hoisted_result_runtime_semantics(self):
        spec = {
            "module_name": "ReadOrDefault",
            "purpose": "Read a file or return the default value",
            "inputs": [],
            "outputs": [{
                "type_format": "string",
                "description": "file content",
            }],
            "constraints": [],
            "test_cases": [],
            "data_sources": [{
                "id": "input_file",
                "kind": "file",
                "description": "input file",
            }],
            "steps": [{
                "id": "step_1",
                "text": "ReadAllText",
                "kind": "ACTION",
                "intent": "FETCH",
                "explicit_intent": True,
                "target_entity": "string",
                "input_refs": [],
                "output_type": "string",
                "side_effect": "IO",
                "source_ref": "input_file",
                "source_kind": "file",
                "semantic_roles": {
                    "path": "missing-input.txt",
                    "error_policy": "return_default",
                },
            }],
        }
        result = self.synthesizer.synthesize_from_structured_spec(
            "ReadOrDefault",
            spec,
        )
        self.assertEqual("success", result.get("status"), result)

        test_code = """
using Xunit;

public class GeneratedReturnDefaultRuntimeTest
{
    [Fact]
    public void ReturnsDefaultWhenReadFails()
    {
        var processor = new GeneratedProcessor();

        var result = processor.ReadOrDefault();

        Assert.Equal(string.Empty, result);
    }
}
"""
        runtime_result = self.verifier.verify_runtime(
            result["code"],
            test_code,
            dependencies=[],
        )
        self.assertTrue(runtime_result["success"], runtime_result)
        self.assertEqual(1, runtime_result["summary"]["passed"])

    def test_generated_http_request_runtime_semantics(self):
        spec = {
            "module_name": "FetchSecureData",
            "purpose": "Fetch data with an API key",
            "inputs": [{
                "name": "apiKey",
                "type_format": "string",
                "description": "API key",
            }, {
                "name": "cancellationToken",
                "type_format": "CancellationToken",
                "description": "caller cancellation",
            }],
            "outputs": [{
                "type_format": "Task<string>",
                "description": "response body",
            }],
            "constraints": [],
            "test_cases": [],
            "data_sources": [{
                "id": "secure_api",
                "kind": "http",
                "description": "secure endpoint",
            }],
            "steps": [{
                "id": "step_1",
                "text": "secure endpoint request",
                "kind": "ACTION",
                "intent": "HTTP_REQUEST",
                "explicit_intent": True,
                "target_entity": "string",
                "input_refs": [],
                "output_type": "string",
                "side_effect": "IO",
                "source_ref": "secure_api",
                "source_kind": "http",
                "semantic_roles": {
                    "url": "https://example.test/data",
                    "http_method": "GET",
                    "api_key_header": "X-API-Key",
                    "api_key_input": "apiKey",
                    "cancellation_token_input": "cancellationToken",
                    "timeout_ms": 5000,
                    "ops": ["use_api_key_header"],
                    "error_policy": "rethrow",
                },
            }],
        }
        result = self.synthesizer.synthesize_from_structured_spec(
            "FetchSecureData",
            spec,
        )
        self.assertEqual("success", result.get("status"), result)
        self.assertNotIn("DefaultRequestHeaders", result.get("code", ""))
        self.assertIn(
            "CancellationTokenSource.CreateLinkedTokenSource(cancellationToken)",
            result.get("code", ""),
        )
        self.assertNotIn(
            "if (cancellationToken == null)",
            result.get("code", ""),
        )

        test_code = """
using System.Net;
using System.Net.Http;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Xunit;

public sealed class BlockingContent : HttpContent
{
    protected override Task SerializeToStreamAsync(
        Stream stream,
        TransportContext? context) => Task.CompletedTask;

    protected override Task SerializeToStreamAsync(
        Stream stream,
        TransportContext? context,
        CancellationToken cancellationToken) =>
        Task.Delay(Timeout.Infinite, cancellationToken);

    protected override bool TryComputeLength(out long length)
    {
        length = 0;
        return false;
    }
}

public sealed class RecordingHandler : HttpMessageHandler
{
    public string? ApiKey { get; private set; }
    public HttpMethod? Method { get; private set; }
    public HttpStatusCode StatusCode { get; set; } = HttpStatusCode.OK;
    public bool BlockBody { get; set; }

    protected override Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        Method = request.Method;
        ApiKey = request.Headers.GetValues("X-API-Key").Single();
        var response = new HttpResponseMessage(StatusCode)
        {
            Content = BlockBody
                ? new BlockingContent()
                : new StringContent("expected-body")
        };
        return Task.FromResult(response);
    }
}

public class GeneratedHttpRuntimeTest
{
    [Fact]
    public async Task SendsExplicitRequestMetadata()
    {
        var handler = new RecordingHandler();
        using var client = new HttpClient(handler);
        var processor = new GeneratedProcessor(client);

        var body = await processor.FetchSecureData(
            "secret",
            CancellationToken.None);

        Assert.Equal("expected-body", body);
        Assert.Equal("secret", handler.ApiKey);
        Assert.Equal(HttpMethod.Get, handler.Method);
    }

    [Fact]
    public async Task RethrowsHttpFailure()
    {
        var handler = new RecordingHandler
        {
            StatusCode = HttpStatusCode.InternalServerError
        };
        using var client = new HttpClient(handler);
        var processor = new GeneratedProcessor(client);

        await Assert.ThrowsAsync<HttpRequestException>(
            () => processor.FetchSecureData(
                "secret",
                CancellationToken.None));
    }

    [Fact]
    public async Task PropagatesCallerCancellation()
    {
        var handler = new RecordingHandler();
        using var client = new HttpClient(handler);
        var processor = new GeneratedProcessor(client);
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(
            () => processor.FetchSecureData(
                "secret",
                cancellation.Token));
    }

    [Fact]
    public async Task CancelsResponseBodyRead()
    {
        var handler = new RecordingHandler { BlockBody = true };
        using var client = new HttpClient(handler);
        var processor = new GeneratedProcessor(client);
        using var cancellation = new CancellationTokenSource();
        cancellation.CancelAfter(TimeSpan.FromMilliseconds(50));

        await Assert.ThrowsAnyAsync<OperationCanceledException>(
            () => processor.FetchSecureData(
                "secret",
                cancellation.Token));
    }
}
"""
        runtime_result = self.verifier.verify_runtime(
            result["code"],
            test_code,
            dependencies=[],
        )

        self.assertTrue(
            runtime_result["success"],
            runtime_result,
        )
        self.assertEqual(4, runtime_result["summary"]["passed"])

    def test_generated_http_post_runtime_semantics(self):
        spec = {
            "module_name": "PostJsonData",
            "purpose": "Post an explicit JSON payload",
            "inputs": [{
                "name": "payload",
                "type_format": "string",
                "description": "JSON payload",
            }, {
                "name": "cancellationToken",
                "type_format": "CancellationToken",
                "description": "caller cancellation",
            }],
            "outputs": [{
                "type_format": "Task<string>",
                "description": "response body",
            }],
            "constraints": [],
            "test_cases": [],
            "data_sources": [{
                "id": "json_api",
                "kind": "http",
                "description": "JSON endpoint",
            }],
            "steps": [{
                "id": "step_1",
                "text": "post JSON",
                "kind": "ACTION",
                "intent": "HTTP_REQUEST",
                "explicit_intent": True,
                "target_entity": "string",
                "input_refs": [],
                "output_type": "string",
                "side_effect": "IO",
                "source_ref": "json_api",
                "source_kind": "http",
                "semantic_roles": {
                    "url": "https://example.test/data",
                    "http_method": "POST",
                    "payload_input": "payload",
                    "content_type": "application/json",
                    "cancellation_token_input": "cancellationToken",
                    "timeout_ms": 5000,
                    "ops": ["structured_http_request"],
                    "error_policy": "rethrow",
                },
            }],
        }
        result = self.synthesizer.synthesize_from_structured_spec(
            "PostJsonData",
            spec,
        )
        self.assertEqual("success", result.get("status"), result)
        self.assertIn("HttpMethod.Post", result.get("code", ""))
        self.assertIn(
            'new StringContent(payload, Encoding.UTF8, "application/json")',
            result.get("code", ""),
        )

        test_code = """
using System.Net;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Xunit;

public sealed class RecordingPostHandler : HttpMessageHandler
{
    public HttpMethod? Method { get; private set; }
    public string? Payload { get; private set; }
    public string? MediaType { get; private set; }

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        Method = request.Method;
        Payload = await request.Content!.ReadAsStringAsync(cancellationToken);
        MediaType = request.Content.Headers.ContentType!.MediaType;
        return new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent("created")
        };
    }
}

public class GeneratedHttpPostRuntimeTest
{
    [Fact]
    public async Task SendsExplicitPayloadMetadata()
    {
        var handler = new RecordingPostHandler();
        using var client = new HttpClient(handler);
        var processor = new GeneratedProcessor(client);

        var body = await processor.PostJsonData(
            "{\\"id\\":42}",
            CancellationToken.None);

        Assert.Equal("created", body);
        Assert.Equal(HttpMethod.Post, handler.Method);
        Assert.Equal("{\\"id\\":42}", handler.Payload);
        Assert.Equal("application/json", handler.MediaType);
    }
}
"""
        runtime_result = self.verifier.verify_runtime(
            result["code"],
            test_code,
            dependencies=[],
        )
        self.assertTrue(runtime_result["success"], runtime_result)
        self.assertEqual(1, runtime_result["summary"]["passed"])

    def test_generated_database_update_runtime_semantics(self):
        parser = StructuredDesignParser()
        spec = parser.parse_design_file(
            "scenarios/StateUpdatePersist.design.md"
        )
        spec["inputs"].append({
            "name": "cancellationToken",
            "type_format": "CancellationToken",
            "description": "caller cancellation",
        })
        for step_index in (0, 2):
            spec["steps"][step_index]["semantic_roles"][
                "cancellation_token_input"
            ] = "cancellationToken"
            spec["steps"][step_index]["semantic_roles"][
                "error_policy"
            ] = "rethrow"
        result = self.synthesizer.synthesize_from_structured_spec(
            spec["module_name"],
            spec,
        )
        self.assertEqual("success", result.get("status"), result)
        self.assertIn(
            'parameters: item, cancellationToken: cancellationToken',
            result.get("code", ""),
        )

        test_code = """
using System;
using System.Threading;
using System.Threading.Tasks;
using Dapper;
using Microsoft.Data.Sqlite;
using Xunit;

public class GeneratedDatabaseRuntimeTest
{
    [Fact]
    public async Task UpdatesTheExactLoadedUser()
    {
        await using var connection = new SqliteConnection("Data Source=:memory:");
        await connection.OpenAsync();
        await connection.ExecuteAsync(
            "CREATE TABLE Users (" +
            "Id INTEGER PRIMARY KEY, Name TEXT, Age INTEGER, Email TEXT, " +
            "Points INTEGER, Price NUMERIC, LastLoginAt TEXT)");
        await connection.ExecuteAsync(
            "INSERT INTO Users " +
            "(Id, Name, Age, Email, Points, Price, LastLoginAt) " +
            "VALUES (1, 'Alice', 20, 'alice@example.test', 10, 12.5, NULL)");

        var processor = new GeneratedProcessor(connection);
        var succeeded = await processor.StateUpdatePersist(
            1,
            CancellationToken.None);
        var updated = await connection.QuerySingleAsync<string>(
            "SELECT LastLoginAt FROM Users WHERE Id = 1");

        Assert.True(succeeded);
        Assert.False(string.IsNullOrWhiteSpace(updated));
    }

    [Fact]
    public async Task PropagatesDatabaseCancellation()
    {
        await using var connection = new SqliteConnection("Data Source=:memory:");
        await connection.OpenAsync();
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();
        var processor = new GeneratedProcessor(connection);

        await Assert.ThrowsAnyAsync<OperationCanceledException>(
            () => processor.StateUpdatePersist(1, cancellation.Token));
    }
}
"""
        runtime_result = self.verifier.verify_runtime(
            result["code"],
            test_code,
            dependencies=[
                {"name": "Dapper", "version": "2.1.35"},
                {
                    "name": "Microsoft.Data.Sqlite",
                    "version": "10.0.0",
                },
            ],
        )

        self.assertTrue(
            runtime_result["success"],
            repr(runtime_result),
        )
        self.assertEqual(2, runtime_result["summary"]["passed"])

    def test_generated_aggregation_runtime_semantics(self):
        parser = StructuredDesignParser()
        spec = parser.parse_design_file(
            "scenarios/AggregationSummary.design.md"
        )
        result = self.synthesizer.synthesize_from_structured_spec(
            spec["module_name"],
            spec,
        )
        self.assertEqual("success", result.get("status"), result)

        test_code = """
using System;
using System.Globalization;
using System.IO;
using Xunit;

public class GeneratedAggregationRuntimeTest
{
    [Fact]
    public void AggregatesOrderTotals()
    {
        File.WriteAllText(
            "orders.json",
            "[{\\"Id\\":1,\\"Total\\":10.5},{\\"Id\\":2,\\"Total\\":5.0}]");
        var originalOut = Console.Out;
        using var output = new StringWriter(CultureInfo.InvariantCulture);
        try
        {
            Console.SetOut(output);
            var processor = new GeneratedProcessor();

            var succeeded = processor.AggregationSummary();

            Assert.True(succeeded);
            Assert.Contains("15.5", output.ToString());
        }
        finally
        {
            Console.SetOut(originalOut);
            File.Delete("orders.json");
        }
    }

    [Fact]
    public void InvalidJsonReturnsFailure()
    {
        File.WriteAllText("orders.json", "{ invalid json");
        try
        {
            var processor = new GeneratedProcessor();

            var succeeded = processor.AggregationSummary();

            Assert.False(succeeded);
        }
        finally
        {
            File.Delete("orders.json");
        }
    }

    [Fact]
    public void MissingFileReturnsFailure()
    {
        File.Delete("orders.json");
        var processor = new GeneratedProcessor();

        var succeeded = processor.AggregationSummary();

        Assert.False(succeeded);
    }
}
"""
        runtime_result = self.verifier.verify_runtime(
            result["code"],
            test_code,
            dependencies=[],
        )

        self.assertTrue(
            runtime_result["success"],
            repr(runtime_result),
        )
        self.assertEqual(3, runtime_result["summary"]["passed"])

    def test_generated_wrapper_runtime_semantics(self):
        fixture_methods = [
            {
                "id": "runtime_flaky",
                "name": "Run",
                "class": "RuntimeFixtures.Flaky",
                "return_type": "void",
                "params": [],
                "code": "RuntimeFixtures.Flaky.Run()",
                "intent": "GENERAL",
                "role": "ACTION",
                "capabilities": ["ACTION"],
                "code_body": """
namespace RuntimeFixtures {
    public static class Flaky {
        public static int Attempts { get; private set; }
        public static void Reset() => Attempts = 0;
        public static void Run() {
            Attempts++;
            if (Attempts < 3) throw new System.InvalidOperationException("retry");
        }
    }
}""",
            },
            {
                "id": "runtime_slow",
                "name": "Run",
                "class": "RuntimeFixtures.Slow",
                "return_type": "void",
                "params": [],
                "code": "RuntimeFixtures.Slow.Run()",
                "intent": "GENERAL",
                "role": "ACTION",
                "capabilities": ["ACTION"],
                "code_body": """
namespace RuntimeFixtures {
    public static class Slow {
        public static void Run() => System.Threading.Thread.Sleep(200);
    }
}""",
            },
            {
                "id": "runtime_transaction_success",
                "name": "Enlist",
                "class": "RuntimeFixtures.TransactionProbe",
                "return_type": "void",
                "params": [],
                "code": "RuntimeFixtures.TransactionProbe.Enlist()",
                "intent": "GENERAL",
                "role": "ACTION",
                "capabilities": ["ACTION"],
                "code_body": """
namespace RuntimeFixtures {
    public sealed class TransactionProbe : System.Transactions.IEnlistmentNotification {
        public static int Commits { get; private set; }
        public static int Rollbacks { get; private set; }
        public static void Reset() { Commits = 0; Rollbacks = 0; }
        public static void Enlist() {
            var transaction = System.Transactions.Transaction.Current
                ?? throw new System.InvalidOperationException("no transaction");
            transaction.EnlistVolatile(new TransactionProbe(), System.Transactions.EnlistmentOptions.None);
        }
        public static void EnlistAndThrow() {
            Enlist();
            throw new System.InvalidOperationException("rollback");
        }
        public void Commit(System.Transactions.Enlistment enlistment) { Commits++; enlistment.Done(); }
        public void InDoubt(System.Transactions.Enlistment enlistment) { enlistment.Done(); }
        public void Prepare(System.Transactions.PreparingEnlistment enlistment) { enlistment.Prepared(); }
        public void Rollback(System.Transactions.Enlistment enlistment) { Rollbacks++; enlistment.Done(); }
    }
}""",
            },
            {
                "id": "runtime_transaction_failure",
                "name": "EnlistAndThrow",
                "class": "RuntimeFixtures.TransactionProbe",
                "return_type": "void",
                "params": [],
                "code": "RuntimeFixtures.TransactionProbe.EnlistAndThrow()",
                "intent": "GENERAL",
                "role": "ACTION",
                "capabilities": ["ACTION"],
                "code_body": """
namespace RuntimeFixtures {
    public sealed class TransactionProbe : System.Transactions.IEnlistmentNotification {
        public static int Commits { get; private set; }
        public static int Rollbacks { get; private set; }
        public static void Reset() { Commits = 0; Rollbacks = 0; }
        public static void Enlist() {
            var transaction = System.Transactions.Transaction.Current
                ?? throw new System.InvalidOperationException("no transaction");
            transaction.EnlistVolatile(new TransactionProbe(), System.Transactions.EnlistmentOptions.None);
        }
        public static void EnlistAndThrow() {
            Enlist();
            throw new System.InvalidOperationException("rollback");
        }
        public void Commit(System.Transactions.Enlistment enlistment) { Commits++; enlistment.Done(); }
        public void InDoubt(System.Transactions.Enlistment enlistment) { enlistment.Done(); }
        public void Prepare(System.Transactions.PreparingEnlistment enlistment) { enlistment.Prepared(); }
        public void Rollback(System.Transactions.Enlistment enlistment) { Rollbacks++; enlistment.Done(); }
    }
}""",
            },
        ]
        for method in fixture_methods:
            self.synthesizer.method_store.add_method(method, overwrite=True)
        self.synthesizer = CodeSynthesizer(
            self.cm,
            method_store=self.synthesizer.method_store,
        )

        def wrapper_ir(kind, method_id, metadata):
            return {
                "logic_tree": [{
                    "id": f"wrap_{kind}",
                    "type": "ACTION",
                    "original_text": kind,
                    "intent": "GENERAL",
                    "role": "ACTION",
                    "cardinality": "SINGLE",
                    "target_entity": "Item",
                    "output_type": "void",
                    "source_kind": None,
                    "source_ref": None,
                    "input_link": None,
                    "semantic_map": {
                        "spec_role": "WRAP",
                        "semantic_roles": {
                            "wrapper_kind": kind,
                            **metadata,
                        },
                    },
                    "children": [{
                        "id": f"child_{kind}",
                        "type": "ACTION",
                        "original_text": method_id,
                        "intent": "GENERAL",
                        "role": "ACTION",
                        "cardinality": "SINGLE",
                        "target_entity": "Item",
                        "output_type": "void",
                        "source_kind": None,
                        "source_ref": None,
                        "input_link": f"wrap_{kind}",
                        "semantic_map": {
                            "spec_role": "ACTION",
                            "semantic_roles": {},
                            "logic": [],
                        },
                        "explicit_method_id": method_id,
                        "children": [],
                        "else_children": [],
                    }],
                    "else_children": [],
                }]
            }

        cases = [
            (
                "RetryRuntime",
                wrapper_ir(
                    "retry",
                    "runtime_flaky",
                    {"max_attempts": 3, "exception_type": "Exception"},
                ),
                """
using Xunit;
public class RetryRuntimeTest {
    [Fact]
    public void RetriesUntilThirdAttempt() {
        RuntimeFixtures.Flaky.Reset();
        new GeneratedProcessor().RetryRuntime();
        Assert.Equal(3, RuntimeFixtures.Flaky.Attempts);
    }
}""",
            ),
            (
                "TimeoutRuntime",
                wrapper_ir(
                    "timeout",
                    "runtime_slow",
                    {
                        "timeout_ms": 20,
                        "timeout_resolution": "explicit_timeout_ms",
                    },
                ),
                """
using System;
using Xunit;
public class TimeoutRuntimeTest {
    [Fact]
    public void ThrowsAfterTimeout() {
        Assert.Throws<TimeoutException>(
            () => new GeneratedProcessor().TimeoutRuntime());
    }
}""",
            ),
            (
                "TransactionCommitRuntime",
                wrapper_ir(
                    "transaction",
                    "runtime_transaction_success",
                    {"transaction_resolution": "explicit_transaction_wrapper"},
                ),
                """
using Xunit;
public class TransactionCommitRuntimeTest {
    [Fact]
    public void CommitsCompletedTransaction() {
        RuntimeFixtures.TransactionProbe.Reset();
        new GeneratedProcessor().TransactionCommitRuntime();
        Assert.Equal(1, RuntimeFixtures.TransactionProbe.Commits);
        Assert.Equal(0, RuntimeFixtures.TransactionProbe.Rollbacks);
    }
}""",
            ),
            (
                "TransactionRollbackRuntime",
                wrapper_ir(
                    "transaction",
                    "runtime_transaction_failure",
                    {"transaction_resolution": "explicit_transaction_wrapper"},
                ),
                """
using System;
using Xunit;
public class TransactionRollbackRuntimeTest {
    [Fact]
    public void RollsBackIncompleteTransaction() {
        RuntimeFixtures.TransactionProbe.Reset();
        Assert.Throws<InvalidOperationException>(
            () => new GeneratedProcessor().TransactionRollbackRuntime());
        Assert.Equal(0, RuntimeFixtures.TransactionProbe.Commits);
        Assert.Equal(1, RuntimeFixtures.TransactionProbe.Rollbacks);
    }
}""",
            ),
        ]

        for method_name, ir_tree, test_code in cases:
            with self.subTest(method_name=method_name):
                generated = self.synthesizer._synthesize_from_ir_tree(
                    method_name,
                    ir_tree,
                    expected_steps=1,
                )
                self.assertEqual("success", generated.get("status"), generated)
                runtime_result = self.verifier.verify_runtime(
                    generated["code"],
                    test_code,
                    dependencies=[],
                )
                self.assertTrue(runtime_result["success"], repr(runtime_result))
                self.assertEqual(1, runtime_result["summary"]["passed"])

if __name__ == "__main__":
    unittest.main()
