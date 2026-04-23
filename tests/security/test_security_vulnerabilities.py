# -*- coding: utf-8 -*-
import unittest
import os
import tempfile
import shutil
import time
from src.action_executor.action_executor import ActionExecutor
from src.log_manager.log_manager import LogManager

class TestSecurityVulnerabilities(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.log_manager = LogManager(log_dir=os.path.join(self.test_dir, "logs"))
        self.executor = ActionExecutor(self.log_manager, workspace_root=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_log_sanitization(self):
        """ログの秘匿化（マスク処理）の検証"""
        sensitive_data = {
            "filename": "super_secret_file.txt",
            "command": "git push --force origin main",
            "content": "API_KEY=1234567890abcdef",
            "api_token": "secret-token",
            "nested": {
                "filename": "nested_secret.py"
            }
        }
        
        # 直接サニタイズメソッドをテスト
        sanitized = self.log_manager.sanitize_log_data(sensitive_data)
        
        # 機密情報が伏せられていること
        self.assertEqual(sanitized["filename"], "***")
        self.assertEqual(sanitized["command"], "***")
        self.assertEqual(sanitized["content"], "***")
        self.assertEqual(sanitized["api_token"], "***")
        self.assertEqual(sanitized["nested"]["filename"], "***")
        
        # 元のデータが壊れていないこと（非機密フィールドがあれば）
        sensitive_data["public"] = "hello"
        sanitized_2 = self.log_manager.sanitize_log_data(sensitive_data)
        self.assertEqual(sanitized_2["public"], "hello")

    def test_redos_protection(self):
        """正規表現 ReDoS 対策の有効性検証"""
        from src.semantic_analyzer.semantic_analyzer import SemanticAnalyzer
        analyzer = SemanticAnalyzer(task_manager=None)
        
        # 極端に長い、悪意のある入力（ReDoSを誘発しやすいパターン）
        # もし対策がなければ、この解析に数秒〜数分かかる
        malicious_input = "「" + "あ" * 1000 + "」を" + "い" * 1000 + "にコピーして"
        
        start_time = time.time()
        # 内部メソッドを直接呼ぶ
        # 実際には chunks 等が必要だが、抽出ロジックのみをテスト
        history = []
        context = {"original_text": malicious_input}
        analyzer._extract_entities(malicious_input, history, context, "FILE_COPY")
        
        duration = time.time() - start_time
        # 過度に厳しい閾値は環境依存で不安定になるため、実用上の上限を設定
        max_duration_seconds = 0.5
        self.assertLess(duration, max_duration_seconds, f"Possible ReDoS detected! Duration: {duration:.4f}s")

    def test_path_traversal_simple(self):
        # Should not be able to access files outside test_dir
        secret_file = os.path.join(os.path.dirname(self.test_dir), "secret.txt")
        with open(secret_file, "w") as f:
            f.write("sensitive data")
        
        try:
            # Try to access using ..
            traversal_path = os.path.join("..", "secret.txt")
            result_path = self.executor._safe_join(traversal_path)
            self.assertIsNone(result_path, f"Should have blocked traversal path: {traversal_path}")
        finally:
            if os.path.exists(secret_file):
                os.remove(secret_file)

    def test_delete_requires_backup(self):
        target_file = os.path.join(self.test_dir, "target.txt")
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("data")
        rel_path = os.path.relpath(target_file, self.test_dir)
        context = {"plan": {"action_method": "_delete_file", "parameters": {"filename": rel_path}}}
        context = self.executor.execute(context)
        self.assertEqual(context["action_result"].get("status"), "success")
        backup_dir = os.path.join(self.test_dir, "backup")
        self.assertTrue(os.path.isdir(backup_dir))

    def test_path_traversal_absolute(self):
        # Should not be able to access absolute paths outside workspace
        if os.name == 'nt':
            absolute_path = "C:\\Windows\\System32\\drivers\\etc\\hosts"
        else:
            absolute_path = "/etc/passwd"
            
        result_path = self.executor._safe_join(absolute_path)
        self.assertIsNone(result_path, f"Should have blocked absolute path: {absolute_path}")

    def test_path_traversal_unc(self):
        if os.name != 'nt':
            return
        unc_path = "\\\\localhost\\C$\\Windows\\win.ini"
        result_path = self.executor._safe_join(unc_path)
        # On Windows, os.path.abspath("\\\\localhost\\C$\\Windows\\win.ini") is still the same UNC path.
        # os.path.join(workspace_abs, unc_path) might behave differently depending on how it's handled.
        self.assertIsNone(result_path, f"Should have blocked UNC path: {unc_path}")

    def test_command_injection_shell_metacharacters(self):
        # On Windows, 'echo' is in safe_commands. 
        # Check if we can chain commands.
        context = {"plan": {"action_method": "_run_command", "parameters": {"command": "echo hello & dir"}}}
        context = self.executor.execute(context)
        
        # If it executed 'dir', the message will contain directory listing
        # In a secure implementation, 'echo' should only echo.
        # However, currently _run_command just checks if the first part is in safe_commands.
        # "echo hello & dir" might be split by shlex into ["echo", "hello", "&", "dir"]
        # Then it's passed to cmd /c which WILL execute dir.
        
        # Should be blocked due to metacharacters in arguments
        self.assertEqual(context["action_result"].get("status"), "error")
        self.assertEqual(context["action_result"].get("message"), "コマンド引数に不正な文字が含まれています。")

    def test_confirmation_required_blocks_execution(self):
        context = {
            "plan": {
                "action_method": "_run_command",
                "parameters": {"command": "echo hello"},
                "confirmation_needed": True
            }
        }
        context = self.executor.execute(context)
        self.assertEqual(context["action_result"].get("status"), "error")
        self.assertEqual(context["action_result"].get("message"), "ユーザー承認が必要な操作です。")

    def test_read_command_outside_allowed_dirs(self):
        script_path = os.path.join(self.test_dir, "outside.txt")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write("secret")
        rel_path = os.path.relpath(script_path, self.test_dir)
        context = {"plan": {"action_method": "_run_command", "parameters": {"command": f"cat {rel_path}"}}}
        context = self.executor.execute(context)
        self.assertEqual(context["action_result"].get("status"), "error")
        self.assertEqual(context["action_result"].get("message"), "読み取り対象のパスが許可範囲外です。")

    def test_read_command_requires_path(self):
        context = {"plan": {"action_method": "_run_command", "parameters": {"command": "cat"}}}
        context = self.executor.execute(context)
        self.assertEqual(context["action_result"].get("status"), "error")
        self.assertEqual(context["action_result"].get("message"), "読み取り対象のパスが指定されていません。")

    def test_read_command_blocked_patterns(self):
        scripts_dir = os.path.join(self.test_dir, "scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        secret_path = os.path.join(scripts_dir, "secrets.txt")
        with open(secret_path, "w", encoding="utf-8") as f:
            f.write("secret")
        rel_path = os.path.relpath(secret_path, self.test_dir).replace("\\", "/")
        context = {"plan": {"action_method": "_run_command", "parameters": {"command": f"cat {rel_path}"}}}
        context = self.executor.execute(context)
        self.assertEqual(context["action_result"].get("status"), "error")
        self.assertEqual(context["action_result"].get("message"), "読み取り対象のパスが禁止されています。")

    def test_read_command_not_blocked_for_tokenizer(self):
        scripts_dir = os.path.join(self.test_dir, "scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        ok_path = os.path.join(scripts_dir, "tokenizer_config.txt")
        with open(ok_path, "w", encoding="utf-8") as f:
            f.write("ok")
        rel_path = os.path.relpath(ok_path, self.test_dir).replace("\\", "/")
        context = {"plan": {"action_method": "_run_command", "parameters": {"command": f"cat {rel_path}"}}}
        context = self.executor.execute(context)
        self.assertNotEqual(context["action_result"].get("message"), "読み取り対象のパスが禁止されています。")

    def test_unauthorized_subcommand(self):
        # 'git init' should be blocked
        context = {"plan": {"action_method": "_run_command", "parameters": {"command": "git init"}}}
        context = self.executor.execute(context)
        self.assertIn("サブコマンドが許可されていない", context["action_result"].get("message", ""))

    def test_disallowed_dotnet_run(self):
        context = {"plan": {"action_method": "_run_command", "parameters": {"command": "dotnet run"}}}
        context = self.executor.execute(context)
        self.assertIn("サブコマンドが許可されていない", context["action_result"].get("message", ""))

    def test_disallowed_python_option(self):
        context = {"plan": {"action_method": "_run_command", "parameters": {"command": "python -c \"print(1)\""}}}
        context = self.executor.execute(context)
        self.assertEqual(context["action_result"].get("status"), "error")
        self.assertEqual(context["action_result"].get("message"), "コマンド引数に禁止されたオプションが含まれています。")

    def test_python_script_outside_allowed_dir(self):
        script_path = os.path.join(self.test_dir, "not_scripts.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write("print('hello')")
        rel_path = os.path.relpath(script_path, self.test_dir)
        context = {"plan": {"action_method": "_run_command", "parameters": {"command": f"python {rel_path}"}}}
        context = self.executor.execute(context)
        self.assertEqual(context["action_result"].get("status"), "error")
        self.assertEqual(context["action_result"].get("message"), "python/py の実行は scripts 配下のスクリプトに限定されています。")

    def test_python_script_not_whitelisted(self):
        scripts_dir = os.path.join(self.test_dir, "scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        allowed_script = os.path.join(scripts_dir, "allowed.py")
        blocked_script = os.path.join(scripts_dir, "blocked.py")
        with open(allowed_script, "w", encoding="utf-8") as f:
            f.write("print('allowed')")
        with open(blocked_script, "w", encoding="utf-8") as f:
            f.write("print('blocked')")

        self.executor.python_allowed_dirs = ["scripts"]
        self.executor.python_allowed_scripts = ["scripts/allowed.py"]

        rel_blocked = os.path.relpath(blocked_script, self.test_dir).replace("\\", "/")
        context = {"plan": {"action_method": "_run_command", "parameters": {"command": f"python {rel_blocked}"}}}
        context = self.executor.execute(context)
        self.assertEqual(context["action_result"].get("status"), "error")
        self.assertEqual(context["action_result"].get("message"), "python/py の実行は許可されたスクリプトに限定されています。")

    def test_illegal_arguments(self):
        # Chaining with ;
        context = {"plan": {"action_method": "_run_command", "parameters": {"command": "ls ; rm -rf /"}}}
        context = self.executor.execute(context)
        self.assertIn("不正な文字が含まれています", context["action_result"].get("message", ""))

if __name__ == "__main__":
    unittest.main()
