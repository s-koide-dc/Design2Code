import unittest
import os
import shutil
import tempfile
import threading
import time
from src.context_manager.context_manager import ContextManager
from src.task_manager.task_manager import TaskManager
from src.action_executor.action_executor import ActionExecutor

from src.context_manager.context_manager import ContextManager
from src.task_manager.task_manager import TaskManager
from src.action_executor.action_executor import ActionExecutor
from src.log_manager.log_manager import LogManager

class TestRobustness(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.log_mgr = LogManager(log_dir=os.path.join(self.temp_dir, "logs"))
        self.context_mgr = ContextManager()
        self.executor = ActionExecutor(self.log_mgr, workspace_root=self.temp_dir)
        self.task_mgr = TaskManager(self.executor)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_session_isolation(self):
        """複数のセッションが互いに干渉しないことを検証"""
        def user_session(session_id, filename, content):
            # 文脈の追加 (正しい構造: analysis.entities)
            self.context_mgr.add_context({
                "session_id": session_id,
                "analysis": {
                    "intent": "FILE_CREATE",
                    "entities": {
                        "filename": {"value": filename},
                        "content": {"value": content}
                    }
                }
            })
            # 少し待機して並行性を模倣
            time.sleep(0.1)
            # コンテキストの取得
            last = self.context_mgr.get_last_context(session_id)
            self.assertEqual(last["entities"]["filename"]["value"], filename, f"Session {session_id} mismatched!")

        threads = []
        for i in range(5):
            t = threading.Thread(target=user_session, args=(f"user_{i}", f"file_{i}.txt", f"content_{i}"))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    def test_invalid_filename(self):
        """不正なファイル名（OS依存の予約語や文字）でのエラーハンドリングを検証"""
        # Windowsで不正な文字 '|' を含む
        invalid_filename = "invalid|file.txt"
        
        # 正しい実行形式: context["plan"]["action_method"]
        context = {
            "plan": {
                "action_method": "_create_file",
                "parameters": {"filename": invalid_filename, "content": "hello"}
            }
        }
        result_context = self.executor.execute(context)
        res = result_context["action_result"]
        self.assertEqual(res["status"], "error")
        # エラーメッセージに何らかの詳細が含まれていることを確認
        error_msg = res.get("message", "") or res.get("original_error", "")
        self.assertTrue(len(error_msg) > 0, "Error message should not be empty")

    def test_very_long_input(self):
        """非常に長い入力に対する挙動（バッファや処理時間）を検証"""
        long_content = "A" * (1024 * 1024)  # 1MB
        context = {
            "plan": {
                "action_method": "_create_file",
                "parameters": {"filename": "long.txt", "content": long_content}
            }
        }
        self.executor.execute(context)
        
        # 読み込み
        read_context = {
            "plan": {
                "action_method": "_read_file",
                "parameters": {"filename": "long.txt"}
            }
        }
        result = self.executor.execute(read_context)
        res = result["action_result"]
        self.assertEqual(len(res["content"]), 1024 * 1024)

if __name__ == "__main__":
    unittest.main()
