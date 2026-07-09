# -*- coding: utf-8 -*-
import unittest
import os
import tempfile
from src.config.config_manager import ConfigManager
from src.morph_analyzer.morph_analyzer import MorphAnalyzer
from src.vector_engine.vector_engine import VectorEngine
from src.code_synthesis.method_store import MethodStore

class TestSemanticMethodSearch(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 重いモデルをロードするため一度だけ実行
        cls.original_suppress_vector_warnings = os.environ.get(
            "SUPPRESS_VECTOR_WARNINGS"
        )
        cls.original_skip_vector_model = os.environ.get("SKIP_VECTOR_MODEL")
        os.environ["SUPPRESS_VECTOR_WARNINGS"] = "1"
        os.environ.pop("SKIP_VECTOR_MODEL", None)
        cls.cm = ConfigManager()
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.cm.storage_dir = cls.temp_dir.name
        cls.ma = MorphAnalyzer()
        cls.ve = VectorEngine(model_path=cls.cm.vector_model_path)
        # Skip if cache is not available (determinism requires cache)
        if not getattr(cls.ve, "is_ready", False):
            cls.temp_dir.cleanup()
            cls._restore_environment()
            raise unittest.SkipTest("Vector cache is not available.")

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()
        cls._restore_environment()

    @classmethod
    def _restore_environment(cls):
        if cls.original_suppress_vector_warnings is None:
            os.environ.pop("SUPPRESS_VECTOR_WARNINGS", None)
        else:
            os.environ["SUPPRESS_VECTOR_WARNINGS"] = (
                cls.original_suppress_vector_warnings
            )
        if cls.original_skip_vector_model is None:
            os.environ.pop("SKIP_VECTOR_MODEL", None)
        else:
            os.environ["SKIP_VECTOR_MODEL"] = cls.original_skip_vector_model

    def test_file_write_search_respects_structural_capabilities(self):
        store = MethodStore(self.cm, self.ma, vector_engine=self.ve)
        query = "データをファイルに書き出す"
        results = store.search(
            query,
            limit=10,
            intent="PERSIST",
            required_capabilities=["FILE_IO", "WRITE"],
        )

        self.assertGreater(len(results), 0)
        self.assertTrue(all(
            {"FILE_IO", "WRITE"}.issubset(
                set(method.get("capabilities") or [])
            )
            for method in results
        ))
        self.assertTrue(any(
            method.get("class") == "System.IO.File"
            and method.get("name") in {
                "WriteAllText",
                "WriteAllTextAsync",
                "WriteAllLines",
            }
            for method in results
        ))

    def test_json_serialize_search_excludes_parse_candidates(self):
        store = MethodStore(self.cm, self.ma, vector_engine=self.ve)
        query = "オブジェクトをシリアライズする"
        results = store.search(
            query,
            limit=10,
            intent="TRANSFORM",
            required_capabilities=["JSON_SERIALIZE"],
        )

        self.assertGreater(len(results), 0)
        self.assertTrue(all(
            "JSON_SERIALIZE" in (method.get("capabilities") or [])
            for method in results
        ))
        self.assertTrue(any(
            method.get("class") == "System.Text.Json.JsonSerializer"
            and method.get("name").startswith("Serialize")
            for method in results
        ))
        self.assertFalse(any(
            method.get("name") in {"Parse", "ParseAsync", "Deserialize"}
            for method in results
        ))

if __name__ == "__main__":
    unittest.main()
