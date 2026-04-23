# -*- coding: utf-8 -*-
import unittest
import os
import shutil
from src.pipeline_core.pipeline_core import Pipeline

class TestContextAndAnaphora(unittest.TestCase):
    def setUp(self):
        self.pipeline = Pipeline()
        self.test_workspace = os.path.abspath("test_context_ws")
        if not os.path.exists(self.test_workspace):
            os.makedirs(self.test_workspace)
        self.pipeline.action_executor.workspace_root = self.test_workspace

    def tearDown(self):
        if os.path.exists(self.test_workspace):
            shutil.rmtree(self.test_workspace)

    def test_anaphora_resolution_flow(self):
        # 1. Create a file with content
        self.pipeline.run("memo.txt というファイルを作成して。内容は「これはメモです」で。")
        
        # 2. Read "it" (anaphora resolution)
        result = self.pipeline.run("それを読み込んで")
        
        intent = result["analysis"]["intent"]
        entities = result["analysis"]["entities"]
        
        self.assertEqual(entities.get("filename").get("value"), "memo.txt") # Access value of entity
        self.assertEqual(intent, "FILE_READ") # Expecting FILE_READ after anaphora resolution
        self.assertEqual(result["action_result"]["status"], "success")
        self.assertIn("これはメモです", result["action_result"]["message"]) # Assert content is read

    def test_history_persistence(self):
        self.pipeline.run("こんにちは")
        self.pipeline.run("元気？")
        
        history = self.pipeline.context_manager.get_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["intent"], "GREETING")

if __name__ == "__main__":
    unittest.main()
