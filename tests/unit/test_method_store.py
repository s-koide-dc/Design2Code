# -*- coding: utf-8 -*-
import unittest
import os
import json
import shutil
import numpy as np
from src.code_synthesis.method_store import MethodStore

class TestMethodStore(unittest.TestCase):

    def setUp(self):
        self.test_dir = os.path.join(os.getcwd(), 'tests', 'tmp_method_store')
        os.makedirs(self.test_dir, exist_ok=True)
        self.store_path = os.path.join(self.test_dir, 'test_store.json')
        
        # テストデータの準備 (新形式: リスト)
        self.test_data = [
            {
                "id": "test1",
                "name": "ValidateEmail",
                "class": "TestService",
                "tags": ["validation", "email"],
                "code": "public bool ValidateEmail(string email) { return true; }"
            },
            {
                "id": "test2",
                "name": "GetUser",
                "class": "TestService",
                "tags": ["database", "read"],
                "code": "public User GetUser(int id) { return new User(); }"
            }
        ]
        with open(self.store_path, 'w', encoding='utf-8') as f:
            json.dump(self.test_data, f)

        class DummyVectorEngine:
            def __init__(self, dim: int = 64):
                self.dim = dim
            def get_sentence_vector(self, words):
                if not words:
                    return None
                text = " ".join([str(w) for w in words]).lower()
                vec = np.zeros(self.dim, dtype=np.float32)
                for ch in text:
                    vec[ord(ch) % self.dim] += 1.0
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec /= norm
                return vec
            def vector_similarity(self, v1, v2):
                if v1 is None or v2 is None:
                    return 0.0
                return float(np.dot(v1, v2))

        class MockConfig:
            def __init__(self, store_path, storage_dir):
                self.method_store_path = store_path
                self.storage_dir = storage_dir
                self.domain_dictionary_path = os.path.join(storage_dir, "domain_dictionary.json")

        self.vector_engine = DummyVectorEngine()
        self.store = MethodStore(config=MockConfig(self.store_path, self.test_dir), vector_engine=self.vector_engine)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_load(self):
        """ストアのロードが正しく行われるか"""
        self.assertEqual(len(self.store.items), 2)
        self.assertEqual(self.store.items[0]["name"], "ValidateEmail")

    def test_search_happy_path(self):
        """キーワードによる検索のテスト"""
        # "email" で検索 (タグにマッチ)
        results = self.store.search("email")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["name"], "ValidateEmail")

    def test_search_japanese_query(self):
        """日本語クエリによる検索のテスト (SymbolMatcherの連動)"""
        # SymbolMatcher が "検証" を "validate" にマップすることを期待
        # (domain_dictionary.json に依存するが、ここでは簡易的に英語キーワードが含まれるクエリを試す)
        results = self.store.search("emailを検証する")
        self.assertTrue(len(results) > 0)
        # スコア計算により ValidateEmail が上位に来るはず
        self.assertEqual(results[0]["name"], "ValidateEmail")

    def test_add_method(self):
        """メソッドの追加と保存のテスト"""
        new_method = {
            "id": "test3",
            "name": "SaveData",
            "class": "TestService",
            "tags": ["write"],
            "code": "public void SaveData() {}"
        }
        self.store.add_method(new_method)
        self.assertEqual(len(self.store.items), 3)
        
        self.store.save()
        
        # ファイルを直接確認
        with open(self.store_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Unified format: {"methods": [...]}
            methods = data.get("methods", [])
            self.assertEqual(len(methods), 3)

    def test_edge_case_not_found(self):
        """ヒットしない場合の検索"""
        results = self.store.search("")
        self.assertEqual(len(results), 0)

if __name__ == '__main__':
    unittest.main()
