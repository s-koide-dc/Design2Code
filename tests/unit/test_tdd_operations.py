import os
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.csharp_operations.csharp_operations import CSharpOperations
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

    def test_extract_build_error_details_without_regex(self):
        raw_output = (
            "C:\\workspace\\NLP\\src\\Example.cs(17,34): error CS1026: ) expected\n"
            "not a compiler error"
        )

        details = self.ops._extract_build_error_details(raw_output)

        self.assertEqual(1, len(details))
        self.assertEqual("C:\\workspace\\NLP\\src\\Example.cs", details[0]["file"])
        self.assertEqual(17, details[0]["line"])
        self.assertEqual("CS1026: ) expected", details[0]["message"])

    def test_parse_dotnet_test_result_without_regex(self):
        csharp_ops = CSharpOperations(self.mock_executor)
        output = """
[xUnit.net 00:00:03.13]     ProcessorTests.GetLength_ShouldReturnLength_WhenDataExists [FAIL]
Error Message:
System.NullReferenceException : Object reference not set to an instance of an object.
Stack Trace:
at MultiTurnRepro.Processor.GetLength(Int32 id) in C:\\workspace\\NLP\\tests\\repro_multi_turn\\Processor.cs:line 12
失敗!   -失敗:     1、合格:     0、スキップ:     0、合計:     1、期間: 1 s - Repro.dll (net10.0)
"""

        summary = csharp_ops.parse_dotnet_test_result(output)

        self.assertEqual(1, summary["failed_count"])
        self.assertEqual(1, summary["total_count"])
        self.assertEqual(0, summary["passed_count"])
        self.assertEqual(
            ["ProcessorTests.GetLength_ShouldReturnLength_WhenDataExists"],
            summary["failed_tests"],
        )
        detail = summary["error_details"][0]
        self.assertEqual("System.NullReferenceException", detail["exception_type"])
        self.assertEqual("missing_test_data", detail["root_cause"])
        self.assertIn("Processor.cs:line 12", detail["stack_trace"])

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

    def test_add_package_failure_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as workspace:
            project_path = os.path.join(workspace, "Sample.csproj")
            with open(project_path, "w", encoding="utf-8") as project:
                project.write("<Project />")
            executor = MagicMock()
            executor.workspace_root = workspace
            executor._get_entity_value.side_effect = (
                lambda value, default=None:
                value if value is not None else default
            )
            executor._safe_join.side_effect = (
                lambda value: os.path.join(workspace, value)
            )
            operations = TDDOperations(executor)
            context = {
                "plan": {"parameters": {"fix_id": "all"}},
                "history": [{
                    "action_result": {
                        "analysis_result": {
                            "fix_suggestions": [{
                                "id": "fix_package",
                                "type": "add_package",
                                "suggested_code": "Example.Package",
                                "target_file": "Generated.cs",
                                "auto_applicable": True,
                            }],
                        },
                    },
                }],
            }

            with patch(
                "src.tdd_operations.tdd_operations.subprocess.run",
                side_effect=subprocess.CalledProcessError(
                    1,
                    ["dotnet", "add", "package"],
                ),
            ):
                result = operations.apply_code_fix(context)

        self.assertEqual("error", result["action_result"]["status"])
        self.assertEqual(
            [{
                "package": "Example.Package",
                "error_type": "CalledProcessError",
            }],
            result["action_result"]["package_failures"],
        )

    def test_analyze_test_failure_does_not_depend_on_test_method_naming(self):
        project_analysis = {"manifest": {"objects": []}, "details_by_id": {}}
        self.mock_executor.advanced_tdd_support.analyze_and_fix_test_failure.return_value = {
            "status": "success",
            "analysis": {"status": "success"},
            "fix_suggestions": [],
        }
        context = {
            "action_result": {
                "test_summary": {
                    "error_details": [{
                        "method": "Example.Tests.CalculatorTests.ArbitraryName",
                        "file": "C:\\workspace\\NLP\\tests\\CalculatorTests.cs",
                        "line": 10,
                        "message": "Expected: 5, Actual: 0",
                        "stack_trace": "stack",
                    }]
                }
            },
            "plan": {"parameters": {}},
            "history": [],
        }

        with patch.object(
            self.ops,
            "_load_failure_project_analysis",
            return_value=project_analysis,
        ):
            self.ops.analyze_test_failure(context)

        failure_data = (
            self.mock_executor.advanced_tdd_support
            .analyze_and_fix_test_failure.call_args.args[0]
        )
        self.assertEqual(
            failure_data["test_method"],
            "Example.Tests.CalculatorTests.ArbitraryName",
        )
        self.assertEqual(failure_data["target_code"]["file"], "")
        self.assertIs(
            self.mock_executor.advanced_tdd_support
            .analyze_and_fix_test_failure.call_args.kwargs["roslyn_data"],
            project_analysis,
        )

    def test_behavioral_validation_rejects_failing_test_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = os.path.join(temp_dir, "Example.csproj")
            test_path = os.path.join(temp_dir, "ExampleTests.cs")
            for path in (project_path, test_path):
                with open(path, "w", encoding="utf-8"):
                    pass
            self.mock_executor.workspace_root = temp_dir

            completed = MagicMock(returncode=1, stdout="1 test failed", stderr="")
            with patch("src.tdd_operations.tdd_operations.subprocess.run", return_value=completed):
                result = self.ops._validate_test_fix_behavior([test_path])

        self.assertFalse(result["valid"])
        self.assertIn("1 test failed", result["error"])

    def test_behavioral_validation_accepts_successful_test_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = os.path.join(temp_dir, "Example.csproj")
            test_path = os.path.join(temp_dir, "ExampleTests.cs")
            for path in (project_path, test_path):
                with open(path, "w", encoding="utf-8"):
                    pass
            self.mock_executor.workspace_root = temp_dir

            completed = MagicMock(returncode=0, stdout="", stderr="")
            with patch("src.tdd_operations.tdd_operations.subprocess.run", return_value=completed):
                result = self.ops._validate_test_fix_behavior([test_path])

        self.assertTrue(result["valid"])


if __name__ == "__main__":
    unittest.main()
