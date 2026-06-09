import unittest
from unittest.mock import MagicMock

from src.tdd_operations.tdd_operations import TDDOperations


class TestTDDOperationsDialogueMetadata(unittest.TestCase):
    def setUp(self):
        self.mock_executor = MagicMock()
        self.mock_executor.workspace_root = "C:\\workspace\\NLP"
        self.mock_executor._get_entity_value.side_effect = lambda value, default=None: value if value is not None else default
        self.mock_executor.log_manager = MagicMock()
        self.ops = TDDOperations(self.mock_executor)

    def test_execute_goal_driven_tdd_sets_dialogue_metadata(self):
        self.mock_executor.advanced_tdd_support.execute_goal_driven_tdd.return_value = {
            "status": "success",
            "tdd_cycle_results": {
                "total_iterations": 3,
                "success_rate": 1.0,
                "total_time_seconds": 0.0,
            },
            "generated_artifacts": {
                "code": ["class A {}", "class B {}"],
                "tests": ["test A"],
            },
            "quality_metrics": {
                "estimated_coverage": 85,
                "cyclomatic_complexity": 2,
                "technical_debt": "low",
            },
        }
        context = {
            "plan": {
                "parameters": {
                    "goal_description": "注文割引ロジックを実装",
                    "acceptance_criteria": ["割引率を計算できること"],
                }
            }
        }

        result = self.ops.execute_goal_driven_tdd(context)

        self.assertEqual(result["action_result"]["status"], "success")
        metadata = result["action_result"]["dialogue_metadata"]
        self.assertEqual(metadata["phase"], "goal_driven_tdd")
        self.assertEqual(metadata["goal_description"], "注文割引ロジックを実装")
        self.assertEqual(metadata["generated_code_count"], 2)
        self.assertEqual(metadata["generated_test_count"], 1)
        self.assertEqual(metadata["next_action"], "review_generated_artifacts")

    def test_analyze_test_failure_sets_dialogue_metadata(self):
        self.mock_executor._get_entity_value.side_effect = lambda value, default=None: value if value is not None else default
        self.mock_executor.advanced_tdd_support.analyze_and_fix_test_failure.return_value = {
            "status": "success",
            "analysis": {
                "status": "success",
                "error_type": "assertion_failure",
                "root_cause": "method_returns_default_value",
                "analysis_summary": {
                    "target_file": "C:\\workspace\\NLP\\src\\Calculator.cs",
                    "root_cause": "method_returns_default_value"
                }
            },
            "fix_suggestions": [
                {
                    "id": "heal_1",
                    "description": "return 0 を修正",
                    "safety_score": 0.95,
                    "auto_applicable": True,
                    "target_file": "C:\\workspace\\NLP\\src\\Calculator.cs",
                    "conversation_hint": "CalculatorTests.Add_ShouldReturnSum の失敗に対して method_returns_default_value を修正する提案",
                    "reason": "method_returns_default_value により Add の修正が必要です。",
                    "recommended_action": "apply_code_fix",
                    "target_summary": "CalculatorTests.Add_ShouldReturnSum / Add"
                }
            ],
        }
        context = {
            "action_result": {
                "test_summary": {
                    "error_details": [
                        {
                            "method": "Example.Tests.CalculatorTests.Add_ShouldReturnSum",
                            "file": "C:\\workspace\\NLP\\src\\Calculator.cs",
                            "line": 10,
                            "message": "Expected: 5, Actual: 0",
                            "stack_trace": "stack",
                        }
                    ]
                }
            },
            "plan": {"parameters": {}},
            "history": [],
        }

        result = self.ops.analyze_test_failure(context)

        self.assertEqual(result["action_result"]["status"], "success")
        metadata = result["action_result"]["dialogue_metadata"]
        self.assertEqual(metadata["phase"], "failure_analysis")
        self.assertEqual(metadata["failure_count"], 1)
        self.assertEqual(metadata["suggestion_count"], 1)
        self.assertEqual(metadata["primary_target_file"], "src\\Calculator.cs")
        self.assertIn("method_returns_default_value", metadata["primary_reason"])
        self.assertEqual(metadata["primary_recommended_action"], "apply_code_fix")
        self.assertIn("Add", metadata["primary_target_summary"])
        self.assertEqual(metadata["next_action"], "apply_code_fix")


if __name__ == "__main__":
    unittest.main()
