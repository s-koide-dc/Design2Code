# -*- coding: utf-8 -*-
import unittest
import os
import shutil
import tempfile
from src.pipeline_core.pipeline_core import Pipeline

class TestEndToEndScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp()
        cls.old_cwd = os.getcwd()
        
        # Copy necessary resources to the test directory
        resources_src = os.path.join(cls.old_cwd, "resources")
        resources_dst = os.path.join(cls.test_dir, "resources")
        shutil.copytree(resources_src, resources_dst)
        
        # Create necessary directories for operations
        os.makedirs(os.path.join(cls.test_dir, "logs"), exist_ok=True)
        
        os.chdir(cls.test_dir)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.old_cwd)
        shutil.rmtree(cls.test_dir)
    def setUp(self):
        self.pipeline = Pipeline()

    def test_file_creation_and_reading_flow(self):
        """test_integration.txt を作成し、その後読み取るフローを検証"""
        # 1. Create File
        input_text = "test_integration.txt を作成して。内容は「統合テスト成功」にして。"
        result = self.pipeline.run(input_text)
        
        self.assertEqual(result["analysis"]["intent"], "FILE_CREATE")
        self.assertEqual(result["action_result"]["status"], "success")
        self.assertTrue(os.path.exists("test_integration.txt"))
        
        # 2. Read File
        input_read = "test_integration.txt を読んで。"
        result_read = self.pipeline.run(input_read)
        
        self.assertEqual(result_read["analysis"]["intent"], "FILE_READ")
        self.assertIn("統合テスト成功", result_read["action_result"]["content"])

    def test_security_traversal_integration(self):
        """統合レベルでのパス・トラバーサル阻止を検証"""
        input_text = "../outside_workspace.txt を読んで。"
        result = self.pipeline.run(input_text)
        
        self.assertEqual(result["action_result"]["status"], "error")
        self.assertIn("無効なパス", result["action_result"]["message"])

    def test_command_injection_integration(self):
        """統合レベルでのコマンドインジェクション阻止を検証 (2ターン対話)"""
        # 1st turn: Command request
        session_id = "session_injection_test"
        input_text = f"session_id:{session_id} コマンド「echo hello & dir」を実行して。"
        result = self.pipeline.run(input_text)
        self.assertIn("response", result)
        self.assertIn("text", result["response"])
        self.assertIn("不正な文字", result["response"]["text"])
        self.assertNotIn("action_result", result)

if __name__ == "__main__":
    unittest.main()
