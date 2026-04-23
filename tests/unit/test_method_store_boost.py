# -*- coding: utf-8 -*-
import unittest
import os
import json
import shutil
import numpy as np
from src.code_synthesis.method_store import MethodStore

class TestMethodStoreBoost(unittest.TestCase):

    def setUp(self):
        self.test_dir = os.path.join(os.getcwd(), 'tests', 'tmp_method_store_boost')
        os.makedirs(self.test_dir, exist_ok=True)
        self.store_path = os.path.join(self.test_dir, 'test_store.json')
        
        # Mock config_manager
        class MockConfig:
            def __init__(self, store_path, storage_dir):
                self.method_store_path = store_path
                self.storage_dir = storage_dir
                self.workspace_root = os.getcwd()
                self.domain_dictionary_path = os.path.join(self.workspace_root, "resources", "domain_dictionary.json")
        
        self.store = MethodStore(config=MockConfig(self.store_path, self.test_dir))

        # テストデータの準備
        self.m1 = {
            "id": "external.util.task",
            "name": "ProcessTask",
            "class": "ExternalUtil",
            "tags": ["process"],
            "code": "public void ProcessTask() {}"
        }
        
        self.m2 = {
            "id": "project.internal.handler",
            "name": "HandleInternalTask",
            "class": "ProjectHandler",
            "tags": ["project_internal", "reuse"],
            "code": "public void HandleInternalTask() {}"
        }

        self.store.add_method(self.m1)
        self.store.add_method(self.m2)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_boost_project_internal(self):
        """プロジェクト内部/再利用タグを持つメソッドが優先されるか"""
        # ProcessTask (external) vs HandleInternalTask (internal + reuse)
        # 両方 "task" を含んでいるが、HandleInternalTask はタグによるブーストを得るはず。
        results = self.store.search("task")
        
        result_ids = [r['id'] for r in results]
        print(f"\nSearch results for 'task': {result_ids}")
        
        if results:
            # ブースト実装前はどちらが上かわからない（または ProcessTask が上かもしれない）
            # ブースト実装後は必ず HandleInternalTask が上に来るべき。
            self.assertEqual(results[0]["id"], "project.internal.handler")

if __name__ == '__main__':
    unittest.main()