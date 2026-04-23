# -*- coding: utf-8 -*-
import unittest

from src.utils.spec_auditor import SpecAuditor


class TestSpecAuditorIntentAndRefs(unittest.TestCase):
    def test_input_link_drop_repro_expect_issue(self):
        spec = {
            "module_name": "InputLinkDropRepro",
            "purpose": "input_link drop repro",
            "inputs": [{"name": "input", "type_format": "int"}],
            "outputs": [{"type_format": "string"}],
            "steps": [
                {"id": "step_1", "kind": "ACTION", "intent": "DATABASE_QUERY", "target_entity": "User", "input_refs": [], "output_type": "IEnumerable<User>", "side_effect": "DB", "text": "取得"},
                {"id": "step_2", "kind": "ACTION", "intent": "LINQ", "target_entity": "User", "input_refs": ["step_1"], "output_type": "IEnumerable<User>", "side_effect": "NONE", "text": "抽出"},
                {"id": "step_3", "kind": "ACTION", "intent": "DISPLAY", "target_entity": "User", "input_refs": ["step_2"], "output_type": "string", "side_effect": "NONE", "text": "レポート作成"},
                {"id": "step_4", "kind": "ACTION", "intent": "PERSIST", "target_entity": "User", "input_refs": ["step_3"], "output_type": "void", "side_effect": "IO", "text": "保存"}
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": [{"id": "user_db", "kind": "db", "description": "User Database"}]
        }
        synthesis_result = {
            "trace": {
                "ir_tree": {
                    "logic_tree": [
                        {"id": "step_1"},
                        {"id": "step_2"},
                        {"id": "step_3"},
                        {"id": "step_4", "input_link": "step_2", "intent": "PERSIST"}
                    ]
                },
                "best_path": {
                    "statements": [
                        {"type": "raw", "code": "var users = QueryUsers();", "node_id": "step_1", "out_var": "users"},
                        {"type": "raw", "code": "var user1 = users.First();", "node_id": "step_2", "out_var": "user1"},
                        {"type": "raw", "code": "var report = BuildReport(user1);", "node_id": "step_3", "out_var": "report"},
                        {"type": "raw", "code": "File.WriteAllText(path, report);", "node_id": "step_4", "intent": "PERSIST"}
                    ],
                    "type_to_vars": {
                        "IEnumerable<User>": [{"var_name": "users", "node_id": "step_1"}],
                        "User": [{"var_name": "user1", "node_id": "step_2"}],
                        "string": [{"var_name": "report", "node_id": "step_3"}]
                    }
                },
                "blueprint": {}
            }
        }
        issues = SpecAuditor().audit(spec, synthesis_result)
        self.assertTrue(any(i.startswith("SPEC_INPUT_LINK_UNUSED") for i in issues))

    def test_input_refs_auto_node_satisfies_ref(self):
        spec = {
            "module_name": "AutoNodeRefs",
            "purpose": "auto node ref",
            "inputs": [],
            "outputs": [{"type_format": "void"}],
            "steps": [
                {"id": "step_1", "kind": "ACTION", "intent": "FETCH", "target_entity": "Order", "input_refs": [], "output_type": "string", "side_effect": "NONE", "text": "取得"},
                {"id": "step_2", "kind": "ACTION", "intent": "TRANSFORM", "target_entity": "Order", "input_refs": ["step_1"], "output_type": "Order", "side_effect": "NONE", "text": "変換"}
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }
        synthesis_result = {
            "trace": {
                "ir_tree": {
                    "logic_tree": [
                        {"id": "step_1", "intent": "FETCH"},
                        {"id": "step_1_json", "intent": "JSON_DESERIALIZE"},
                        {"id": "step_2", "intent": "TRANSFORM"}
                    ]
                },
                "best_path": {
                    "statements": [
                        {"type": "raw", "code": "var order = File.ReadAllText(\"orders.json\");", "node_id": "step_1", "out_var": "order"},
                        {"type": "raw", "code": "var order1 = JsonSerializer.Deserialize<Order>(order);", "node_id": "step_1_json", "out_var": "order1"},
                        {"type": "raw", "code": "var total = order1.TotalAmount;", "node_id": "step_2", "intent": "TRANSFORM"}
                    ],
                    "type_to_vars": {
                        "string": [{"var_name": "order", "node_id": "step_1"}],
                        "Order": [{"var_name": "order1", "node_id": "step_1_json"}]
                    }
                },
                "blueprint": {}
            }
        }
        issues = SpecAuditor().audit(spec, synthesis_result)
        self.assertFalse(any(i.startswith("SPEC_INPUT_REF_UNUSED") for i in issues))

    def test_intent_coverage_detects_missing_intent(self):
        spec = {
            "module_name": "IntentCoverage",
            "purpose": "intent coverage",
            "inputs": [],
            "outputs": [{"type_format": "void"}],
            "steps": [
                {"id": "step_1", "kind": "ACTION", "intent": "LINQ", "target_entity": "User", "input_refs": [], "output_type": "IEnumerable<User>", "side_effect": "NONE", "text": "抽出"}
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }
        synthesis_result = {
            "trace": {
                "ir_tree": {
                    "logic_tree": [
                        {"id": "step_1", "intent": "LINQ"}
                    ]
                },
                "best_path": {
                    "statements": [
                        {"type": "raw", "code": "var users = source.Where(x => x.Active).ToList();", "node_id": "step_1"}
                    ],
                    "type_to_vars": {}
                },
                "blueprint": {}
            }
        }
        issues = SpecAuditor().audit(spec, synthesis_result)
        self.assertTrue(any(i.startswith("SPEC_INTENT_NOT_EMITTED") for i in issues))

    def test_intent_coverage_accepts_emitted_intent(self):
        spec = {
            "module_name": "IntentCoverageOk",
            "purpose": "intent coverage",
            "inputs": [],
            "outputs": [{"type_format": "void"}],
            "steps": [
                {"id": "step_1", "kind": "ACTION", "intent": "LINQ", "target_entity": "User", "input_refs": [], "output_type": "IEnumerable<User>", "side_effect": "NONE", "text": "抽出"}
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }
        synthesis_result = {
            "trace": {
                "ir_tree": {
                    "logic_tree": [
                        {"id": "step_1", "intent": "LINQ"}
                    ]
                },
                "best_path": {
                    "statements": [
                        {"type": "raw", "code": "var users = source.Where(x => x.Active).ToList();", "node_id": "step_1", "intent": "LINQ"}
                    ],
                    "type_to_vars": {}
                },
                "blueprint": {}
            }
        }
        issues = SpecAuditor().audit(spec, synthesis_result)
        self.assertFalse(any(i.startswith("SPEC_INTENT_NOT_EMITTED") for i in issues))

    def test_input_refs_unused_detection(self):
        spec = {
            "module_name": "InputRefsUsage",
            "purpose": "input_refs usage",
            "inputs": [],
            "outputs": [{"type_format": "void"}],
            "steps": [
                {"id": "step_1", "kind": "ACTION", "intent": "FETCH", "target_entity": "User", "input_refs": [], "output_type": "IEnumerable<User>", "side_effect": "NONE", "text": "取得"},
                {"id": "step_2", "kind": "ACTION", "intent": "LINQ", "target_entity": "User", "input_refs": ["step_1"], "output_type": "IEnumerable<User>", "side_effect": "NONE", "text": "抽出"}
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }
        synthesis_result = {
            "trace": {
                "ir_tree": {
                    "logic_tree": [
                        {"id": "step_1", "intent": "FETCH"},
                        {"id": "step_2", "intent": "LINQ"}
                    ]
                },
                "best_path": {
                    "statements": [
                        {"type": "raw", "code": "var users = GetUsers();", "node_id": "step_1", "out_var": "users"},
                        {"type": "raw", "code": "var filtered = source.Where(x => x.Active).ToList();", "node_id": "step_2", "intent": "LINQ"}
                    ],
                    "type_to_vars": {
                        "IEnumerable<User>": [{"var_name": "users", "node_id": "step_1"}]
                    }
                },
                "blueprint": {}
            }
        }
        issues = SpecAuditor().audit(spec, synthesis_result)
        self.assertTrue(any(i.startswith("SPEC_INPUT_REF_UNUSED") for i in issues))

    def test_input_refs_self_reference_is_ignored(self):
        spec = {
            "module_name": "InputRefsSelf",
            "purpose": "self ref ignored",
            "inputs": [],
            "outputs": [{"type_format": "void"}],
            "steps": [
                {"id": "step_1", "kind": "ACTION", "intent": "FETCH", "target_entity": "User", "input_refs": [], "output_type": "IEnumerable<User>", "side_effect": "NONE", "text": "取得"},
                {"id": "step_2", "kind": "ACTION", "intent": "TRANSFORM", "target_entity": "User", "input_refs": ["step_2"], "output_type": "void", "side_effect": "NONE", "text": "変換"}
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }
        synthesis_result = {
            "trace": {
                "ir_tree": {
                    "logic_tree": [
                        {"id": "step_1", "intent": "FETCH"},
                        {"id": "step_2", "intent": "TRANSFORM"}
                    ]
                },
                "best_path": {
                    "statements": [
                        {"type": "raw", "code": "var users = GetUsers();", "node_id": "step_1", "out_var": "users"},
                        {"type": "raw", "code": "var result = Transform(users);", "node_id": "step_2", "intent": "TRANSFORM"}
                    ],
                    "type_to_vars": {
                        "IEnumerable<User>": [{"var_name": "users", "node_id": "step_1"}]
                    }
                },
                "blueprint": {}
            }
        }
        issues = SpecAuditor().audit(spec, synthesis_result)
        self.assertFalse(any(i.startswith("SPEC_INPUT_REF_UNUSED") for i in issues))

    def test_input_refs_notification_display_is_ignored(self):
        spec = {
            "module_name": "InputRefsNotify",
            "purpose": "notification ignores input_refs",
            "inputs": [],
            "outputs": [{"type_format": "void"}],
            "steps": [
                {"id": "step_1", "kind": "ACTION", "intent": "FETCH", "target_entity": "Order", "input_refs": [], "output_type": "IEnumerable<Order>", "side_effect": "NONE", "text": "取得"},
                {"id": "step_2", "kind": "ACTION", "intent": "DISPLAY", "target_entity": "Order", "input_refs": ["step_1"], "output_type": "void", "side_effect": "NONE", "text": "通知"}
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }
        synthesis_result = {
            "trace": {
                "ir_tree": {
                    "logic_tree": [
                        {"id": "step_1", "intent": "FETCH"},
                        {"id": "step_2", "intent": "DISPLAY"}
                    ]
                },
                "best_path": {
                    "statements": [
                        {"type": "raw", "code": "var orders = GetOrders();", "node_id": "step_1", "out_var": "orders"},
                        {"type": "raw", "code": "Console.WriteLine(\"done\");", "node_id": "step_2", "intent": "DISPLAY", "semantic_role": "notification"}
                    ],
                    "type_to_vars": {
                        "IEnumerable<Order>": [{"var_name": "orders", "node_id": "step_1"}]
                    }
                },
                "blueprint": {}
            }
        }
        issues = SpecAuditor().audit(spec, synthesis_result)
        self.assertFalse(any(i.startswith("SPEC_INPUT_REF_UNUSED") for i in issues))

    def test_input_refs_downstream_usage_is_allowed(self):
        spec = {
            "module_name": "InputRefsDownstream",
            "purpose": "downstream use allowed",
            "inputs": [],
            "outputs": [{"type_format": "void"}],
            "steps": [
                {"id": "step_1", "kind": "ACTION", "intent": "FETCH", "target_entity": "Config", "input_refs": [], "output_type": "string", "side_effect": "NONE", "text": "取得"},
                {"id": "step_2", "kind": "ACTION", "intent": "FETCH", "target_entity": "Config", "input_refs": ["step_1"], "output_type": "string", "side_effect": "NONE", "text": "取得"},
                {"id": "step_3", "kind": "ACTION", "intent": "TRANSFORM", "target_entity": "Config", "input_refs": ["step_1", "step_2"], "output_type": "string", "side_effect": "NONE", "text": "整形"}
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }
        synthesis_result = {
            "trace": {
                "ir_tree": {
                    "logic_tree": [
                        {"id": "step_1", "intent": "FETCH"},
                        {"id": "step_2", "intent": "FETCH"},
                        {"id": "step_3", "intent": "TRANSFORM"}
                    ]
                },
                "best_path": {
                    "statements": [
                        {"type": "raw", "code": "var mode = ReadMode();", "node_id": "step_1", "out_var": "mode"},
                        {"type": "raw", "code": "var region = ReadRegion();", "node_id": "step_2", "out_var": "region"},
                        {"type": "raw", "code": "var formatted = $\"{mode}-{region}\";", "node_id": "step_3", "intent": "TRANSFORM"}
                    ],
                    "type_to_vars": {
                        "string": [{"var_name": "mode", "node_id": "step_1"}, {"var_name": "region", "node_id": "step_2"}]
                    }
                },
                "blueprint": {}
            }
        }
        issues = SpecAuditor().audit(spec, synthesis_result)
        self.assertFalse(any(i.startswith("SPEC_INPUT_REF_UNUSED") for i in issues))

    def test_input_link_loop_accumulator_usage_is_allowed(self):
        spec = {
            "module_name": "InputLinkAccumulator",
            "purpose": "loop accumulator use",
            "inputs": [],
            "outputs": [{"type_format": "void"}],
            "steps": [
                {"id": "step_1", "kind": "ACTION", "intent": "FETCH", "target_entity": "Row", "input_refs": [], "output_type": "IEnumerable<Row>", "side_effect": "NONE", "text": "取得"},
                {"id": "step_2", "kind": "LOOP", "intent": "GENERAL", "target_entity": "Row", "input_refs": ["step_1"], "output_type": "void", "side_effect": "NONE", "text": "繰り返す"},
                {"id": "step_3", "kind": "ACTION", "intent": "CALC", "target_entity": "Row", "input_refs": ["step_2"], "output_type": "decimal", "side_effect": "NONE", "text": "集計"},
                {"id": "step_4", "kind": "ACTION", "intent": "TRANSFORM", "target_entity": "Row", "input_refs": ["step_2"], "output_type": "string", "side_effect": "NONE", "text": "CSV変換"}
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
                        {"id": "step_2"},
                        {"id": "step_3"},
                        {"id": "step_4", "input_link": "step_2", "intent": "TRANSFORM"}
                    ]
                },
                "best_path": {
                    "statements": [
                        {"type": "raw", "code": "var rows = GetRows();", "node_id": "step_1", "out_var": "rows"},
                        {"type": "foreach", "source": "rows", "item_name": "row", "body": [], "node_id": "step_2"},
                        {"type": "raw", "code": "totals[row.Id] += row.Value;", "node_id": "step_3", "intent": "CALC"},
                        {"type": "raw", "code": "var csv = BuildCsv(totals);", "node_id": "step_4", "intent": "TRANSFORM"}
                    ],
                    "type_to_vars": {
                        "IEnumerable<Row>": [{"var_name": "rows", "node_id": "step_1"}],
                        "Row": [{"var_name": "row", "node_id": "step_2"}],
                        "Dictionary<int, decimal>": [{"var_name": "totals", "node_id": "step_3", "role": "accumulator"}]
                    }
                },
                "blueprint": {}
            }
        }
        issues = SpecAuditor().audit(spec, synthesis_result)
        self.assertFalse(any(i.startswith("SPEC_INPUT_LINK_UNUSED") for i in issues))

    def test_loop_inner_input_link_uses_parent(self):
        spec = {
            "module_name": "LoopInnerLink",
            "purpose": "inner node uses parent loop",
            "inputs": [],
            "outputs": [{"type_format": "void"}],
            "steps": [
                {"id": "step_1", "kind": "ACTION", "intent": "FETCH", "target_entity": "Order", "input_refs": [], "output_type": "IEnumerable<Order>", "side_effect": "NONE", "text": "取得"},
                {"id": "step_2", "kind": "LOOP", "intent": "GENERAL", "target_entity": "Order", "input_refs": ["step_1"], "output_type": "void", "side_effect": "NONE", "text": "繰り返す"},
                {"id": "step_3", "kind": "ACTION", "intent": "PERSIST", "target_entity": "Order", "input_refs": ["step_2"], "output_type": "void", "side_effect": "DB", "text": "保存"}
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
                        {"id": "step_3_inner", "input_link": "step_2", "intent": "PERSIST"}
                    ]
                },
                "best_path": {
                    "statements": [
                        {"type": "raw", "code": "var orders = new List<Order>();", "node_id": "step_1", "out_var": "orders"},
                        {"type": "foreach", "source": "orders", "item_name": "order", "body": [], "node_id": "step_2"},
                        {"type": "raw", "code": "db.Save(order);", "node_id": "step_3_inner", "intent": "PERSIST"}
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


if __name__ == "__main__":
    unittest.main()
