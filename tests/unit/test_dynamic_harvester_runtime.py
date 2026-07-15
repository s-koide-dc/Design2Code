import os
import subprocess
import unittest
from unittest.mock import patch

from src.code_synthesis.dynamic_harvester import DynamicHarvester


class TestDynamicHarvesterRuntime(unittest.TestCase):
    def setUp(self):
        self.harvester = DynamicHarvester()

    def test_rejects_type_name_that_could_modify_inspector_source(self):
        with patch("subprocess.run") as run:
            with self.assertLogs(self.harvester.logger, level="WARNING") as captured:
                result = self.harvester.harvest_from_type(
                    'System.String"; Console.WriteLine("injected")'
                )

        self.assertEqual([], result)
        run.assert_not_called()
        self.assertIn("Rejected unsupported reflection type name", "\n".join(captured.output))

    def test_uses_structured_json_output_and_removes_temporary_project(self):
        captured_directory = None

        def run_inspector(*args, **kwargs):
            nonlocal captured_directory
            captured_directory = kwargs["cwd"]
            self.assertTrue(os.path.exists(os.path.join(
                captured_directory,
                "Inspector.csproj",
            )))
            self.assertTrue(os.path.exists(os.path.join(
                captured_directory,
                "Program.cs",
            )))
            return subprocess.CompletedProcess(
                args=args[0],
                returncode=0,
                stdout=(
                    "Build succeeded.\n"
                    '[{"Name":"Abs","ReturnType":"int",'
                    '"Parameters":[{"Name":"value","Type":"int"}]}]\n'
                ),
                stderr="",
            )

        with patch("subprocess.run", side_effect=run_inspector):
            result = self.harvester.harvest_from_type("System.Math")

        self.assertIsNotNone(captured_directory)
        self.assertFalse(os.path.exists(captured_directory))
        self.assertEqual("Abs", result[0]["name"])
        self.assertEqual("System.Math.Abs({value})", result[0]["code"])

    def test_timeout_is_reported_as_an_operational_failure(self):
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("dotnet", 30),
        ):
            with self.assertLogs(
                self.harvester.logger,
                level="ERROR",
            ) as captured:
                result = self.harvester.harvest_from_type("System.Math")

        self.assertEqual([], result)
        self.assertTrue(any(
            "timed out" in message
            for message in captured.output
        ))
