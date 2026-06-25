# -*- coding: utf-8 -*-
import unittest
import os
import json
import shutil
import numpy as np
from src.code_synthesis.method_store import MethodStore
from src.code_synthesis.method_store_policy import MethodStorePolicy

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

    def test_legacy_vector_store_files_are_migrated_to_vector_db(self):
        """旧 resources 直下の method_store ベクトルDBファイルを統一保存先へ移行する"""
        workspace_root = os.path.join(self.test_dir, "workspace")
        resources_dir = os.path.join(workspace_root, "resources")
        target_dir = os.path.join(resources_dir, "vectors", "vector_db")
        os.makedirs(resources_dir, exist_ok=True)
        store_path = os.path.join(resources_dir, "method_store.json")
        with open(store_path, "w", encoding="utf-8") as f:
            json.dump({"methods": self.test_data}, f)

        legacy_meta = os.path.join(resources_dir, "method_store_meta.json")
        legacy_vec = os.path.join(resources_dir, "method_store_vectors.npy")
        with open(legacy_meta, "w", encoding="utf-8") as f:
            json.dump(self.test_data, f)
        np.save(legacy_vec, np.zeros((len(self.test_data), self.vector_engine.dim)))

        class MockConfig:
            def __init__(self):
                self.workspace_root = workspace_root
                self.method_store_path = store_path
                self.storage_dir = target_dir
                self.domain_dictionary_path = os.path.join(resources_dir, "domain_dictionary.json")

        MethodStore(config=MockConfig(), vector_engine=self.vector_engine)

        self.assertFalse(os.path.exists(legacy_meta))
        self.assertFalse(os.path.exists(legacy_vec))
        self.assertTrue(os.path.exists(os.path.join(target_dir, "method_store_meta.json")))
        self.assertTrue(os.path.exists(os.path.join(target_dir, "method_store_vectors.npy")))

    def test_add_method_prunes_low_value_harvested_api(self):
        """harvest 経路の低価値 API は共通 policy で MethodStore に入れない"""
        before = len(self.store.items)
        self.store.add_method(
            {
                "id": "system.consolekeyinfo.gethashcode",
                "name": "GetHashCode",
                "class": "System.ConsoleKeyInfo",
                "return_type": "int",
                "params": [],
                "code": "value.GetHashCode()",
                "definition": "Int32 GetHashCode()",
                "tags": ["harvested"],
            }
        )

        self.assertEqual(len(self.store.items), before)
        self.assertIsNone(self.store.get_method_by_id("system.consolekeyinfo.gethashcode"))

    def test_policy_reports_prune_reason_from_structured_policy(self):
        """除外ルールは resources の構造化 policy から読み、理由を監査できる"""
        policy = MethodStorePolicy(workspace_root=os.getcwd())

        normalized = policy.normalize(
            {
                "id": "system.consolekeyinfo.gethashcode",
                "name": "GetHashCode",
                "class": "System.ConsoleKeyInfo",
                "return_type": "int",
                "params": [],
                "code": "value.GetHashCode()",
                "tags": ["harvested"],
            }
        )

        audit = policy.get_audit_summary()
        self.assertIsNone(normalized)
        self.assertEqual(audit["pruned"], 1)
        self.assertEqual(audit["prune_reasons"]["object_protocol"], 1)

    def test_policy_uses_custom_policy_file_without_code_change(self):
        """policy JSON の exact class 追加だけで pruning ルールを拡張できる"""
        workspace_root = os.path.join(self.test_dir, "policy_workspace")
        resources_dir = os.path.join(workspace_root, "resources")
        os.makedirs(resources_dir, exist_ok=True)
        policy_path = os.path.join(resources_dir, "method_store_policy.json")
        with open(policy_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "semantic_roles": ["FETCH"],
                    "allowed_capabilities": ["FETCH"],
                    "pruning": {
                        "method_names": {},
                        "class_suffixes": {},
                        "class_contains": {},
                        "class_prefixes": {},
                        "exact_classes": {"project_specific_low_value": ["App.GeneratedNoise"]},
                        "method_allowlist_by_class": {},
                        "header_value_suffixes": [],
                        "header_value_methods": [],
                    },
                },
                f,
            )

        policy = MethodStorePolicy(workspace_root=workspace_root)
        normalized = policy.normalize(
            {
                "id": "app.generatednoise.run",
                "name": "Run",
                "class": "App.GeneratedNoise",
                "return_type": "void",
                "params": [],
                "code": "App.GeneratedNoise.Run()",
                "tags": ["harvested"],
            }
        )

        audit = policy.get_audit_summary()
        self.assertIsNone(normalized)
        self.assertEqual(audit["prune_reasons"]["project_specific_low_value"], 1)

    def test_add_method_normalizes_capabilities_for_harvested_http_api(self):
        """harvest entry は保存前に role / capabilities / param role を補完する"""
        self.store.add_method(
            {
                "id": "system.net.http.httpclient.getasync",
                "name": "GetAsync",
                "class": "System.Net.Http.HttpClient",
                "return_type": "Task<HttpResponseMessage>",
                "params": [{"name": "requestUri", "type": "string"}],
                "code": "client.GetAsync({requestUri})",
                "definition": "Task<HttpResponseMessage> GetAsync(string requestUri)",
                "tags": ["harvested"],
            }
        )

        method = self.store.get_method_by_id("system.net.http.httpclient.getasync")
        self.assertIsNotNone(method)
        self.assertEqual(method["role"], "HTTP_REQUEST")
        self.assertIn("HTTP_REQUEST", method["capabilities"])
        self.assertEqual(method["params"][0]["role"], "url")

    def test_rebuild_index_from_source_replaces_stale_vector_db(self):
        """rebuild は既存 vector DB ではなく method_store.json を正として作り直す"""
        stale_item = {
            "id": "stale",
            "name": "OldMethod",
            "class": "OldService",
            "tags": ["old"],
            "code": "OldService.OldMethod()",
        }
        self.store.collection.items = [stale_item]
        self.store.collection.vectors = np.zeros((1, self.vector_engine.dim), dtype=np.float32)
        self.store.collection.id_to_index = {"stale": 0}
        self.store.collection._save()

        rebuilt_count = self.store.rebuild_index_from_source()

        self.assertEqual(rebuilt_count, len(self.test_data))
        self.assertEqual([item["id"] for item in self.store.items], ["test1", "test2"])
        self.assertNotIn("stale", self.store.collection.id_to_index)
        self.assertEqual(len(self.store.collection.vectors), len(self.test_data))

    def test_save_regenerates_vectors_when_collection_shape_is_stale(self):
        """save は件数合わせのゼロ埋めではなく現在の items から vector を再生成する"""
        self.store.collection.vectors = np.zeros((1, self.vector_engine.dim), dtype=np.float32)

        self.store.save()

        self.assertEqual(len(self.store.collection.vectors), len(self.store.items))
        self.assertGreater(float(np.linalg.norm(self.store.collection.vectors[0])), 0.0)

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
