# -*- coding: utf-8 -*-
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.validate import run_local_semantic_quality_gate


class TestLocalSemanticQualityGate(unittest.TestCase):
    def test_module_timeout_is_recorded(self):
        with patch.object(
            run_local_semantic_quality_gate.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("python", 1),
        ):
            result = run_local_semantic_quality_gate._run_module("tests.example", 1)

        self.assertEqual("timeout", result["status"])
        self.assertIsNone(result["return_code"])

    def test_report_is_written_atomically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.json"
            run_local_semantic_quality_gate._write_report(output, {"status": "passed"})

            self.assertEqual({"status": "passed"}, json.loads(output.read_text(encoding="utf-8")))
            self.assertFalse(output.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
