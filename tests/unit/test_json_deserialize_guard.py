# -*- coding: utf-8 -*-
import unittest

from src.config.config_manager import ConfigManager
from src.design_parser.structured_parser import StructuredDesignParser
from src.code_synthesis.code_synthesizer import CodeSynthesizer


def _collect_statements(statements):
    collected = []
    for stmt in statements:
        collected.append(stmt)
        for key in ["body", "else_body", "catch_body"]:
            nested = stmt.get(key)
            if isinstance(nested, list):
                collected.extend(_collect_statements(nested))
    return collected


class TestJsonDeserializeGuard(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()
        self.parser = StructuredDesignParser()
        self.synthesizer = CodeSynthesizer(self.config)

    def test_json_deserialize_return_default_uses_helper_with_guard(self):
        spec = self.parser.parse_design_file("scenarios/SyncExternalData.design.md")
        result = self.synthesizer.synthesize_from_structured_spec(
            spec.get("module_name"),
            spec,
            return_trace=True
        )
        trace = result.get("trace", {})
        best_path = trace.get("best_path", {})
        statements = _collect_statements(best_path.get("statements", []))

        json_calls = [
            s for s in statements
            if s.get("intent") == "JSON_DESERIALIZE" and s.get("type") == "call"
        ]
        self.assertTrue(json_calls, "Expected helper call for JSON_DESERIALIZE statements in trace.")
        self.assertTrue(any("Deserialize" in str(stmt.get("call_expr", "")) for stmt in json_calls))
        self.assertTrue(any("out " in str(stmt.get("call_expr", "")) for stmt in json_calls))
        failure_guards = [
            s for s in statements
            if s.get("intent") == "JSON_DESERIALIZE"
            and s.get("type") == "raw"
            and str(s.get("code", "")).startswith("if (!")
        ]
        self.assertTrue(failure_guards, "Expected JSON helper failure guard in trace.")
        extra_code = "\n".join(best_path.get("extra_code", []))
        self.assertIn("JsonSerializer.Deserialize", extra_code)
        self.assertIn("GeneratedErrorLog.Write", extra_code)
        self.assertIn("catch (System.OperationCanceledException)", extra_code)


if __name__ == "__main__":
    unittest.main()
