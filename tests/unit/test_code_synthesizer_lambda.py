# -*- coding: utf-8 -*-
import unittest
import json
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.config.config_manager import ConfigManager
from src.morph_analyzer.morph_analyzer import MorphAnalyzer
from src.code_synthesis.method_store import MethodStore

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
            "tags": ["data"],
            "intent": "FETCH",
            "role": "FETCH",
            "capabilities": ["FETCH", "DATA_FETCH"]
        })
        store.add_method({
            "id": "get_files",
            "name": "GetFiles",
            "class": "System.IO.Directory",
            "return_type": "string[]",
            "params": [{"name": "path", "type": "string"}],
            "code": "System.IO.Directory.GetFiles({path})",
            "tags": ["file", "list"],
            "intent": "FETCH",
            "role": "FETCH",
            "capabilities": ["FETCH", "FILE_IO"]
        })

    def tearDown(self):
        self.test_dir.cleanup()

    def test_synthesize_complex_lambda(self):
        """
        複雑な条件を含むラムダ式の合成テスト。
        """
        design_steps = [
            {"text": "GetUsers"},
            {
                "text": "価格が100より大きいアイテムで絞り込む",
                "semantic_roles": {"property": "Price"},
            },
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
            {
                "text": "GetFiles",
                "semantic_roles": {"path": "."},
            },
            "名前が'test'を含むもので絞り込む"
        ]

        result = self.synthesizer.synthesize("FindTestFiles", design_steps)
        code = result["code"]
        print("\n--- Generated Code (Contains) ---\n")
        print(code)

        self.assertIn('.Contains("test")', code)
        self.assertIn(".ToArray()", code)
        self.assertIn('string[] result0 = System.IO.Directory.GetFiles(".")', code)
        self.assertNotIn("return;\n", code)

    def test_synthesize_select_lambda(self):
        """
        Selectを含むラムダ式の合成テスト。
        """
        design_steps = [
            {"text": "GetUsers"},
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
            "'input.txt' が存在するかチェックする",
            "もし存在するならば",
            {
                "text": "ReadAllText",
                "intent": "FETCH",
                "explicit_intent": True,
                "source_kind": "file",
                "semantic_roles": {"path": "input.txt"},
            },
            "そうでなければ",
            {
                "text": "エラーログを出力する",
                "semantic_roles": {
                    "output_channel": "stderr",
                    "log_level": "error",
                    "message": "入力ファイルが存在しません。",
                },
            },
            "を終えて"
        ]

        result = self.synthesizer.synthesize("CheckAndRead", design_steps)
        code = result["code"]
        print("\n--- Generated Code (If-Else) ---\n")
        print(code)

        self.assertIn("if (", code)
        self.assertIn("else", code)
        self.assertNotIn("TODO", code)
        self.assertIn("File.Exists", code)
        self.assertIn('File.ReadAllText("input.txt")', code)
        self.assertNotIn("WriteAllText", code)
        self.assertIn(
            'Console.Error.WriteLine("入力ファイルが存在しません。")',
            code,
        )
        self.assertNotIn("Console.WriteLine(result0)", code)
        self.assertIn("bool result0 = File.Exists", code)
        self.assertIn("if (result0)", code)

    def test_stderr_display_requires_explicit_message(self):
        result = self.synthesizer.synthesize(
            "WriteError",
            [{
                "text": "エラーログを出力する",
                "intent": "DISPLAY",
                "explicit_intent": True,
                "semantic_roles": {
                    "output_channel": "stderr",
                    "log_level": "error",
                },
            }],
        )

        self.assertEqual("error", result.get("status"))
        unresolved = result.get("error", {}).get("unresolved_nodes", [])
        self.assertEqual(
            "display_message_not_explicit",
            unresolved[0].get("reason"),
        )

    def test_display_does_not_infer_notification_from_text(self):
        result = self.synthesizer.synthesize(
            "Notify",
            [{
                "text": "全ての処理が完了しました",
                "intent": "DISPLAY",
                "explicit_intent": True,
                "semantic_roles": {},
            }],
        )

        self.assertEqual("error", result.get("status"))
        self.assertEqual("", result.get("code"))
        unresolved = result.get("error", {}).get("unresolved_nodes", [])
        self.assertEqual(
            "display_source_not_explicit",
            unresolved[0].get("reason"),
        )

    def test_knowledge_base_filters_incompatible_write_candidate(self):
        candidates = self.synthesizer.ukb.search(
            "ファイルを読み込む",
            intent="FETCH",
            requested_role="FETCH",
            source_kind="file",
        )

        candidate_ids = [candidate.get("id") for candidate in candidates]
        self.assertTrue(candidate_ids)
        self.assertNotIn("file_writealltext", candidate_ids)

    def test_ambiguous_candidates_are_reported_with_candidate_ids(self):
        result = self.synthesizer.synthesize_from_structured_spec(
            "ReadUnknownSource",
            {
                "module_name": "ReadUnknownSource",
                "purpose": "ambiguous candidate test",
                "inputs": [],
                "outputs": [],
                "constraints": [],
                "test_cases": [],
                "data_sources": [],
                "steps": [{
                    "id": "step_1",
                    "text": "入力を取得する",
                    "kind": "ACTION",
                    "intent": "GENERAL",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": [],
                    "output_type": "string",
                    "side_effect": "NONE",
                    "semantic_roles": {},
                }],
            },
        )

        self.assertEqual("error", result.get("status"))
        unresolved = result.get("error", {}).get("unresolved_nodes", [])
        self.assertEqual("ambiguous_method_candidates", unresolved[0].get("reason"))
        self.assertGreater(
            len(unresolved[0].get("details", {}).get("candidate_ids", [])),
            1,
        )

    def test_explicit_rethrow_error_policy_is_emitted(self):
        result = self.synthesizer.synthesize(
            "ReadOrThrow",
            [{
                "text": "ReadAllText",
                "intent": "FETCH",
                "explicit_intent": True,
                "source_kind": "file",
                "semantic_roles": {
                    "path": "input.txt",
                    "error_policy": "rethrow",
                },
            }],
        )

        self.assertEqual("success", result.get("status"), result)
        self.assertIn("catch (Exception ex)", result.get("code", ""))
        self.assertIn("throw;", result.get("code", ""))

    def test_return_default_error_policy_does_not_swallow_cancellation(self):
        result = self.synthesizer.synthesize(
            "ReadOrDefault",
            [{
                "text": "ReadAllText",
                "intent": "FETCH",
                "explicit_intent": True,
                "source_kind": "file",
                "semantic_roles": {
                    "path": "input.txt",
                    "error_policy": "return_default",
                },
            }],
        )

        self.assertEqual("success", result.get("status"), result)
        code = result.get("code", "")
        cancellation_catch = code.index("catch (OperationCanceledException)")
        general_catch = code.index("catch (Exception ex)")
        self.assertLess(cancellation_catch, general_catch)
        cancellation_block = code[
            cancellation_catch:general_catch
        ]
        self.assertIn("throw;", cancellation_block)
        general_catch_block = code[general_catch:]
        self.assertIn("return;", general_catch_block)
        self.assertNotIn("return result0;", general_catch_block)

    def test_invalid_error_policy_is_rejected(self):
        result = self.synthesizer.synthesize(
            "ReadWithInvalidPolicy",
            [{
                "text": "ReadAllText",
                "source_kind": "file",
                "semantic_roles": {
                    "path": "input.txt",
                    "error_policy": "ignore_and_guess",
                },
            }],
        )

        self.assertEqual("error", result.get("status"))
        unresolved = result.get("error", {}).get("unresolved_nodes", [])
        self.assertEqual("invalid_error_policy", unresolved[0].get("reason"))

if __name__ == '__main__':
    unittest.main()
