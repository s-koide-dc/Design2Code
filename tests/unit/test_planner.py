import unittest
import json
import shutil
from unittest.mock import MagicMock, patch
import os

# Assuming Planner is in src.planner.planner
# ActionExecutor is in src.action_executor.action_executor
from src.planner.planner import Planner
from src.action_executor.action_executor import ActionExecutor

# Mock the LogManager as it's not the focus of this unit test
mock_log_manager = MagicMock()

class TestPlanner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a dummy retry_rules.json for testing
        cls.test_resources_dir = "test_resources"
        os.makedirs(cls.test_resources_dir, exist_ok=True)
        cls.retry_rules_path = os.path.join(cls.test_resources_dir, "retry_rules.json")
        with open(cls.retry_rules_path, "w", encoding="utf-8") as f:
            json.dump({
                "retry_rules": [
                    {
                        "error_type": "FileNotFoundError",
                        "condition": "filename is similar to existing files",
                        "suggestion": "ファイルが見つかりません。再試行しますか？",
                        "alternative_action": "LIST_DIR"
                    }
                ]
            }, f, ensure_ascii=False, indent=2)
        
        # Patch os.path.exists and open for retry rules loading
        # Store original os.path.exists and open
        cls.original_os_path_exists = os.path.exists
        cls.original_builtins_open = open

        cls.patcher_exists = patch('src.planner.planner.os.path.exists', side_effect=cls._mock_os_path_exists)
        cls.mock_exists = cls.patcher_exists.start()
        cls.patcher_open = patch('builtins.open', side_effect=cls._mock_builtins_open)
        cls.mock_open = cls.patcher_open.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher_exists.stop()
        cls.patcher_open.stop()
        if os.path.exists(cls.test_resources_dir):
            shutil.rmtree(cls.test_resources_dir) # Use shutil.rmtree for robust cleanup

    @staticmethod
    def _mock_os_path_exists(path):
        if path == TestPlanner.retry_rules_path:
            return True
        # Call the original os.path.exists
        return TestPlanner.original_os_path_exists(path)

    @staticmethod
    def _mock_builtins_open(file, mode='r', encoding=None):
        if file == TestPlanner.retry_rules_path:
            return TestPlanner.original_builtins_open(file, mode, encoding='utf-8')
        # Call the original builtins.open
        return TestPlanner.original_builtins_open(file, mode, encoding=encoding)

    def setUp(self):
        self.mock_action_executor = MagicMock(spec=ActionExecutor)
        self.mock_action_executor.get_required_entities_for_intent.side_effect = \
            lambda intent: {
                "FILE_CREATE": ["filename", "content"],
                "FILE_READ": ["filename"],
                "FILE_APPEND": ["filename", "content"],
                "FILE_DELETE": ["filename"],
                "LIST_DIR": [],
                "CMD_RUN": ["command"]
            }.get(intent, [])
        self.mock_action_executor.safe_commands = ["git", "ls", "dir", "echo"]
        
        self.planner = Planner(
            action_executor=self.mock_action_executor,
            log_manager=mock_log_manager,
            intent_entity_thresholds={"intent": 0.7, "entity": 0.7},
            retry_rules_path=self.retry_rules_path
        )

    def test_successful_file_create_plan(self):
        context = {
            "original_text": "hello.txt を作って。内容は「Hello World」で。",
            "analysis": {
                "intent": "FILE_CREATE",
                "intent_confidence": 0.9,
                "entities": {
                    "filename": {"value": "hello.txt", "confidence": 0.95},
                    "content": {"value": "Hello World", "confidence": 0.95}
                }
            }
        }
        result = self.planner.create_plan(context)
        self.assertIn("plan", result)
        self.assertEqual(result["plan"]["action_method"], "_create_file")
        self.assertEqual(result["plan"]["parameters"]["filename"], "hello.txt")
        self.assertEqual(result["plan"]["confirmation_needed"], False)
        self.assertEqual(result["plan"]["safety_check_status"], "OK")
        self.assertFalse("errors" in result and result["errors"])

    def test_low_intent_confidence_plan_creation(self):
        context = {
            "original_text": "曖昧な指示",
            "analysis": {"intent": "AMBIGUOUS_ACTION", "intent_confidence": 0.6},
        }
        result = self.planner.create_plan(context)
        self.assertIn("errors", result)
        self.assertIn("意図の信頼度が低すぎます", result["errors"][0]["message"])
        self.assertFalse("plan" in result)

    def test_missing_required_entity_plan_creation(self):
        context = {
            "original_text": "ファイルを作って",
            "analysis": {
                "intent": "FILE_CREATE", "intent_confidence": 0.9,
                "entities": {"filename": {"value": "new.txt", "confidence": 0.9}} # Content is missing
            },
        }
        result = self.planner.create_plan(context)
        self.assertIn("errors", result)
        self.assertIn("必須エンティティが不足しています: content", result["errors"][0]["message"])
        self.assertFalse("plan" in result)

    def test_low_entity_confidence_plan_creation(self):
        context = {
            "original_text": "ファイル A を編集",
            "analysis": {
                "intent": "FILE_APPEND", "intent_confidence": 0.9,
                "entities": {"filename": {"value": "file A", "confidence": 0.6}, "content": {"value": "add", "confidence": 0.9}}
            },
        }
        result = self.planner.create_plan(context)
        self.assertIn("errors", result)
        self.assertIn("信頼度が低いエンティティがあります: filename", result["errors"][0]["message"])
        self.assertFalse("plan" in result)

    def test_cmd_run_needs_confirmation(self):
        context = {
            "original_text": "「ls」を実行",
            "analysis": {
                "intent": "CMD_RUN", "intent_confidence": 0.95,
                "entities": {"command": {"value": "ls", "confidence": 0.95}}
            },
        }
        result = self.planner.create_plan(context)
        self.assertIn("plan", result)
        self.assertEqual(result["plan"]["action_method"], "_run_command")
        self.assertTrue(result["plan"]["confirmation_needed"])
        self.assertFalse("errors" in result and result["errors"])

    def test_retry_logic_file_not_found(self):
        original_text = "ファイルが見つからない"
        context = {
            "original_text": original_text,
            "analysis": {"intent": "FILE_READ", "intent_confidence": 0.9},
            "history": [
                {
                    "analysis": {"intent": "FILE_READ"},
                    "action_result": {
                        "status": "error",
                        "original_error_type": "FileNotFoundError"
                    }
                }
            ],
            "action_result": {
                "status": "error",
                "original_error_type": "FileNotFoundError",
                "message": "指定されたファイルが見つかりません。"
            }
        }
        result = self.planner.create_plan(context)
        self.assertIn("plan", result)
        self.assertTrue(result["plan"]["retry_possible"])
        self.assertIn("以前の操作が失敗しました。再試行しますか？", result["plan"]["suggestion"])
        mock_log_manager.log_event.assert_called_with(
            "planner_retry_suggestion",
            {"context_summary": original_text, "previous_error": context["action_result"]},
            level="INFO"
        )
        self.assertFalse("errors" in result and result["errors"])

    def test_compound_subtask_planning(self):
        # Mocking a compound task with an active subtask
        context = {
            "session_id": "compound_planner_session",
            "analysis": {
                "intent": "BACKUP_AND_DELETE", # Parent intent, but subtask should be planned
                "intent_confidence": 0.9,
                "entities": {} # No new entities in this turn
            },
            "task": {
                "id": "compound_task_123",
                "name": "BACKUP_AND_DELETE",
                "type": "COMPOUND_TASK",
                "state": "IN_PROGRESS",
                "parameters": {
                    "source_filename": {"value": "original.txt", "confidence": 0.9},
                    "destination_filename": {"value": "backup.txt", "confidence": 0.9}
                },
                "subtasks": [
                    {
                        "name": "FILE_READ",
                        "state": "READY_FOR_EXECUTION", # The subtask is ready for execution
                        "parameters": {
                            "filename": {"value": "original.txt", "confidence": 0.9}
                        }
                    },
                    {
                        "name": "FILE_DELETE",
                        "state": "PENDING",
                        "parameters": {}
                    }
                ],
                "current_subtask_index": 0,
                "clarification_needed": False,
                "clarification_message": None
            }
        }
        
        # Ensure mock_action_executor returns required entities for FILE_READ
        self.mock_action_executor.get_required_entities_for_intent.side_effect = \
            lambda intent: {
                "FILE_CREATE": ["filename", "content"],
                "FILE_READ": ["filename"], # Required for FILE_READ
                "FILE_APPEND": ["filename", "content"],
                "FILE_DELETE": ["filename"],
                "LIST_DIR": [],
                "CMD_RUN": ["command"]
            }.get(intent, [])

        result = self.planner.create_plan(context)
        self.assertIn("plan", result)
        self.assertEqual(result["plan"]["action_method"], "_read_file")
        self.assertEqual(result["plan"]["parameters"]["filename"], "original.txt")
        self.assertEqual(result["plan"]["confirmation_needed"], False)
        self.assertEqual(result["plan"]["safety_check_status"], "OK")
        self.assertEqual(result["plan"]["parent_task"], "BACKUP_AND_DELETE") # Check parent task info
        self.assertFalse("errors" in result and result["errors"])

    def test_safety_policy_block(self):
        # Scenario: Trying to run a banned command
        context = {
            "original_text": "rm -rf / を実行",
            "analysis": {
                "intent": "CMD_RUN", 
                "intent_confidence": 0.95,
                "entities": {"command": {"value": "rm -rf /", "confidence": 0.95}}
            },
        }
        # Planner should consult SafetyPolicyValidator, which flags 'rm' as Blocked
        result = self.planner.create_plan(context)
        
        self.assertIn("plan", result)
        self.assertEqual(result["plan"]["safety_check_status"], "BLOCK")
        self.assertIn("許可されていません", result["plan"]["safety_message"])
        self.assertTrue(any("Safety Policy Error" in e["message"] for e in result.get("errors", [])))

if __name__ == '__main__':
    unittest.main()
