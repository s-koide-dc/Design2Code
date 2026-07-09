import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

from scripts.tools.rotate_logs import rotate_logs
from src.pipeline_core.pipeline_core import Pipeline


class TestLogRotation(unittest.TestCase):
    def test_archives_only_expired_matching_logs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = datetime(2026, 7, 6, 12, 0, 0)
            old_log = root / "pipeline_20260601.log"
            old_json = root / "pipeline_20260601.json"
            current_log = root / "pipeline_20260706.log"
            unrelated = root / "application_20260601.log"
            for path in (old_log, old_json, current_log, unrelated):
                path.write_text(path.name, encoding="utf-8")

            old_timestamp = (now - timedelta(days=8)).timestamp()
            current_timestamp = now.timestamp()
            os.utime(old_log, (old_timestamp, old_timestamp))
            os.utime(old_json, (old_timestamp, old_timestamp))
            os.utime(unrelated, (old_timestamp, old_timestamp))
            os.utime(current_log, (current_timestamp, current_timestamp))

            result = rotate_logs(root, "pipeline", 7, now=now)

            self.assertEqual("success", result["status"])
            self.assertEqual(
                ["pipeline_20260601.json", "pipeline_20260601.log"],
                result["archived_files"],
            )
            self.assertFalse(old_log.exists())
            self.assertFalse(old_json.exists())
            self.assertTrue(current_log.exists())
            self.assertTrue(unrelated.exists())
            with ZipFile(result["archive_path"]) as archive:
                self.assertEqual(
                    ["pipeline_20260601.json", "pipeline_20260601.log"],
                    sorted(archive.namelist()),
                )

    def test_missing_log_directory_is_a_successful_no_op(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"

            result = rotate_logs(missing)

            self.assertEqual([], result["archived_files"])
            self.assertIsNone(result["archive_path"])

    def test_rejects_invalid_retention(self):
        with self.assertRaises(ValueError):
            rotate_logs(retention_days=-1)

    def test_pipeline_records_operational_rotation_failure(self):
        pipeline = Pipeline.__new__(Pipeline)
        pipeline.log_manager = MagicMock()
        pipeline.log_manager.log_dir = "logs"
        pipeline.log_manager.log_file_prefix = "pipeline"

        with patch(
            "scripts.tools.rotate_logs.rotate_logs",
            side_effect=PermissionError("denied"),
        ):
            pipeline._rotate_expired_logs()

        pipeline.log_manager.log_event.assert_called_once_with(
            "log_rotation_error",
            {
                "error_type": "PermissionError",
                "message": "denied",
            },
            level="WARNING",
        )

    def test_pipeline_does_not_hide_programming_failure(self):
        pipeline = Pipeline.__new__(Pipeline)
        pipeline.log_manager = MagicMock()
        pipeline.log_manager.log_dir = "logs"
        pipeline.log_manager.log_file_prefix = "pipeline"

        with patch(
            "scripts.tools.rotate_logs.rotate_logs",
            side_effect=RuntimeError("invalid implementation state"),
        ):
            with self.assertRaises(RuntimeError):
                pipeline._rotate_expired_logs()
