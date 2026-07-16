# -*- coding: utf-8 -*-
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from src.code_verification.dependency_contract import InvalidDependencyError
from src.code_verification.sandbox_provisioner import SandboxProvisioner


class TestSandboxProvisioner(unittest.TestCase):
    def setUp(self):
        self.provisioner = SandboxProvisioner(config=object())
        self.addCleanup(self.provisioner.clean_up)

    @patch("src.code_verification.sandbox_provisioner.subprocess.run")
    def test_creates_unique_owned_directory_and_fixed_project_file(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")

        first_directory = self.provisioner.provision_sandbox("../untrusted", [])
        first_project = first_directory / "Sandbox.csproj"
        self.assertTrue(first_project.exists())
        self.assertNotIn("untrusted", str(first_project))

        second_directory = self.provisioner.provision_sandbox("another-name", [])

        self.assertNotEqual(first_directory, second_directory)
        self.assertFalse(first_directory.exists())
        self.assertTrue((second_directory / "Sandbox.csproj").exists())

    @patch("src.code_verification.sandbox_provisioner.subprocess.run")
    def test_uses_shared_dependency_contract_when_rendering_project_file(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")

        directory = self.provisioner.provision_sandbox(
            "ignored",
            [{"name": "Example.Package", "version": "1.2.3"}],
        )

        content = (directory / "Sandbox.csproj").read_text(encoding="utf-8")
        self.assertIn('Include="Example.Package" Version="1.2.3"', content)
        self.assertEqual(1, run.call_count)
        self.assertEqual(directory, Path(run.call_args.kwargs["cwd"]))

    @patch("src.code_verification.sandbox_provisioner.subprocess.run")
    def test_rejects_invalid_dependency_before_creating_or_restoring_project(self, run):
        with self.assertRaises(InvalidDependencyError):
            self.provisioner.provision_sandbox(
                "ignored",
                [{"name": 'Bad" Package', "version": "1.0.0"}],
            )

        self.assertIsNone(self.provisioner.temp_dir)
        run.assert_not_called()

    @patch("src.code_verification.sandbox_provisioner.subprocess.run")
    def test_cleanup_removes_only_owned_directory(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        directory = self.provisioner.provision_sandbox("ignored", [])

        self.provisioner.clean_up()

        self.assertFalse(directory.exists())
        self.assertIsNone(self.provisioner.temp_dir)


if __name__ == "__main__":
    unittest.main()
