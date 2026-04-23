# -*- coding: utf-8 -*-
import unittest

from src.config.config_manager import ConfigManager
from src.ir_generator.ir_generator import IRGenerator


class TestIRGeneratorStructuredSpec(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()
        self.generator = IRGenerator(self.config)

    def test_from_structured_spec_minimal(self):
        structured_spec = {
            "module_name": "Sample",
            "purpose": "demo",
            "inputs": [],
            "outputs": [],
            "constraints": [],
            "test_cases": [],
            "steps": [
                {
                    "id": "step_1",
                    "kind": "ACTION",
                    "intent": "FETCH",
                    "target_entity": "User",
                    "input_refs": [],
                    "output_type": "IEnumerable<User>",
                    "side_effect": "NONE",
                    "text": "全ユーザーを取得する"
                }
            ]
        }

        ir = self.generator.from_structured_spec(structured_spec)
        self.assertIn("logic_tree", ir)
        self.assertEqual(len(ir["logic_tree"]), 1)
        self.assertEqual(ir["logic_tree"][0]["intent"], "FETCH")

    def test_from_structured_spec_maps_control_kinds(self):
        structured_spec = {
            "module_name": "Flow",
            "purpose": "control flow mapping",
            "inputs": [],
            "outputs": [],
            "constraints": [],
            "test_cases": [],
            "steps": [
                {
                    "id": "step_1",
                    "kind": "ACTION",
                    "intent": "FETCH",
                    "target_entity": "User",
                    "input_refs": [],
                    "output_type": "IEnumerable<User>",
                    "side_effect": "NONE",
                    "text": "Fetch users"
                },
                {
                    "id": "step_2",
                    "kind": "CONDITION",
                    "intent": "EXISTS",
                    "target_entity": "User",
                    "input_refs": ["step_1"],
                    "output_type": "bool",
                    "side_effect": "NONE",
                    "text": "If user exists"
                },
                {
                    "id": "step_3",
                    "kind": "ACTION",
                    "intent": "DISPLAY",
                    "target_entity": "User",
                    "input_refs": ["step_2"],
                    "output_type": "void",
                    "side_effect": "NONE",
                    "text": "Show user"
                },
                {
                    "id": "step_4",
                    "kind": "ELSE",
                    "intent": "GENERAL",
                    "target_entity": "User",
                    "input_refs": ["step_2"],
                    "output_type": "void",
                    "side_effect": "NONE",
                    "text": "Else"
                },
                {
                    "id": "step_5",
                    "kind": "ACTION",
                    "intent": "DISPLAY",
                    "target_entity": "User",
                    "input_refs": ["step_2"],
                    "output_type": "void",
                    "side_effect": "NONE",
                    "text": "Show fallback"
                },
                {
                    "id": "step_6",
                    "kind": "END",
                    "intent": "GENERAL",
                    "target_entity": "User",
                    "input_refs": [],
                    "output_type": "void",
                    "side_effect": "NONE",
                    "text": "End if"
                },
                {
                    "id": "step_7",
                    "kind": "LOOP",
                    "intent": "GENERAL",
                    "target_entity": "User",
                    "input_refs": ["step_1"],
                    "output_type": "void",
                    "side_effect": "NONE",
                    "text": "For each user"
                },
                {
                    "id": "step_8",
                    "kind": "ACTION",
                    "intent": "DISPLAY",
                    "target_entity": "User",
                    "input_refs": ["step_7"],
                    "output_type": "void",
                    "side_effect": "NONE",
                    "text": "Print user"
                },
                {
                    "id": "step_9",
                    "kind": "END",
                    "intent": "GENERAL",
                    "target_entity": "User",
                    "input_refs": [],
                    "output_type": "void",
                    "side_effect": "NONE",
                    "text": "End loop"
                },
                {
                    "id": "step_10",
                    "kind": "ACTION",
                    "intent": "PERSIST",
                    "target_entity": "User",
                    "input_refs": ["step_1"],
                    "output_type": "void",
                    "side_effect": "NONE",
                    "text": "Save summary"
                }
            ]
        }

        ir = self.generator.from_structured_spec(structured_spec)
        self.assertEqual(len(ir["logic_tree"]), 4)

        cond = ir["logic_tree"][1]
        self.assertEqual(cond["type"], "CONDITION")
        self.assertEqual(len(cond["children"]), 1)
        self.assertEqual(len(cond["else_children"]), 1)

        loop = ir["logic_tree"][2]
        self.assertEqual(loop["type"], "LOOP")
        self.assertEqual(loop["cardinality"], "COLLECTION")
        self.assertEqual(len(loop["children"]), 1)


    def test_structured_db_intent_requires_db_evidence(self):
        structured_spec = {
            "module_name": "Sample",
            "purpose": "db guard",
            "inputs": [],
            "outputs": [],
            "constraints": [],
            "test_cases": [],
            "steps": [
                {
                    "id": "step_1",
                    "kind": "ACTION",
                    "intent": "DATABASE_QUERY",
                    "target_entity": "User",
                    "input_refs": [],
                    "output_type": "IEnumerable<User>",
                    "side_effect": "NONE",
                    "text": "ユーザーを取得する"
                }
            ]
        }

        ir = self.generator.from_structured_spec(structured_spec)
        self.assertEqual(ir["logic_tree"][0]["intent"], "FETCH")

    def test_structured_db_intent_with_source_kind_db(self):
        structured_spec = {
            "module_name": "Sample",
            "purpose": "db explicit",
            "inputs": [],
            "outputs": [],
            "constraints": [],
            "test_cases": [],
            "steps": [
                {
                    "id": "step_1",
                    "kind": "ACTION",
                    "intent": "DATABASE_QUERY",
                    "target_entity": "User",
                    "input_refs": [],
                    "output_type": "IEnumerable<User>",
                    "side_effect": "NONE",
                    "source_kind": "db",
                    "text": "ユーザーを取得する"
                }
            ]
        }

        ir = self.generator.from_structured_spec(structured_spec)
        self.assertEqual(ir["logic_tree"][0]["intent"], "DATABASE_QUERY")

    def test_return_literal_does_not_force_input_link(self):
        structured_spec = {
            "module_name": "ReturnLiteral",
            "purpose": "return literal should not chain",
            "inputs": [],
            "outputs": [],
            "constraints": [],
            "test_cases": [],
            "steps": [
                {
                    "id": "step_1",
                    "kind": "ACTION",
                    "intent": "FETCH",
                    "target_entity": "User",
                    "input_refs": [],
                    "output_type": "IEnumerable<User>",
                    "side_effect": "NONE",
                    "text": "ユーザーを取得する"
                },
                {
                    "id": "step_2",
                    "kind": "ACTION",
                    "intent": "RETURN",
                    "target_entity": "bool",
                    "input_refs": ["step_1"],
                    "output_type": "bool",
                    "side_effect": "NONE",
                    "text": "true を返す"
                }
            ]
        }

        ir = self.generator.from_structured_spec(structured_spec)
        self.assertEqual(len(ir["logic_tree"]), 2)
        self.assertEqual(ir["logic_tree"][1]["intent"], "RETURN")
        self.assertIsNone(ir["logic_tree"][1].get("input_link"))
if __name__ == "__main__":
    unittest.main()
