# -*- coding: utf-8 -*-
import unittest

from src.utils.spec_auditor import SpecAuditor


class TestSpecAuditorLoopUsage(unittest.TestCase):
    def test_loop_consumes_input_link_output(self):
        spec = {
            "module_name": "LoopInputLink",
            "purpose": "loop consumes upstream output",
            "inputs": [],
            "outputs": [{"type_format": "void"}],
            "steps": [
                {"id": "step_1", "kind": "ACTION", "intent": "FETCH", "target_entity": "Order", "input_refs": [], "output_type": "IEnumerable<Order>", "side_effect": "NONE", "text": "取得"},
                {"id": "step_2", "kind": "LOOP", "intent": "GENERAL", "target_entity": "Order", "input_refs": ["step_1"], "output_type": "void", "side_effect": "NONE", "text": "繰り返す"}
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }
        synthesis_result = {
            "trace": {
                "ir_tree": {
                    "logic_tree": [
                        {"id": "step_1"},
                        {"id": "step_2", "input_link": "step_1"}
                    ]
                },
                "best_path": {
                    "statements": [
                        {"type": "raw", "code": "var orders = new List<Order>();", "node_id": "step_1", "out_var": "orders"},
                        {"type": "foreach", "source": "orders", "item_name": "order", "body": [], "node_id": "step_2"}
                    ],
                    "type_to_vars": {
                        "IEnumerable<Order>": [{"var_name": "orders", "node_id": "step_1"}]
                    }
                },
                "blueprint": {}
            }
        }
        issues = SpecAuditor().audit(spec, synthesis_result)
        self.assertFalse(any(i.startswith("SPEC_INPUT_LINK_UNUSED") for i in issues))

    def test_condition_consumes_loop_item(self):
        spec = {
            "module_name": "ConditionInputLink",
            "purpose": "condition consumes loop item",
            "inputs": [],
            "outputs": [{"type_format": "void"}],
            "steps": [
                {"id": "step_1", "kind": "ACTION", "intent": "FETCH", "target_entity": "Order", "input_refs": [], "output_type": "IEnumerable<Order>", "side_effect": "NONE", "text": "取得"},
                {"id": "step_2", "kind": "LOOP", "intent": "GENERAL", "target_entity": "Order", "input_refs": ["step_1"], "output_type": "void", "side_effect": "NONE", "text": "繰り返す"},
                {"id": "step_3", "kind": "CONDITION", "intent": "GENERAL", "target_entity": "Order", "input_refs": ["step_2"], "output_type": "bool", "side_effect": "NONE", "text": "条件"}
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }
        synthesis_result = {
            "trace": {
                "ir_tree": {
                    "logic_tree": [
                        {"id": "step_1"},
                        {"id": "step_2", "input_link": "step_1"},
                        {"id": "step_3", "input_link": "step_2"}
                    ]
                },
                "best_path": {
                    "statements": [
                        {"type": "raw", "code": "var orders = new List<Order>();", "node_id": "step_1", "out_var": "orders"},
                        {"type": "foreach", "source": "orders", "item_name": "order", "body": [], "node_id": "step_2"},
                        {"type": "if", "condition": "order.Total > 10", "body": [], "else_body": [], "node_id": "step_3"}
                    ],
                    "type_to_vars": {
                        "IEnumerable<Order>": [{"var_name": "orders", "node_id": "step_1"}],
                        "Order": [{"var_name": "order", "node_id": "step_2"}]
                    }
                },
                "blueprint": {}
            }
        }
        issues = SpecAuditor().audit(spec, synthesis_result)
        self.assertFalse(any(i.startswith("SPEC_INPUT_LINK_UNUSED") for i in issues))

    def test_inner_node_allows_parent_loop_usage(self):
        spec = {
            "module_name": "LoopInnerParentUsage",
            "purpose": "inner node uses item while parent consumes list",
            "inputs": [],
            "outputs": [{"type_format": "void"}],
            "steps": [
                {"id": "step_1", "kind": "ACTION", "intent": "FETCH", "target_entity": "Inventory", "input_refs": [], "output_type": "IEnumerable<Inventory>", "side_effect": "NONE", "text": "取得"},
                {"id": "step_2", "kind": "ACTION", "intent": "PERSIST", "target_entity": "Inventory", "input_refs": ["step_1"], "output_type": "void", "side_effect": "DB", "text": "保存"}
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }
        synthesis_result = {
            "trace": {
                "ir_tree": {
                    "logic_tree": [
                        {"id": "step_1"},
                        {"id": "step_2", "input_link": "step_1"},
                        {"id": "step_2_inner", "input_link": "step_1", "intent": "PERSIST"}
                    ]
                },
                "best_path": {
                    "statements": [
                        {"type": "raw", "code": "var inventory1 = new List<Inventory>();", "node_id": "step_1", "out_var": "inventory1"},
                        {"type": "foreach", "source": "inventory1", "item_name": "item", "body": [], "node_id": "step_2"},
                        {"type": "raw", "code": "db.Save(item);", "node_id": "step_2_inner", "intent": "PERSIST"}
                    ],
                    "type_to_vars": {
                        "IEnumerable<Inventory>": [{"var_name": "inventory1", "node_id": "step_1"}],
                        "Inventory": [{"var_name": "item", "node_id": "step_2"}]
                    }
                },
                "blueprint": {}
            }
        }
        issues = SpecAuditor().audit(spec, synthesis_result)
        self.assertFalse(any(i.startswith("SPEC_INPUT_LINK_UNUSED") for i in issues))


if __name__ == "__main__":
    unittest.main()
