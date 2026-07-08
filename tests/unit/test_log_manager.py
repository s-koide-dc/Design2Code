import unittest
import os
import json
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.log_manager.log_manager import LogManager

class TestLogManager(unittest.TestCase):
    def setUp(self):
        self.test_log_dir = "test_logs_temp"
        self.log_manager = LogManager(log_dir=self.test_log_dir, log_level="DEBUG")
        
    def tearDown(self):
        if os.path.exists(self.test_log_dir):
            shutil.rmtree(self.test_log_dir)

    def test_init_creates_log_dir(self):
        self.assertTrue(os.path.exists(self.test_log_dir))

    def test_log_event_pipeline_stage_completion(self):
        event_data = {"stage": "intent_detection", "intent": "FILE_CREATE", "confidence": 0.95}
        self.log_manager.log_event("pipeline_stage_completion", event_data, level="INFO")

        with open(self.log_manager.log_file_path, 'r', encoding='utf-8') as f:
            text_log_content = f.read()
            self.assertIn("intent_detection", text_log_content)
            self.assertIn("FILE_CREATE", text_log_content)
        
        with open(self.log_manager.json_log_file_path, 'r', encoding='utf-8') as f:
            json_log_content = f.read()
            self.assertIn('"event_type": "pipeline_stage_completion"', json_log_content)
            self.assertIn('"intent": "FILE_CREATE"', json_log_content)

    def test_log_event_action_execution_success(self):
        event_data = {"action": "_create_file", "filename": "test.txt", "status": "success"}
        self.log_manager.log_event("action_execution", event_data, level="INFO")

        with open(self.log_manager.log_file_path, 'r', encoding='utf-8') as f:
            text_log_content = f.read()
            self.assertIn("action_execution", text_log_content)
            self.assertIn("success", text_log_content)
        
        with open(self.log_manager.json_log_file_path, 'r', encoding='utf-8') as f:
            json_log_content = f.read()
            self.assertIn('"action": "_create_file"', json_log_content)
            self.assertIn('"status": "success"', json_log_content)

    def test_log_event_action_execution_error_and_summary(self):
        event_data = {
            "action": "_create_file", "filename": "non_existent_dir/test.txt", "status": "error",
            "message": "指定されたファイルが見つかりません。ファイル名を確認してください。",
            "original_error": "[Errno 2] No such file or directory: 'non_existent_dir/test.txt'",
            "suggested_action": "ファイル名またはパスを修正して再試行してください。",
            "original_text": "ファイルを作って"
        }
        self.log_manager.log_event("action_execution", event_data, level="ERROR")

        with open(self.log_manager.log_file_path, 'r', encoding='utf-8') as f:
            text_log_content = f.read()
            self.assertIn("action_execution", text_log_content)
            self.assertIn("ERROR", text_log_content)
        
        with open(self.log_manager.json_log_file_path, 'r', encoding='utf-8') as f:
            json_log_content = f.read()
            self.assertIn('"status": "error"', json_log_content)
            self.assertIn('"original_error": "[Errno 2] No such file or directory', json_log_content)

        # Check error summary file
        with open(self.log_manager.error_summary_file_path, 'r', encoding='utf-8') as f:
            error_summary_content = json.load(f)
            self.assertEqual(len(error_summary_content), 1)
            self.assertEqual(error_summary_content[0]["action"], "_create_file")
            self.assertIn("No such file or directory", error_summary_content[0]["original_error"])

    def test_log_level_filtering(self):
        lm_info_level = LogManager(log_dir=self.test_log_dir, log_file_prefix="info_filter", log_level="INFO")
        lm_info_level.log_event("debug_event", {"data": "debug data"}, level="DEBUG")
        lm_info_level.log_event("info_event", {"data": "info data"}, level="INFO")

        with open(lm_info_level.log_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertNotIn("debug_event", content)
            self.assertIn("info_event", content)

    def test_json_log_is_json_lines_and_can_be_read(self):
        self.log_manager.log_event("first", {"value": 1})
        self.log_manager.log_event("second", {"value": 2})

        with open(
            self.log_manager.json_log_file_path,
            encoding="utf-8",
        ) as log_file:
            records = [
                json.loads(line)
                for line in log_file.read().splitlines()
            ]

        self.assertEqual(["first", "second"], [
            record["event_type"] for record in records
        ])
        events = self.log_manager.get_events_after(
            datetime.now() - timedelta(minutes=1)
        )
        self.assertEqual(["first", "second"], [
            event["event_type"] for event in events
        ])

    def test_reader_supports_legacy_records_and_skips_malformed_lines(self):
        timestamp = datetime.now().isoformat()
        legacy_records = [
            json.dumps({
                "timestamp": timestamp,
                "event_type": "valid_before",
                "data": {},
            }) + ",",
            "{invalid",
            json.dumps({
                "timestamp": timestamp,
                "event_type": "valid_after",
                "data": {},
            }) + ",",
        ]
        with open(
            self.log_manager.json_log_file_path,
            "w",
            encoding="utf-8",
        ) as log_file:
            log_file.write("\n".join(legacy_records))

        with self.assertLogs(
            self.log_manager.logger,
            level="WARNING",
        ) as captured:
            events = self.log_manager.get_events_after(
                datetime.now() - timedelta(minutes=1)
            )

        self.assertEqual(["valid_before", "valid_after"], [
            event["event_type"] for event in events
        ])
        self.assertTrue(any(
            "line 2" in message
            for message in captured.output
        ))

if __name__ == '__main__':
    unittest.main()
