# -*- coding: utf-8 -*-
import unittest

from src.code_synthesis.semantic_binder import SemanticBinder
from src.code_synthesis.type_system import TypeSystem


class TestSemanticBinderLogic(unittest.TestCase):
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
