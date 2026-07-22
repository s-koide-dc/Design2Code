# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Dict, List


def csharp_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def csharp_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return csharp_string_literal(value)
    raise TypeError(f"Unsupported oracle literal type: {type(value).__name__}")


def _render_text_assertions(expression: str, assertion: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for expected in assertion.get("contains", []) or []:
        lines.append(f"        Assert.Contains({csharp_string_literal(expected)}, {expression});")
    for expected in assertion.get("not_contains", []) or []:
        lines.append(f"        Assert.DoesNotContain({csharp_string_literal(expected)}, {expression});")
    return lines


def _has_http_body_assertions(requests: List[Dict[str, Any]]) -> bool:
    return any(bool(request.get("body")) for request in requests)


def _render_http_handler(responses: List[Dict[str, Any]]) -> List[str]:
    if not responses:
        return []
    response_items = []
    for response in responses:
        response_items.append(
            "        new RuntimeOracleHttpResponse("
            f"{int(response['status_code'])}, "
            f"{csharp_string_literal(response['body'])}, "
            f"{csharp_string_literal(response.get('content_type', 'application/json'))})"
        )
    return [
        "public sealed record RuntimeOracleHttpResponse(int StatusCode, string Body, string ContentType);",
        "",
        "public sealed class RuntimeOracleHttpHandler : HttpMessageHandler",
        "{",
        "    private readonly Queue<RuntimeOracleHttpResponse> _responses;",
        "    public RuntimeOracleHttpHandler(IEnumerable<RuntimeOracleHttpResponse> responses)",
        "    {",
        "        _responses = new Queue<RuntimeOracleHttpResponse>(responses);",
        "    }",
        "",
        "    public List<HttpRequestMessage> Requests { get; } = new List<HttpRequestMessage>();",
        "",
        "    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)",
        "    {",
        "        Requests.Add(request);",
        '        var responseSpec = _responses.Count > 0 ? _responses.Dequeue() : new RuntimeOracleHttpResponse(500, "No runtime oracle response configured.", "text/plain");',
        "        var response = new HttpResponseMessage((HttpStatusCode)responseSpec.StatusCode)",
        "        {",
        "            Content = new StringContent(responseSpec.Body)",
        "        };",
        "        response.Content.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue(responseSpec.ContentType);",
        "        return Task.FromResult(response);",
        "    }",
        "}",
        "",
        "public static class RuntimeOracleHttpFixtures",
        "{",
        "    public static IReadOnlyList<RuntimeOracleHttpResponse> Responses { get; } = new List<RuntimeOracleHttpResponse>",
        "    {",
        ",\n".join(response_items),
        "    };",
        "}",
        "",
    ]


def _render_sqlite_setup(sqlite: Dict[str, Any]) -> List[str]:
    if not sqlite:
        return []
    lines = [
        '        await using var connection = new SqliteConnection("Data Source=:memory:");',
        "        await connection.OpenAsync();",
    ]
    for statement in sqlite.get("schema", []) or []:
        lines.append(f"        await connection.ExecuteAsync({csharp_string_literal(statement)});")
    for statement in sqlite.get("seed", []) or []:
        lines.append(f"        await connection.ExecuteAsync({csharp_string_literal(statement)});")
    return lines


def _render_db_assertions(assertions: List[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    for index, assertion in enumerate(assertions):
        value_var = f"dbValue{index}"
        query_literal = csharp_string_literal(assertion["query"])
        lines.append(f"            var {value_var} = await connection.QuerySingleOrDefaultAsync<object>({query_literal});")
        if assertion.get("not_null"):
            lines.append(f"            Assert.NotNull({value_var});")
        if "equals" in assertion:
            lines.append(f"            Assert.Equal({csharp_literal(assertion['equals'])}, {value_var});")
        if "not_equals" in assertion:
            expected = assertion["not_equals"]
            if isinstance(expected, str):
                lines.append(f"            Assert.NotEqual({csharp_literal(expected)}, {value_var}?.ToString());")
            else:
                lines.append(f"            Assert.NotEqual({csharp_literal(expected)}, {value_var});")
        if "contains" in assertion:
            lines.append(f"            Assert.Contains({csharp_string_literal(assertion['contains'])}, {value_var}?.ToString());")
    return lines


def build_runtime_oracle_test_code(module_name: str, contract: Dict[str, Any]) -> str:
    method_args = ", ".join(csharp_literal(arg) for arg in contract.get("method_args", []) or [])
    fixtures = contract.get("fixtures", []) or []
    stdin = contract.get("stdin")
    environment = contract.get("environment", {}) or {}
    http_responses = contract.get("http_responses", []) or []
    http_requests = contract.get("http_requests", []) or []
    uses_http = bool(http_responses or http_requests)
    sqlite = contract.get("sqlite", {}) or {}
    db_assertions = contract.get("db_assertions", []) or []
    uses_sqlite = bool(sqlite or db_assertions)
    file_assertions = contract.get("files", []) or []
    has_stdout = bool(contract.get("stdout"))
    awaits_call = bool(contract.get("await"))
    awaits_request_assertions = _has_http_body_assertions(http_requests)
    call_prefix = "var result = " if "return" in contract else ""
    test_signature = (
        "public async Task ExplicitRuntimeOraclePasses()"
        if awaits_call or uses_sqlite or awaits_request_assertions
        else "public void ExplicitRuntimeOraclePasses()"
    )
    await_prefix = "await " if awaits_call else ""
    if uses_sqlite and uses_http:
        processor_expr = "new GeneratedProcessor(connection, httpClient)"
    elif uses_sqlite:
        processor_expr = "new GeneratedProcessor(connection)"
    elif uses_http:
        processor_expr = "new GeneratedProcessor(httpClient)"
    else:
        processor_expr = "new GeneratedProcessor()"
    lines: List[str] = [
        "using System;",
        "using System.Collections.Generic;",
        "using System.Globalization;",
        "using System.IO;",
        "using System.Net;",
        "using System.Net.Http;",
        "using System.Threading;",
        "using System.Threading.Tasks;",
        "using Xunit;",
        "",
    ]
    if uses_sqlite:
        lines.insert(-2, "using Dapper;")
        lines.insert(-2, "using Microsoft.Data.Sqlite;")
    default_response = [{"status_code": 500, "body": ""}] if uses_http and not http_responses else []
    lines.extend(_render_http_handler(http_responses or default_response))
    lines.extend([
        "public class RuntimeOracleTest",
        "{",
        "    [Fact]",
        f"    {test_signature}",
        "    {",
        '        var root = Path.Combine(Path.GetTempPath(), "runtime-oracle-" + Guid.NewGuid().ToString("N"));',
        "        Directory.CreateDirectory(root);",
        "        var previousDirectory = Directory.GetCurrentDirectory();",
        "        var originalOut = Console.Out;",
        "        var originalIn = Console.In;",
        "        using var capturedOut = new StringWriter(CultureInfo.InvariantCulture);",
    ])
    if environment:
        lines.append("        var previousEnvironment = new Dictionary<string, string?>();")
        for name in environment:
            name_literal = csharp_string_literal(str(name))
            lines.append(f"        previousEnvironment[{name_literal}] = Environment.GetEnvironmentVariable({name_literal});")
    if uses_http:
        lines.extend([
            "        var handler = new RuntimeOracleHttpHandler(RuntimeOracleHttpFixtures.Responses);",
            "        using var httpClient = new HttpClient(handler);",
        ])
    lines.extend(_render_sqlite_setup(sqlite))
    lines.extend([
        "        try",
        "        {",
        "            Directory.SetCurrentDirectory(root);",
    ])
    for fixture in fixtures:
        lines.append(
            f"            File.WriteAllText({csharp_string_literal(fixture['path'])}, {csharp_string_literal(fixture['content'])});"
        )
    for name, value in environment.items():
        lines.append(
            f"            Environment.SetEnvironmentVariable({csharp_string_literal(str(name))}, {csharp_literal(value)});"
        )
    if stdin is not None:
        lines.append(f"            Console.SetIn(new StringReader({csharp_string_literal(stdin)}));")
    if has_stdout:
        lines.append("            Console.SetOut(capturedOut);")
    lines.extend([
        "",
        f"            {call_prefix}{await_prefix}{processor_expr}.{module_name}({method_args});",
    ])
    if "return" in contract:
        lines.append(f"            Assert.Equal({csharp_literal(contract['return'])}, result);")
    if has_stdout:
        lines.append("            var stdout = capturedOut.ToString();")
        lines.extend(_render_text_assertions("stdout", contract["stdout"]))
    for file_assertion in file_assertions:
        file_path = csharp_string_literal(file_assertion["path"])
        lines.append(f"            Assert.True(File.Exists({file_path}), \"Expected output file to exist: {file_assertion['path']}\");")
        if file_assertion.get("contains") or file_assertion.get("not_contains"):
            file_var = f"fileText{len(lines)}"
            lines.append(f"            var {file_var} = File.ReadAllText({file_path});")
            lines.extend(_render_text_assertions(file_var, file_assertion))
    if http_requests:
        lines.append(f"            Assert.Equal({len(http_requests)}, handler.Requests.Count);")
        for index, request in enumerate(http_requests):
            if request.get("method"):
                lines.append(
                    f"            Assert.Equal({csharp_string_literal(request['method'].upper())}, handler.Requests[{index}].Method.Method);"
                )
            if request.get("url"):
                lines.append(
                    f"            Assert.Equal({csharp_string_literal(request['url'])}, handler.Requests[{index}].RequestUri?.ToString());"
                )
            for header_index, (header_name, header_value) in enumerate((request.get("headers") or {}).items()):
                values_var = f"headerValues{index}_{header_index}"
                lines.append(
                    f"            Assert.True(handler.Requests[{index}].Headers.TryGetValues({csharp_string_literal(header_name)}, out var {values_var}), \"Expected HTTP request header: {header_name}\");"
                )
                lines.append(
                    f"            Assert.Contains({csharp_string_literal(header_value)}, {values_var});"
                )
            if request.get("body"):
                body_var = f"requestBody{index}"
                lines.append(f"            var {body_var} = await handler.Requests[{index}].Content!.ReadAsStringAsync();")
                lines.extend(_render_text_assertions(body_var, request["body"]))
    if db_assertions:
        lines.extend(_render_db_assertions(db_assertions))
    lines.extend([
        "        }",
        "        finally",
        "        {",
        "            Console.SetOut(originalOut);",
        "            Console.SetIn(originalIn);",
    ])
    if environment:
        for name in environment:
            name_literal = csharp_string_literal(str(name))
            lines.append(
                f"            Environment.SetEnvironmentVariable({name_literal}, previousEnvironment[{name_literal}]);"
            )
    lines.extend([
        "            Directory.SetCurrentDirectory(previousDirectory);",
        "            if (Directory.Exists(root))",
        "                Directory.Delete(root, recursive: true);",
        "        }",
        "    }",
        "}",
    ])
    return "\n".join(lines)
