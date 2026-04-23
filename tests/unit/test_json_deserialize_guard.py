# -*- coding: utf-8 -*-
import unittest

from src.config.config_manager import ConfigManager
from src.design_parser.structured_parser import StructuredDesignParser
from src.code_synthesis.code_synthesizer import CodeSynthesizer


def _collect_statements(statements):
    collected = []
    for stmt in statements:
        collected.append(stmt)
        for key in ["body", "else_body"]:
            nested = stmt.get(key)
            if isinstance(nested, list):
                collected.extend(_collect_statements(nested))
    return collected


class TestJsonDeserializeGuard(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()
        self.parser = StructuredDesignParser()
        self.synthesizer = CodeSynthesizer(self.config)

    def test_json_deserialize_is_wrapped_with_try_catch(self):
        spec = self.parser.parse_design_file("scenarios/SyncExternalData.design.md")
        result = self.synthesizer.synthesize_from_structured_spec(
            spec.get("module_name"),
            spec,
            return_trace=True
        )
        trace = result.get("trace", {})
        best_path = trace.get("best_path", {})
        statements = _collect_statements(best_path.get("statements", []))

        json_stmts = [
            s for s in statements
            if s.get("intent") == "JSON_DESERIALIZE"
        ]
        self.assertTrue(json_stmts, "Expected JSON_DESERIALIZE statements in trace.")
        for stmt in json_stmts:
            self.assertEqual("raw", stmt.get("type"))
            code = stmt.get("code") or ""
            self.assertIn("try", code)
            self.assertIn("catch (Exception ex)", code)


if __name__ == "__main__":
    unittest.main()
