import unittest
import sys
import os

sys.path.append(os.getcwd())

from src.ir_generator.ir_generator import IRGenerator
from src.morph_analyzer.morph_analyzer import MorphAnalyzer
from src.config.config_manager import ConfigManager

class TestIRGeneratorV2(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()
        self.morph_analyzer = MorphAnalyzer(self.config)
        self.ir_gen = IRGenerator(self.config, morph_analyzer=self.morph_analyzer)

    def test_database_fetch_collection(self):
        steps = ["全ユーザーを取得する"]
        ir = self.ir_gen.generate(steps)
        node = ir["logic_tree"][0]
        
        self.assertEqual(node["type"], "ACTION")
        # 決定論的解析により FETCH または GENERAL にマッピングされる
        self.assertTrue(node["role"] in ["FETCH", "GENERAL"])
        self.assertEqual(node["cardinality"], "COLLECTION")

    def test_database_fetch_single(self):
        steps = ["IDが1のユーザーを取得する"]
        ir = self.ir_gen.generate(steps)
        node = ir["logic_tree"][0]
        
        self.assertEqual(node["type"], "ACTION")
        self.assertTrue(node["role"] in ["FETCH", "GENERAL"])
        self.assertEqual(node["cardinality"], "SINGLE")

    def test_file_persist(self):
        steps = ["結果を 'report.txt' に保存する"]
        ir = self.ir_gen.generate(steps)
        node = ir["logic_tree"][0]
        
        self.assertEqual(node["type"], "ACTION")
        self.assertTrue(node["role"] in ["PERSIST", "GENERAL"])
        self.assertEqual(node["cardinality"], "SINGLE") 

    def test_loop_structure(self):
        steps = ["取得した各アイテムに対して", "表示する", "を終えて"]
        ir = self.ir_gen.generate(steps)
        loop_node = ir["logic_tree"][0]
        
        self.assertEqual(loop_node["type"], "LOOP")
        self.assertEqual(len(loop_node.get("children", [])), 1)
        body_node = loop_node.get("children", [])[0]
        self.assertTrue(body_node["role"] in ["DISPLAY", "GENERAL"])

if __name__ == '__main__':
    unittest.main()
