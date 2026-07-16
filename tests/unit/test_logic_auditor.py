# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock

from src.utils.logic_auditor import LogicAuditor


class TestLogicAuditor(unittest.TestCase):
    def test_structured_audit_matches_step_ids_without_vector_scoring(self):
        vector_engine = MagicMock()
        auditor = LogicAuditor(vector_engine=vector_engine)
        design = {
            "steps": [
                {"id": "step_1", "intent": "FETCH"},
                {"id": "step_2", "intent": "RETURN"},
            ]
        }
        source_structure = {
            "implemented_steps": [
                {"id": "step_1", "symbol_id": "M:Example.Fetch"},
                {"id": "step_2", "symbol_id": "M:Example.Run"},
            ]
        }

        result = auditor.audit(design, source_structure, "unrelated text")

        self.assertEqual(result["status"], "consistent")
        self.assertIsNone(result["consistency_score"])
        self.assertEqual(result["coverage"]["missing_step_count"], 0)
        vector_engine.vector_similarity.assert_not_called()

    def test_structured_audit_reports_exact_missing_and_unexpected_ids(self):
        auditor = LogicAuditor()
        result = auditor.audit(
            {
                "steps": [
                    {"id": "step_1"},
                    {"id": "step_2"},
                ]
            },
            {
                "implemented_steps": [
                    {"id": "step_1"},
                    {"id": "step_3"},
                ]
            },
        )

        self.assertEqual(result["status"], "inconsistent")
        self.assertEqual(
            [(finding["type"], finding["step_id"]) for finding in result["findings"]],
            [("missing_step", "step_2"), ("unexpected_step", "step_3")],
        )

    def test_structured_audit_is_indeterminate_without_step_contract(self):
        auditor = LogicAuditor()

        result = auditor.audit(
            {"specification": {"core_logic": ["Do something"]}},
            {"files_analyzed": 1},
            "def run(): pass",
        )

        self.assertEqual(result["status"], "indeterminate")
        self.assertIsNone(result["consistency_score"])

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

    def test_same_step_multiple_assertions_are_not_ordered(self):
        auditor = LogicAuditor()
        goals = [
            {"type": "numeric", "operator": "GreaterEqual", "expected_value": "1", "original_step": "影響件数が1以上ならtrue、0ならfalse"},
            {"type": "numeric", "operator": "Equal", "expected_value": "0", "original_step": "影響件数が1以上ならtrue、0ならfalse"},
        ]
        code = "if (rows == 0) return false; if (rows >= 1) return true;"
        findings = auditor.verify_logic_goals(goals, code)
        self.assertFalse(any(f.get("reason") == "order_mismatch" for f in findings))


if __name__ == "__main__":
    unittest.main()
