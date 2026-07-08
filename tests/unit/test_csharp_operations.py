import os
import json
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.csharp_operations.csharp_operations import CSharpOperations


class TestCSharpOperations(unittest.TestCase):
    def test_analysis_fingerprint_changes_with_source_content(self):
        with tempfile.TemporaryDirectory() as workspace:
            project_dir = os.path.join(workspace, "project")
            analyzer_dir = os.path.join(workspace, "analyzer")
            os.makedirs(project_dir)
            os.makedirs(analyzer_dir)
            project_path = os.path.join(project_dir, "Sample.csproj")
            source_path = os.path.join(project_dir, "Sample.cs")
            analyzer_path = os.path.join(analyzer_dir, "Analyzer.csproj")
            for path, content in (
                (project_path, "<Project />"),
                (source_path, "class Sample {}"),
                (analyzer_path, "<Project />"),
            ):
                with open(path, "w", encoding="utf-8") as output:
                    output.write(content)
            operations = CSharpOperations(MagicMock())
            initial = operations._analysis_fingerprint(
                project_path,
                analyzer_path,
            )
            with open(source_path, "w", encoding="utf-8") as output:
                output.write("class Sample { int Value { get; set; } }")

            changed = operations._analysis_fingerprint(
                project_path,
                analyzer_path,
            )

            self.assertNotEqual(initial, changed)

    @patch("src.csharp_operations.csharp_operations.subprocess.run")
    def test_analyze_csharp_reuses_complete_content_cache(self, mock_run):
        with tempfile.TemporaryDirectory() as workspace:
            project_path = os.path.join(workspace, "Sample.csproj")
            source_path = os.path.join(workspace, "Sample.cs")
            with open(project_path, "w", encoding="utf-8") as output:
                output.write("<Project />")
            with open(source_path, "w", encoding="utf-8") as output:
                output.write("class Sample {}")

            executor = MagicMock()
            executor.workspace_root = workspace
            executor._get_entity_value.return_value = project_path
            executor._safe_join.return_value = project_path
            operations = CSharpOperations(executor)
            analyzer_project = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "..",
                    "tools",
                    "csharp",
                    "MyRoslynAnalyzer",
                    "MyRoslynAnalyzer.csproj",
                )
            )
            fingerprint = operations._analysis_fingerprint(
                project_path,
                analyzer_project,
            )
            cache_dir = os.path.join(
                workspace,
                "logs",
                "analysis_output",
                f"analysis_{fingerprint[:24]}",
            )
            details_dir = os.path.join(cache_dir, "details")
            os.makedirs(details_dir)
            with open(
                os.path.join(cache_dir, "manifest.json"),
                "w",
                encoding="utf-8",
            ) as output:
                json.dump({"objects": []}, output)

            result = operations.analyze_csharp(
                {"analysis": {"entities": {}}},
                {"filename": project_path},
            )

            mock_run.assert_not_called()
            self.assertTrue(result["action_result"]["cache_hit"])

    @patch("src.csharp_operations.csharp_operations.subprocess.run")
    def test_analyze_csharp_atomically_publishes_completed_analysis(
        self,
        mock_run,
    ):
        with tempfile.TemporaryDirectory() as workspace:
            project_path = os.path.join(workspace, "Sample.csproj")
            source_path = os.path.join(workspace, "Sample.cs")
            with open(project_path, "w", encoding="utf-8") as output:
                output.write("<Project />")
            with open(source_path, "w", encoding="utf-8") as output:
                output.write("class Sample {}")

            def create_analyzer_output(command, **kwargs):
                work_dir = command[-1]
                os.makedirs(os.path.join(work_dir, "details"))
                with open(
                    os.path.join(work_dir, "manifest.json"),
                    "w",
                    encoding="utf-8",
                ) as output:
                    json.dump({"objects": []}, output)
                return subprocess.CompletedProcess(command, 0, "", "")

            mock_run.side_effect = create_analyzer_output
            executor = MagicMock()
            executor.workspace_root = workspace
            executor._get_entity_value.return_value = project_path
            executor._safe_join.return_value = project_path

            result = CSharpOperations(executor).analyze_csharp(
                {"analysis": {"entities": {}}},
                {"filename": project_path},
            )

            output_path = result["action_result"]["output_path"]
            self.assertTrue(os.path.basename(output_path).startswith("analysis_"))
            self.assertFalse(
                any(
                    name.startswith(".analysis-work-")
                    for name in os.listdir(
                        os.path.join(workspace, "logs", "analysis_output")
                    )
                )
            )

    @patch("src.csharp_operations.csharp_operations.subprocess.run")
    def test_dotnet_test_uses_argument_list_and_captures_log(self, mock_run):
        with tempfile.TemporaryDirectory() as workspace:
            project_path = os.path.join(workspace, "Sample.csproj")
            action_executor = MagicMock()
            action_executor.workspace_root = workspace
            action_executor._get_entity_value.return_value = project_path
            action_executor._safe_join.return_value = project_path
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess(
                    [], 0, "Total: 1 Passed: 1 Failed: 0", ""
                ),
            ]

            result = CSharpOperations(action_executor).run_dotnet_test(
                {}, {"project_path": project_path}
            )

            test_call = mock_run.call_args_list[2]
            self.assertEqual(
                test_call.args[0],
                ["dotnet", "test", project_path, "--no-build"],
            )
            self.assertNotIn("shell", test_call.kwargs)
            self.assertEqual(result["action_result"]["status"], "success")
            log_path = os.path.join(workspace, "logs", "last_dotnet_test.log")
            with open(log_path, encoding="utf-8") as log:
                self.assertIn("Total: 1", log.read())

    @patch("src.csharp_operations.csharp_operations.subprocess.run")
    def test_dotnet_test_build_failure_returns_structured_errors(self, mock_run):
        with tempfile.TemporaryDirectory() as workspace:
            project_path = os.path.join(workspace, "Sample.csproj")
            source_path = os.path.join(workspace, "Sample.cs")
            action_executor = MagicMock()
            action_executor.workspace_root = workspace
            action_executor._get_entity_value.return_value = project_path
            action_executor._safe_join.return_value = project_path
            build_error = (
                f"{source_path}(17,34): error CS1026: ) expected"
            )
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess([], 1, "", build_error),
            ]

            result = CSharpOperations(action_executor).run_dotnet_test(
                {}, {"project_path": project_path}
            )

            action_result = result["action_result"]
            self.assertEqual("error", action_result["status"])
            self.assertTrue(action_result["build_failed"])
            self.assertIn(build_error, action_result["raw_output"])
            self.assertEqual(
                [{
                    "file": source_path,
                    "line": 17,
                    "code": "CS1026",
                    "message": ") expected",
                    "raw_line": build_error,
                }],
                action_result["build_errors"],
            )
