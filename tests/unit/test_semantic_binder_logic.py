# -*- coding: utf-8 -*-
import unittest

from src.code_synthesis.semantic_binder import SemanticBinder
from src.code_synthesis.type_system import TypeSystem


class TestSemanticBinderLogic(unittest.TestCase):
    def test_exists_check_uses_file_exists(self):
        binder = SemanticBinder(TypeSystem())
        semantic_map = {
            "spec_role": "CHECK",
            "check_kind": "exists_check",
            "check_subject": "config.json",
            "expected_truth": True,
            "source_ref": "config.json",
            "source_kind": "file",
            "logic": []
        }
        path = {
            "type_to_vars": {},
            "poco_defs": {},
            "last_literal_map": {},
            "all_usings": set()
        }
        expr = binder.generate_logic_expression(semantic_map, "string", path, node={"intent": "EXISTS"})
        self.assertEqual(expr, "File.Exists(\"config.json\")")
        self.assertIn("System.IO", path["all_usings"])

    def test_null_check_uses_null_comparison(self):
        binder = SemanticBinder(TypeSystem())
        semantic_map = {
            "spec_role": "CHECK",
            "check_kind": "null_check",
            "check_subject": "user",
            "expected_truth": False,
            "logic": []
        }
        path = {
            "type_to_vars": {},
            "poco_defs": {},
            "last_literal_map": {}
        }
        expr = binder.generate_logic_expression(semantic_map, "User", path, node={"intent": "EXISTS"})
        self.assertEqual(expr, "user == null")

    def test_comparison_check_uses_ir_metadata(self):
        binder = SemanticBinder(TypeSystem())
        semantic_map = {
            "spec_role": "CHECK",
            "check_kind": "comparison_check",
            "check_subject": "Points",
            "check_operator": ">",
            "check_value": "100",
            "expected_truth": True,
            "logic": []
        }
        path = {
            "type_to_vars": {},
            "poco_defs": {"User": {"Points": "int"}},
            "active_scope_item": "x",
            "in_loop": True,
            "last_literal_map": {}
        }
        expr = binder.generate_logic_expression(semantic_map, "User", path, node={"id": "step_check"})
        self.assertEqual(expr, "x.Points > 100")

    def test_comparison_check_resolves_property_even_when_target_entity_is_item(self):
        binder = SemanticBinder(TypeSystem())
        semantic_map = {
            "spec_role": "CHECK",
            "check_kind": "comparison_check",
            "check_subject": "Points",
            "check_operator": ">",
            "check_value": "100",
            "expected_truth": True,
            "logic": []
        }
        path = {
            "type_to_vars": {},
            "poco_defs": {"User": {"Points": "int", "Name": "string"}},
            "active_scope_item": "x",
            "in_loop": True,
            "last_literal_map": {}
        }
        expr = binder.generate_logic_expression(semantic_map, "Item", path, node={"id": "step_check"})
        self.assertEqual(expr, "x.Points > 100")

    def test_comparison_check_with_default_subject_resolution_stays_generic(self):
        binder = SemanticBinder(TypeSystem())
        semantic_map = {
            "spec_role": "CHECK",
            "check_kind": "comparison_check",
            "check_subject": "Points",
            "subject_resolution": "default_subject",
            "check_operator": ">",
            "check_value": "100",
            "expected_truth": True,
            "logic": []
        }
        path = {
            "type_to_vars": {},
            "poco_defs": {"User": {"Points": "int", "Name": "string"}},
            "active_scope_item": "x",
            "in_loop": True,
            "last_literal_map": {}
        }
        expr = binder.generate_logic_expression(semantic_map, "Item", path, node={"id": "step_check"})
        self.assertEqual(expr, "Points > 100")

    def test_comparison_check_with_history_subject_uses_exact_target_scope_only(self):
        binder = SemanticBinder(TypeSystem())
        semantic_map = {
            "spec_role": "CHECK",
            "check_kind": "comparison_check",
            "check_subject": "Points",
            "subject_resolution": "history_subject",
            "check_operator": ">",
            "check_value": "100",
            "expected_truth": True,
            "logic": []
        }
        path = {
            "type_to_vars": {},
            "poco_defs": {"User": {"Points": "int"}, "Order": {"Total": "decimal"}},
            "active_scope_item": "x",
            "in_loop": True,
            "last_literal_map": {}
        }
        expr = binder.generate_logic_expression(semantic_map, "User", path, node={"id": "step_check"})
        self.assertEqual(expr, "x.Points > 100")

    def test_numeric_input_does_not_use_startswith(self):
        binder = SemanticBinder(TypeSystem())
        semantic_map = {
            "logic": [{
                "type": "numeric",
                "operator": "Greater",
                "expected_value": "{input}",
                "variable_hint": "Points"
            }]
        }
        path = {
            "type_to_vars": {
                "int": [{"var_name": "input_1", "role": "input", "node_id": "input"}]
            },
            "poco_defs": {"User": {"Points": "int"}},
            "active_scope_item": "x",
            "in_loop": True
        }
        expr = binder.generate_logic_expression(semantic_map, "User", path, node={"id": "step_2"})
        self.assertIn("x.Points > input_1", expr)
        self.assertNotIn("StartsWith", expr)

    def test_sql_param_role_binds_input_variable(self):
        binder = SemanticBinder(TypeSystem())
        method = {
            "class": "Dapper.SqlMapper",
            "name": "QueryAsync",
            "params": [
                {"name": "sql", "type": "string", "role": "sql"},
                {"name": "param", "type": "object", "role": "param"}
            ]
        }
        node = {
            "intent": "DATABASE_QUERY",
            "original_text": "ユーザーを取得する",
            "semantic_map": {"semantic_roles": {"sql": "SELECT * FROM Users WHERE Id = @userId"}}
        }
        path = {
            "type_to_vars": {"int": [{"var_name": "input_1", "role": "input", "node_id": "input"}]},
            "last_literal_map": {},
            "poco_defs": {}
        }
        params = binder.bind_parameters(method, node, path)
        self.assertIsNotNone(params)
        self.assertEqual(params[0], "\"SELECT * FROM Users WHERE Id = @userId\"")
        self.assertEqual(params[1], "new { userId = input_1 }")


if __name__ == "__main__":
    unittest.main()
