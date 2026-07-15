# -*- coding: utf-8 -*-
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.validate import validate_real_vector_model


class TestRealVectorModelValidation(unittest.TestCase):
    def test_missing_assets_returns_documented_exit_code(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = MagicMock(vector_model_path=str(Path(temp_dir) / "model.txt"))
            with patch.object(validate_real_vector_model, "ConfigManager", return_value=config), \
                 patch.object(sys, "argv", ["validate_real_vector_model.py"]):
                result = validate_real_vector_model.main()

        self.assertEqual(result, 2)

    def test_module_timeout_is_reported_as_timeout_status(self):
        with patch.object(
            validate_real_vector_model.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("python", 1),
        ):
            result = validate_real_vector_model._run_module("tests.example", 1)

        self.assertEqual(result["status"], "timeout")
        self.assertIsNone(result["return_code"])


if __name__ == "__main__":
    unittest.main()
