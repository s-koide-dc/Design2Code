# -*- coding: utf-8 -*-
import unittest

from src.utils.logic_auditor import LogicAuditor


class TestLogicAuditor(unittest.TestCase):
    def test_input_placeholder_matches_resolved_input_var(self):
        auditor = LogicAuditor()
        goals = [{
            "type": "numeric",
            "operator": "Greater",
            "expected_value": "{input}",
            "original_step": "ポイントが入力値({input})より多いユーザーのみを抽出する"
        }]
        code = "var filtered = users.Where(x => x.Points > input_1).ToList();"
        findings = auditor.verify_logic_goals(goals, code)
        self.assertEqual(findings, [])

    def test_input_placeholder_requires_input_var_presence(self):
        auditor = LogicAuditor()
        goals = [{
            "type": "numeric",
            "operator": "Greater",
            "expected_value": "{input}",
            "original_step": "ポイントが入力値({input})より多いユーザーのみを抽出する"
        }]
        code = "var filtered = users.Where(x => x.Points > 100).ToList();"
        findings = auditor.verify_logic_goals(goals, code)
        self.assertTrue(any(f.get("reason") == "LOGIC_VALUE_MISMATCH" for f in findings))

    def test_numeric_goal_flags_string_op(self):
        auditor = LogicAuditor()
        goals = [{
            "type": "numeric",
            "operator": "Greater",
            "expected_value": "100",
            "original_step": "ポイントが100より多い"
        }]
        code = "var filtered = users.Where(x => x.Points.StartsWith(\"100\")).ToList();"
        findings = auditor.verify_logic_goals(goals, code)
        self.assertTrue(any(f.get("reason") == "LOGIC_OPERATOR_MISMATCH" for f in findings))

    def test_calculation_non_numeric_value_is_ignored(self):
        auditor = LogicAuditor()
        goals = [{
            "type": "calculation",
            "operator": "Add",
            "value": "総計に注文の合計金額を",
            "original_step": "総計に注文の合計金額を加算する"
        }]
        code = "total += order.TotalAmount;"
        findings = auditor.verify_logic_goals(goals, code)
        self.assertEqual(findings, [])

    def test_string_identifier_matches_unquoted_in_code(self):
        auditor = LogicAuditor()
        goals = [{
            "type": "string",
            "operator": "Equal",
            "expected_value": "Id",
            "original_step": "IDに一致するユーザーを検索する"
        }]
        code = "var user = _dbConnection.QueryAsync<User>(\"SELECT * FROM Users WHERE Id = @userId\", new { userId = input_1 });"
        findings = auditor.verify_logic_goals(goals, code)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
