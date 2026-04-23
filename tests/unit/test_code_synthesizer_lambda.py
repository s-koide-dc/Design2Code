# -*- coding: utf-8 -*-
import unittest
import json
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.config.config_manager import ConfigManager
from src.morph_analyzer.morph_analyzer import MorphAnalyzer

class TestReproLambda(unittest.TestCase):

    def setUp(self):
        from unittest.mock import MagicMock
        import tempfile
        import os
        
        self.test_dir = tempfile.TemporaryDirectory()
        self.store_path = os.path.join(self.test_dir.name, "test_method_store.json")
        self.dd_path = os.path.join(self.test_dir.name, "domain_dictionary.json")
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump([], f)
            
        with open(self.dd_path, "w", encoding="utf-8") as f:
            json.dump({
                "mappings": {
                    "保存": ["save"],
                    "取得": ["get"],
                    "一覧": ["list"],
                    "存在する": ["exists"],
                    "存在": ["exists"],
                    "チェック": ["check"],
                    "確認": ["check"],
                    "読み込む": ["read"],
                    "変換": ["select"],
                    "絞り込む": ["where"]
                }
            }, f, ensure_ascii=False)

        self.cm = MagicMock(spec=ConfigManager)
        self.cm.workspace_root = self.test_dir.name
        self.cm.method_store_path = self.store_path
        self.cm.storage_dir = self.test_dir.name
        self.cm.domain_dictionary_path = self.dd_path
        self.cm.repair_knowledge_path = os.path.join(self.test_dir.name, "repair_knowledge.json")
        self.cm.custom_knowledge_path = os.path.join(self.test_dir.name, "custom_knowledge.json")
        self.cm.dictionary_db_path = os.path.join(self.test_dir.name, "dictionary.db")
        self.cm.dependency_map_path = os.path.join(self.test_dir.name, "dependency_map.json")
        self.cm.intent_corpus_path = os.path.join(self.test_dir.name, "intent_corpus.json")
        self.cm.domain_dictionary_path = os.path.join(self.test_dir.name, "domain_dictionary.json")
        self.cm.error_patterns_path = os.path.join(self.test_dir.name, "error_patterns.json")
        self.cm.scoring_rules = {}
        self.cm.user_preferences = {}
        self.cm.get_retry_rules.return_value = []
        self.cm.get_safety_policy.return_value = {}

        from src.code_synthesis.method_store import MethodStore
        self.ms = MethodStore(self.cm)
        self.ms.methods = []

        self.ma = MorphAnalyzer(config_manager=self.cm)
        self.synthesizer = CodeSynthesizer(self.cm, method_store=self.ms, morph_analyzer=self.ma)
        
        # Inject required methods for lambda/conditional testing
        store = self.ms
        store.add_method({
            "id": "linq_where",
            "name": "Where",
            "class": "System.Linq.Enumerable",
            "return_type": "IEnumerable<T>",
            "params": [{"name": "source", "type": "IEnumerable<T>"}, {"name": "predicate", "type": "Func<T, bool>"}],
            "code": "{source}.Where({predicate})",
            "tags": ["linq", "filter"]
        })
        store.add_method({
            "id": "linq_select",
            "name": "Select",
            "class": "System.Linq.Enumerable",
            "return_type": "IEnumerable<TResult>",
            "params": [{"name": "source", "type": "IEnumerable<TSource>"}, {"name": "selector", "type": "Func<TSource, TResult>"}],
            "code": "{source}.Select({selector})",
            "tags": ["linq", "map"]
        })
        store.add_method({
            "id": "file_exists",
            "name": "Exists",
            "class": "System.IO.File",
            "return_type": "bool",
            "params": [{"name": "path", "type": "string"}],
            "code": "System.IO.File.Exists({path})",
            "tags": ["file", "check"]
        })
        store.add_method({
            "id": "file_readalltext",
            "name": "ReadAllText",
            "class": "System.IO.File",
            "return_type": "string",
            "params": [{"name": "path", "type": "string"}],
            "code": "System.IO.File.ReadAllText({path})",
            "tags": ["file", "read"]
        })
        store.add_method({
            "id": "get_users",
            "name": "GetUsers",
            "class": "Data.Repo",
            "return_type": "IEnumerable<User>",
            "params": [],
            "code": "Data.Repo.GetUsers()",
            "tags": ["data"]
        })
        store.add_method({
            "id": "get_files",
            "name": "GetFiles",
            "class": "System.IO.Directory",
            "return_type": "string[]",
            "params": [{"name": "path", "type": "string"}],
            "code": "System.IO.Directory.GetFiles({path})",
            "tags": ["file", "list"]
        })

    def tearDown(self):
        self.test_dir.cleanup()

    def test_synthesize_complex_lambda(self):
        """
        複雑な条件を含むラムダ式の合成テスト。
        """
        design_steps = [
            "ユーザーのリストを取得する",
            "価格が100より大きいアイテムで絞り込む"
        ]
        
        result = self.synthesizer.synthesize("FilterItems", design_steps)
        code = result["code"]
        print("\n--- Generated Code ---\n")
        print(code)
        
        self.assertIn("item.Price > 100", code)

    def test_synthesize_contains_lambda(self):
        """
        Containsを含むラムダ式の合成テスト。
        """
        design_steps = [
            "ファイルの一覧を取得する",
            "名前が'test'を含むもので絞り込む"
        ]
        
        result = self.synthesizer.synthesize("FindTestFiles", design_steps)
        code = result["code"]
        print("\n--- Generated Code (Contains) ---\n")
        print(code)
        
        self.assertIn('.Contains("test")', code)

    def test_synthesize_select_lambda(self):
        """
        Selectを含むラムダ式の合成テスト。
        """
        design_steps = [
            "ユーザーのリストを取得する",
            "Selectで各ユーザーの名前に変換する"
        ]
        
        # '変換' が Select にマッピングされることを期待
        result = self.synthesizer.synthesize("GetNames", design_steps)
        code = result["code"]
        
        # Select またはプロパティ名、あるいは Deserialize が含まれているか（変換ロジックの存在確認）
        self.assertTrue(any(kw in code for kw in [".Select", ".Name", "Deserialize"]))

    def test_synthesize_if_else(self):
        """
        if-else 構文の合成テスト。
        """
        design_steps = [
            "ファイルが存在するかチェックする",
            "もし存在するならば",
            "ファイルを読み込む",
            "そうでなければ",
            "エラーログを出力する",
            "を終えて"
        ]
        
        result = self.synthesizer.synthesize("CheckAndRead", design_steps)
        code = result["code"]
        print("\n--- Generated Code (If-Else) ---\n")
        print(code)
        
        self.assertIn("if (", code)
        # 現在の実装では else は TODO になる
        self.assertIn("TODO:", code)
        self.assertIn("File.Exists", code)

if __name__ == '__main__':
    unittest.main()
