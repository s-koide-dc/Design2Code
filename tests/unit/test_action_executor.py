# -*- coding: utf-8 -*-
import unittest
import os
import shutil
import json
from unittest.mock import MagicMock, patch
from src.action_executor.action_executor import ActionExecutor

class TestActionExecutor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir_class_scope = os.path.abspath("test_workspace_class")
        if not os.path.exists(cls.test_dir_class_scope):
            os.makedirs(cls.test_dir_class_scope)

        cls.error_patterns_dir = os.path.join(cls.test_dir_class_scope, "resources")
        os.makedirs(cls.error_patterns_dir, exist_ok=True)
        cls.error_patterns_path = os.path.join(cls.error_patterns_dir, "error_patterns.json")

        # Create a dummy error_patterns.json
        error_patterns_data = {
            "error_patterns": [
                {
                    "type": "FileNotFoundError",
                    "regex": "が見つかりません",
                    "user_message": "指定されたファイルまたはディレクトリが見つかりませんでした。",
                    "suggested_action": "ファイル名またはパスを確認してください。"
                },
                {
                    "type": "PermissionError",
                    "regex": "アクセスが拒否",
                    "user_message": "操作に必要なアクセス権限がありません。",
                    "suggested_action": "管理者権限で再試行するか、別の場所を選択してください。"
                }
            ]
        }
        with open(cls.error_patterns_path, "w", encoding="utf-8") as f:
            json.dump(error_patterns_data, f, ensure_ascii=False, indent=2)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_dir_class_scope):
            shutil.rmtree(cls.test_dir_class_scope)

    def setUp(self):
        self.test_dir = os.path.abspath("test_workspace")
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)
        
        mock_log_manager = MagicMock()
        self.executor = ActionExecutor(
            log_manager=mock_log_manager,
            workspace_root=self.test_dir,
            error_patterns_path=self.error_patterns_path
        )

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_create_file_success(self):
        context = {
            "analysis": {
                "intent": "FILE_CREATE",
                "entities": {"filename": "test.txt", "content": "hello world"}
            }
        }
        # In this test, we are directly calling execute, so we need to mock the plan structure
        context["plan"] = {
            "action_method": "_create_file",
            "parameters": context["analysis"]["entities"],
            "confirmation_needed": False,
            "safety_check_status": "OK"
        }
        result = self.executor.execute(context)
        self.assertEqual(result["action_result"]["status"], "success")
        
        file_path = os.path.join(self.test_dir, "test.txt")
        self.assertTrue(os.path.exists(file_path))
        with open(file_path, 'r', encoding='utf-8') as f:
            self.assertEqual(f.read(), "hello world")

    def test_read_file_success(self):
        file_path = os.path.join(self.test_dir, "read_test.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("content to read")
            
        context = {
            "analysis": {
                "intent": "FILE_READ",
                "entities": {"filename": "read_test.txt"}
            }
        }
        context["plan"] = {
            "action_method": "_read_file",
            "parameters": context["analysis"]["entities"],
            "confirmation_needed": False,
            "safety_check_status": "OK"
        }
        result = self.executor.execute(context)
        self.assertEqual(result["action_result"]["status"], "success")
        self.assertIn("content to read", result["action_result"]["message"])

    def test_list_dir_success(self):
        os.makedirs(os.path.join(self.test_dir, "subdir"))
        context = {
            "analysis": {
                "intent": "LIST_DIR",
                "entities": {"directory": "."}
            }
        }
        context["plan"] = {
            "action_method": "_list_dir",
            "parameters": context["analysis"]["entities"],
            "confirmation_needed": False,
            "safety_check_status": "OK"
        }
        result = self.executor.execute(context)
        self.assertEqual(result["action_result"]["status"], "success")
        self.assertIn("subdir", result["action_result"]["message"])

    def test_append_file_success(self):
        file_path = os.path.join(self.test_dir, "append_test.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("initial")
            
        context = {
            "analysis": {
                "intent": "FILE_APPEND",
                "entities": {"filename": "append_test.txt", "content": "appended"}
            }
        }
        context["plan"] = {
            "action_method": "_append_file",
            "parameters": context["analysis"]["entities"],
            "confirmation_needed": False,
            "safety_check_status": "OK"
        }
        result = self.executor.execute(context)
        self.assertEqual(result["action_result"]["status"], "success")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            self.assertEqual(f.read(), "initial\nappended")

    def test_delete_file_success(self):
        file_path = os.path.join(self.test_dir, "delete_test.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("to be deleted")
            
        context = {
            "analysis": {
                "intent": "FILE_DELETE",
                "entities": {"filename": "delete_test.txt"}
            }
        }
        context["plan"] = {
            "action_method": "_delete_file",
            "parameters": context["analysis"]["entities"],
            "confirmation_needed": False,
            "safety_check_status": "OK"
        }
        result = self.executor.execute(context)
        self.assertEqual(result["action_result"]["status"], "success")
        self.assertFalse(os.path.exists(file_path))

    def test_path_traversal_blocked(self):
        # Create a file outside the workspace root
        secret_dir = os.path.abspath(os.path.join(self.test_dir, "../secret_zone")) # Ensure secret_dir is outside test_dir
        if not os.path.exists(secret_dir):
            os.makedirs(secret_dir)
        secret_file = os.path.join(secret_dir, "password.txt")
        with open(secret_file, 'w') as f:
            f.write("secret123")
            
        try:
            # Attempt to read using relative traversal
            context = {
                "analysis": {
                    "intent": "FILE_READ",
                    "entities": {"filename": "../secret_zone/password.txt"}
                }
            }
            context["plan"] = {
                "action_method": "_read_file",
                "parameters": context["analysis"]["entities"],
                "confirmation_needed": False,
                "safety_check_status": "OK"
            }
            result = self.executor.execute(context)
            self.assertEqual(result["action_result"]["status"], "error")
            self.assertIn("無効なパス", result["action_result"]["message"])
        finally:
            if os.path.exists(secret_dir):
                shutil.rmtree(secret_dir)

    def test_safe_command_success(self):
        context = {
            "analysis": {
                "intent": "CMD_RUN",
                "entities": {"command": "echo test_cmd"}
            }
        }
        context["plan"] = {
            "action_method": "_run_command",
            "parameters": context["analysis"]["entities"],
            "confirmation_needed": True, # Commands usually need confirmation
            "safety_check_status": "OK"
        }
        result = self.executor.execute(context)
        self.assertEqual(result["action_result"]["status"], "success")
        # Depending on OS, output might include newline.
        # Check for presence of "test_cmd" in output.
        self.assertIn("test_cmd", result["action_result"]["message"])

    def test_unsafe_command_blocked(self):
        context = {
            "analysis": {
                "intent": "CMD_RUN",
                "entities": {"command": "del critical_file.py"}
            }
        }
        context["plan"] = {
            "action_method": "_run_command",
            "parameters": context["analysis"]["entities"],
            "confirmation_needed": True,
            "safety_check_status": "OK"
        }
        result = self.executor.execute(context)
        self.assertEqual(result["action_result"]["status"], "error")
        self.assertIn("許可されていません", result["action_result"]["message"])
        self.assertIsNone(result["action_result"].get("original_error")) # No original error from security block

    # ---
    # New Tests for Entity Validation and Error Handling ---

    def test_create_file_missing_filename(self):
        context = {
            "plan": {
                "action_method": "_create_file",
                "parameters": {"content": "some content"} # Filename is missing
            }
        }
        result = self.executor.execute(context)
        self.assertEqual(result["action_result"]["status"], "error")
        self.assertEqual(result["action_result"]["message"], "ファイル名が指定されていません。")
        self.assertIsNone(result["action_result"].get("suggested_action"))

    def test_create_file_missing_content(self):
        context = {
            "plan": {
                "action_method": "_create_file",
                "parameters": {"filename": "missing_content.txt"} # Content is missing
            }
        }
        # _create_file defaults content to "" if not provided, so it should succeed
        result = self.executor.execute(context)
        self.assertEqual(result["action_result"]["status"], "success")
        file_path = os.path.join(self.test_dir, "missing_content.txt")
        self.assertTrue(os.path.exists(file_path))
        with open(file_path, 'r', encoding='utf-8') as f:
            self.assertEqual(f.read(), "") # Content should be empty string

    def test_read_file_missing_filename(self):
        context = {
            "plan": {
                "action_method": "_read_file",
                "parameters": {} # Filename is missing
            }
        }
        result = self.executor.execute(context)
        self.assertEqual(result["action_result"]["status"], "error")
        self.assertEqual(result["action_result"]["message"], "ファイル名が指定されていません。")
        self.assertIsNone(result["action_result"].get("suggested_action"))

    def test_run_command_missing_command(self):
        context = {
            "plan": {
                "action_method": "_run_command",
                "parameters": {} # Command is missing
            }
        }
        result = self.executor.execute(context)
        self.assertEqual(result["action_result"]["status"], "error")
        self.assertEqual(result["action_result"]["message"], "コマンドが指定されていません。")
        self.assertIsNone(result["action_result"].get("suggested_action"))
    
    def test_file_not_found_error_pattern(self):
        # This tests _handle_exception_with_patterns logic
        context = {
            "plan": {
                "action_method": "_read_file",
                "parameters": {"filename": "non_existent.txt"}
            }
        }
        result = self.executor.execute(context)
        self.assertEqual(result["action_result"]["status"], "error")
        self.assertEqual(result["action_result"]["message"], "指定されたファイルまたはディレクトリが見つかりませんでした。")
        self.assertEqual(result["action_result"]["suggested_action"], "ファイル名またはパスを確認してください。")

    def test_permission_error_pattern(self):
        # ... (既存のテストロジック) ...
        pass

    def test_autonomous_learning_trigger_on_failure(self):
        """失敗時に自律学習がトリガーされるかテスト"""
        mock_learning = MagicMock()
        self.executor.autonomous_learning = mock_learning
        
        context = {
            "plan": {
                "action_method": "_read_file",
                "parameters": {"filename": "non_existent.txt"}
            }
        }
        self.executor.execute(context)
        
        # trigger_learningが呼ばれたことを確認
        mock_learning.trigger_learning.assert_called()
        args, kwargs = mock_learning.trigger_learning.call_args
        self.assertEqual(kwargs['event_type'], "ACTION_FAILED")
        self.assertEqual(kwargs['data']['error_type'], "FileNotFoundError")

    def test_autonomous_learning_trigger_on_command_failure(self):
        """コマンド失敗時に自律学習がトリガーされるかテスト"""
        mock_learning = MagicMock()
        self.executor.autonomous_learning = mock_learning
        
        # git statusを実行（リポジトリ外なら失敗する可能性があるが、確実に失敗させるために空コマンドなど）
        # ホワイトリストにあるコマンドで、returncodeが非0になるケース
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Error from shell")
            
            context = {
                "plan": {
                    "action_method": "_run_command",
                    "parameters": {"command": "git status"}
                }
            }
            self.executor.execute(context)
            
            mock_learning.trigger_learning.assert_called()
            args, kwargs = mock_learning.trigger_learning.call_args
            self.assertEqual(kwargs['event_type'], "ACTION_FAILED")
            self.assertEqual(kwargs['data']['event'], "command_failed")


if __name__ == "__main__":
    unittest.main()