# -*- coding: utf-8 -*-
import unittest
import os
import json
import tempfile
import shutil
from pathlib import Path
from src.config.config_manager import ConfigManager

class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.workspace_root = Path(self.test_dir)
        self.config_dir = self.workspace_root / "config"
        os.makedirs(self.config_dir)
        
        # Create dummy config files
        self.config_data = {"logging": {"log_level": "DEBUG"}, "test_key": "test_val"}
        with open(self.config_dir / "config.json", 'w', encoding='utf-8') as f:
            json.dump(self.config_data, f)
            
        self.safety_data = {"safe_commands": ["git", "ls"]}
        with open(self.config_dir / "safety_policy.json", 'w', encoding='utf-8') as f:
            json.dump(self.safety_data, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_load_valid_config(self):
        """正常な設定ファイルの読み込み検証"""
        cm = ConfigManager(workspace_root=self.test_dir)
        
        self.assertEqual(cm.get("test_key"), "test_val")
        self.assertEqual(cm.get_section("logging")["log_level"], "DEBUG")
        self.assertIn("git", cm.get_safety_policy()["safe_commands"])

    def test_missing_config_fallback(self):
        """ファイル欠落時のフォールバック検証"""
        # resourcesディレクトリ自体がない空のディレクトリをルートにする
        empty_dir = tempfile.mkdtemp()
        try:
            cm = ConfigManager(workspace_root=empty_dir)
            self.assertEqual(cm.config_data, {})
            self.assertEqual(cm.get_safety_policy(), {})
            # パス文字列自体は生成されることを確認
            self.assertTrue(cm.intent_corpus_path.endswith("intent_corpus.json"))
        finally:
            shutil.rmtree(empty_dir)

    def test_invalid_json_handling(self):
        """不正なJSONファイルが含まれる場合の検証"""
        with open(self.config_dir / "bad.json", 'w', encoding='utf-8') as f:
            f.write("{ invalid json")
            
        cm = ConfigManager(workspace_root=self.test_dir)
        # _load_json を直接テスト
        res = cm._load_json(self.config_dir / "bad.json")
        self.assertEqual(res, {})

    def test_path_resolution(self):
        """各リソースパスが正しく解決されているか検証"""
        cm = ConfigManager(workspace_root=self.test_dir)
        
        # 相対パスではなく絶対パスになっていること
        self.assertTrue(os.path.isabs(cm.intent_corpus_path))
        self.assertIn("resources", cm.vector_model_path)
        self.assertIn("vectors", cm.vector_model_path)

if __name__ == '__main__':
    unittest.main()
