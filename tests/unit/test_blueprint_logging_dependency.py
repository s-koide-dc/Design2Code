# -*- coding: utf-8 -*-
import unittest

from src.code_synthesis.blueprint_assembler import BlueprintAssembler


class TestBlueprintLoggingDependency(unittest.TestCase):
    def test_preserves_ir_input_link_on_emitted_statement(self):
        assembler = BlueprintAssembler()
        blueprint = assembler.create_blueprint(
            "LoadAndShow",
            {"statements": [{"type": "raw", "node_id": "step_2", "code": "Console.WriteLine(value);"}]},
            ir_tree={
                "logic_tree": [
                    {"id": "step_1", "type": "ACTION"},
                    {"id": "step_2", "type": "ACTION", "input_link": "step_1"},
                ]
            },
        )

        statement = blueprint["methods"][0]["body"][0]
        self.assertEqual(["step_1"], statement["input_node_ids"])

    def test_logger_unused_does_not_add_logging(self):
        assembler = BlueprintAssembler()
        path = {
            "all_usings": set(["System"]),
            "statements": [{"type": "raw", "code": "return 42;"}],
            "poco_defs": {},
            "method_return_type": "int"
        }
        blueprint = assembler.create_blueprint("TestMethod", path, inputs=[], ir_tree={})
        self.assertNotIn("Microsoft.Extensions.Logging", blueprint.get("usings", []))
        self.assertFalse(any(f.get("name") == "_logger" for f in blueprint.get("fields", [])))

    def test_logger_used_adds_logging(self):
        assembler = BlueprintAssembler()
        path = {
            "all_usings": set(["System"]),
            "statements": [{"type": "raw", "code": "_logger.LogError(ex, \"fail\");"}],
            "poco_defs": {},
            "method_return_type": "int"
        }
        blueprint = assembler.create_blueprint("TestMethod", path, inputs=[], ir_tree={})
        self.assertIn("Microsoft.Extensions.Logging", blueprint.get("usings", []))
        self.assertTrue(any(f.get("name") == "_logger" for f in blueprint.get("fields", [])))


if __name__ == "__main__":
    unittest.main()
