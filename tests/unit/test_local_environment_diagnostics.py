# -*- coding: utf-8 -*-
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.validate.diagnose_local_environment import CORE_CONFIG_FILES, diagnose


class TestLocalEnvironmentDiagnostics(unittest.TestCase):
    def _workspace(self) -> tempfile.TemporaryDirectory[str]:
        workspace = tempfile.TemporaryDirectory()
        root = Path(workspace.name)
        for relative_path in CORE_CONFIG_FILES:
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
        (root / "global.json").write_text(json.dumps({"sdk": {"version": "10.0.109"}}), encoding="utf-8")
        project = root / "tools" / "csharp" / "CodeBuilder" / "CodeBuilder.csproj"
        project.parent.mkdir(parents=True, exist_ok=True)
        project.write_text("<Project />", encoding="utf-8")
        return workspace

    @patch("scripts.validate.diagnose_local_environment.shutil.which", return_value="dotnet")
    def test_generation_is_ready_without_optional_local_assets(self, _which):
        with self._workspace() as directory:
            report = diagnose(
                Path(directory),
                command_runner=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "10.0.109\n", ""),
                package_version=lambda package: "test-version",
            )

        self.assertTrue(report["capabilities"]["design_generation"])
        self.assertFalse(report["capabilities"]["semantic_pipeline"])
        vector_check = next(check for check in report["checks"] if check["name"] == "semantic_vector_model")
        self.assertEqual("optional_missing", vector_check["status"])

    @patch("scripts.validate.diagnose_local_environment.shutil.which", return_value=None)
    def test_missing_dotnet_blocks_design_generation(self, _which):
        with self._workspace() as directory:
            report = diagnose(Path(directory), package_version=lambda package: "test-version")

        self.assertFalse(report["capabilities"]["design_generation"])
        dotnet_check = next(check for check in report["checks"] if check["name"] == "dotnet_sdk")
        self.assertEqual("blocked", dotnet_check["status"])

    @patch("scripts.validate.diagnose_local_environment.shutil.which", return_value="dotnet")
    def test_invalid_configuration_blocks_design_generation(self, _which):
        with self._workspace() as directory:
            root = Path(directory)
            (root / "config" / "config.json").write_text("not-json", encoding="utf-8")
            report = diagnose(
                root,
                command_runner=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "10.0.109\n", ""),
                package_version=lambda package: "test-version",
            )

        self.assertFalse(report["capabilities"]["design_generation"])
        configuration_check = next(check for check in report["checks"] if check["name"] == "configuration")
        self.assertEqual("blocked", configuration_check["status"])

    @patch("scripts.validate.diagnose_local_environment.shutil.which", return_value="dotnet")
    def test_vector_assets_enable_semantic_capabilities(self, _which):
        with self._workspace() as directory:
            root = Path(directory)
            model = root / "resources" / "vectors" / "chive-1.3-mc90.txt"
            model.parent.mkdir(parents=True, exist_ok=True)
            for path in (model, Path(f"{model}.v0.vocab.npy"), Path(f"{model}.v0.matrix.npy")):
                path.write_bytes(b"asset")
            vector_db = model.parent / "vector_db"
            vector_db.mkdir()
            (vector_db / "method_store_meta.json").write_text("{}", encoding="utf-8")
            (vector_db / "method_store_vectors.npy").write_bytes(b"asset")
            report = diagnose(
                root,
                command_runner=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "10.0.109\n", ""),
                package_version=lambda package: "test-version",
            )

        self.assertTrue(report["capabilities"]["semantic_pipeline"])
        self.assertTrue(report["capabilities"]["semantic_method_search"])


if __name__ == "__main__":
    unittest.main()
