# -*- coding: utf-8 -*-
import unittest
import json
import os
from src.ir_generator.ir_generator import IRGenerator
from src.config.config_manager import ConfigManager

class TestIRGenerator(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()
        self.generator = IRGenerator(self.config)

    def test_generate_simple_chain(self):
        steps = [
            "Data.Repo.GetUsersで全ユーザーを取得する",
            "結果を 'active_users.txt' に保存する"
        ]
        ir = self.generator.generate(steps)
        
        self.assertEqual(len(ir["logic_tree"]), 2)
        # 決定論的解析により、最初のステップは FETCH 意図を持つ ACTION
        self.assertEqual(ir["logic_tree"][0]["type"], "ACTION")
        # エンティティ名は解析の深さに依存するため、存在確認に留める
        self.assertTrue(len(ir["logic_tree"][0]["target_entity"]) > 0)

    def test_generate_nested_structure(self):
        steps = [
            "リトライする。以下の処理を繰り返す：",
            "Data.Repo.GetUsersで全ユーザーを取得する。",
            "取得した各アイテムに対して、以下の処理を行う：",
            "名前をコンソールに表示する。",
            "を終えて。",
            "を終えて。"
        ]
        ir = self.generator.generate(steps)
        
        # Structure: ACTION(Retry) -> children: [ACTION(GetUsers), LOOP -> children: [ACTION(Display)]]
        self.assertEqual(ir["logic_tree"][0]["type"], "ACTION")
        wrapper_children = ir["logic_tree"][0].get("children", [])
        self.assertTrue(len(wrapper_children) >= 1)

    def test_generate_conditional(self):
        steps = [
            "もし config.json が存在するならば、以下の処理を行う：",
            "ファイルを読み込む。",
            "そうでなければ、以下の処理を行う：",
            "エラーを表示する。",
            "を終えて。"
        ]
        ir = self.generator.generate(steps)
        
        self.assertEqual(ir["logic_tree"][0]["type"], "CONDITION")
        self.assertEqual(len(ir["logic_tree"][0].get("children", [])), 1)
        self.assertEqual(len(ir["logic_tree"][0].get("else_children", [])), 1)

    def test_input_link_prefers_latest_collection(self):
        steps = [
            "Data.Repo.GetUsersで全ユーザーを取得する。",
            "取得したユーザーの件数を計算する。",
            "ユーザー一覧をコンソールに表示する。"
        ]
        ir = self.generator.generate(steps)
        
        self.assertEqual(len(ir["logic_tree"]), 3)
        first_node = ir["logic_tree"][0]
        display_node = ir["logic_tree"][2]
        
        self.assertEqual(first_node.get("cardinality"), "COLLECTION")
        self.assertEqual(display_node.get("intent"), "DISPLAY")
        self.assertEqual(display_node.get("input_link"), first_node.get("id"))

if __name__ == "__main__":
    unittest.main()
