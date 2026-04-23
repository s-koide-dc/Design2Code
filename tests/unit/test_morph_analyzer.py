import unittest
from src.morph_analyzer.morph_analyzer import MorphAnalyzer

class TestMorphAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = MorphAnalyzer()

    def test_happy_path_basic_sentence(self):
        """
        ハッピーパス: '猫が歩く' という単純な文章を形態素解析する。
        """
        initial_context = {
            "original_text": "猫が歩く",
            "pipeline_history": [],
            "analysis": {},
            "errors": []
        }
        
        result_context = self.analyzer.analyze(initial_context)
        
        self.assertIsNotNone(result_context)
        self.assertIn("analysis", result_context)
        self.assertIn("tokens", result_context["analysis"])
        self.assertEqual(len(result_context["analysis"]["tokens"]), 3)
        
        self.assertEqual(result_context["analysis"]["tokens"][0]["surface"], "猫")
        self.assertEqual(result_context["analysis"]["tokens"][0]["pos"], "名詞,一般,*,*")
        self.assertEqual(result_context["analysis"]["tokens"][0]["base"], "猫")

        self.assertEqual(result_context["analysis"]["tokens"][1]["surface"], "が")
        self.assertEqual(result_context["analysis"]["tokens"][1]["pos"], "助詞,格助詞,一般,*")
        self.assertEqual(result_context["analysis"]["tokens"][1]["base"], "が")
        
        self.assertEqual(result_context["analysis"]["tokens"][2]["surface"], "歩く")
        self.assertEqual(result_context["analysis"]["tokens"][2]["pos"], "動詞,自立,*,*")
        self.assertEqual(result_context["analysis"]["tokens"][2]["base"], "歩く")

        self.assertIn("morph_analyzer", result_context["pipeline_history"])
        self.assertEqual(len(result_context["errors"]), 0)

    def test_edge_case_empty_string(self):
        """
        エッジケース: 空の文字列を形態素解析する。
        """
        initial_context = {
            "original_text": "",
            "pipeline_history": [],
            "analysis": {},
            "errors": []
        }
        
        result_context = self.analyzer.analyze(initial_context)
        
        self.assertIsNotNone(result_context)
        self.assertIn("analysis", result_context)
        self.assertIn("tokens", result_context["analysis"])
        self.assertEqual(len(result_context["analysis"]["tokens"]), 0) # 空のリストが期待される
        
        self.assertIn("morph_analyzer", result_context["pipeline_history"])
        self.assertEqual(len(result_context["errors"]), 0)

    def test_edge_case_missing_original_text(self):
        """
        エッジケース: original_textフィールドが存在しないコンテキスト。
        """
        initial_context = {
            "pipeline_history": [],
            "analysis": {},
            "errors": []
        }
        
        result_context = self.analyzer.analyze(initial_context)
        
        self.assertIsNotNone(result_context)
        self.assertIn("errors", result_context)
        self.assertGreater(len(result_context["errors"]), 0)
        self.assertIn("original_textがcontextに存在しない", result_context["errors"][0]["message"])
        # エラーが発生した場合、pipeline_historyは更新されない、analysis.tokensも更新されないことを確認
        self.assertNotIn("morph_analyzer", result_context["pipeline_history"])
        self.assertNotIn("tokens", result_context["analysis"])


    def test_edge_case_non_string_original_text(self):
        """
        エッジケース: original_textフィールドが文字列ではないコンテキスト。
        """
        initial_context = {
            "original_text": 123, # 数値
            "pipeline_history": [],
            "analysis": {},
            "errors": []
        }
        
        result_context = self.analyzer.analyze(initial_context)
        
        self.assertIsNotNone(result_context)
        self.assertIn("errors", result_context)
        self.assertGreater(len(result_context["errors"]), 0)
        self.assertIn("original_textがcontextに存在しないか、文字列ではありません。", result_context["errors"][0]["message"])
        self.assertNotIn("morph_analyzer", result_context["pipeline_history"])
        self.assertNotIn("tokens", result_context["analysis"])

if __name__ == '__main__':
    unittest.main()
