import unittest

from src.code_verification.compilation_verifier import CompilationVerifier
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.config.config_manager import ConfigManager
from src.design_parser.structured_parser import StructuredDesignParser
from tests.unit import test_code_synthesizer_lambda as lambda_fixture


class TestGeneratedLambdaCompilation(unittest.TestCase):
    def test_file_filter_and_condition_outputs_compile(self):
        fixture = lambda_fixture.TestReproLambda()
        fixture.setUp()
        try:
            verifier = CompilationVerifier(fixture.cm)
            cases = [
                (
                    "FindTestFiles",
                    [
                        {
                            "text": "GetFiles",
                            "semantic_roles": {"path": "."},
                        },
                        "名前が'test'を含むもので絞り込む",
                    ],
                ),
                (
                    "CheckAndRead",
                    [
                        {
                            "text": "Exists",
                            "semantic_roles": {"path": "input.txt"},
                        },
                        "もし存在するならば",
                        {
                            "text": "ReadAllText",
                            "semantic_roles": {"path": "input.txt"},
                        },
                        "そうでなければ",
                        {
                            "text": "エラーログを出力する",
                            "semantic_roles": {
                                "output_channel": "stderr",
                                "log_level": "error",
                                "message": "入力ファイルが存在しません。",
                            },
                        },
                        "を終えて",
                    ],
                ),
                (
                    "ReadOrDefault",
                    [{
                        "text": "ReadAllText",
                        "intent": "FETCH",
                        "explicit_intent": True,
                        "source_kind": "file",
                        "semantic_roles": {
                            "path": "input.txt",
                            "error_policy": "return_default",
                        },
                    }],
                ),
            ]

            for method_name, steps in cases:
                with self.subTest(method_name=method_name):
                    generated = fixture.synthesizer.synthesize(method_name, steps)
                    verification = verifier.verify(
                        generated["code"],
                        dependencies=[],
                    )
                    self.assertTrue(
                        verification["valid"],
                        verification.get("errors"),
                    )
        finally:
            fixture.tearDown()

    def test_wrapper_outputs_compile(self):
        fixture = lambda_fixture.TestReproLambda()
        fixture.setUp()
        try:
            verifier = CompilationVerifier(fixture.cm)

            def wrapper_ir(kind, metadata):
                roles = {"wrapper_kind": kind, **metadata}
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
                            "semantic_roles": roles,
                        },
                        "children": [{
                            "id": f"display_{kind}",
                            "type": "ACTION",
                            "original_text": "display",
                            "intent": "DISPLAY",
                            "role": "DISPLAY",
                            "cardinality": "SINGLE",
                            "target_entity": "string",
                            "output_type": "void",
                            "source_kind": None,
                            "source_ref": None,
                            "input_link": f"wrap_{kind}",
                            "semantic_map": {
                                "spec_role": "DISPLAY",
                                "semantic_roles": {"message": "completed"},
                                "logic": [],
                            },
                            "children": [],
                            "else_children": [],
                        }],
                        "else_children": [],
                    }]
                }

            cases = [
                ("retry", {"max_attempts": 3, "exception_type": "Exception"}),
                (
                    "timeout",
                    {
                        "timeout_ms": 1000,
                        "timeout_resolution": "explicit_timeout_ms",
                    },
                ),
                (
                    "transaction",
                    {"transaction_resolution": "explicit_transaction_wrapper"},
                ),
            ]
            for kind, metadata in cases:
                with self.subTest(kind=kind):
                    generated = fixture.synthesizer._synthesize_from_ir_tree(
                        f"{kind.title()}Wrapper",
                        wrapper_ir(kind, metadata),
                        expected_steps=1,
                    )
                    self.assertEqual("success", generated.get("status"), generated)
                    verification = verifier.verify(
                        generated.get("code", ""),
                        dependencies=[],
                    )
                    self.assertTrue(
                        verification["valid"],
                        verification.get("errors"),
                    )
        finally:
            fixture.tearDown()

    def test_structured_scenarios_compile(self):
        config = ConfigManager()
        synthesizer = CodeSynthesizer(config)
        parser = StructuredDesignParser()
        verifier = CompilationVerifier(config)
        scenario_paths = [
            "scenarios/AggregationSummary.design.md",
            "scenarios/StateUpdatePersist.design.md",
            "scenarios/DailyInventorySync.design.md",
            "scenarios/SyncExternalData.design.md",
        ]
        semantic_expectations = {
            "scenarios/StateUpdatePersist.design.md": [
                "item.LastLoginAt = DateTime.Now;",
                'ExecuteAsync("UPDATE Users SET LastLoginAt = @LastLoginAt WHERE Id = @Id", item)',
                "return default;",
            ],
            "scenarios/DailyInventorySync.design.md": [
                'SendGeneratedHttpGetStringAsync(_httpClient, "https://inventory.example.com/api/current", "X-API-Key", input_1, 30000)',
                "new System.Net.Http.HttpRequestMessage(System.Net.Http.HttpMethod.Get, url)",
                "request.Headers.Add(headerName, headerValue);",
                "new System.Threading.CancellationTokenSource(System.TimeSpan.FromMilliseconds(timeoutMs))",
                "await httpClient.SendAsync(request, requestTimeout.Token);",
                "return default;",
            ],
            "scenarios/AggregationSummary.design.md": [
                "total += item.Total;",
                "return false;",
            ],
        }

        for scenario_path in scenario_paths:
            with self.subTest(scenario_path=scenario_path):
                spec = parser.parse_design_file(scenario_path)
                generated = synthesizer.synthesize_from_structured_spec(
                    spec["module_name"],
                    spec,
                    return_trace=True,
                )
                self.assertEqual("success", generated.get("status"), generated)
                code = generated.get("code", "")
                for expected_fragment in semantic_expectations.get(
                    scenario_path,
                    [],
                ):
                    self.assertIn(expected_fragment, code)
                if scenario_path == "scenarios/DailyInventorySync.design.md":
                    self.assertNotIn("DefaultRequestHeaders", code)
                dependencies = [
                    {"name": dependency}
                    for dependency in generated.get("dependencies", [])
                ]
                verification = verifier.verify(
                    code,
                    dependencies=dependencies,
                )
                self.assertTrue(
                    verification["valid"],
                    verification.get("errors"),
                )
