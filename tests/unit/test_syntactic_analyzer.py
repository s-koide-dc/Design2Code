import unittest
from src.syntactic_analyzer.syntactic_analyzer import SyntacticAnalyzer

class TestSyntacticAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = SyntacticAnalyzer()

    def test_happy_path_chunking(self):
        """
        ハッピーパス: 「猫が歩く」というトークンリストをチャンク化する。
        """
        # `morph_analyzer`からの出力を模倣
        tokens = [
            { "surface": "猫", "pos": "名詞,一般,*,*", "base": "猫" },
            { "surface": "が", "pos": "助詞,格助詞,一般,*", "base": "が" },
            { "surface": "歩く", "pos": "動詞,自立,*,*", "base": "歩く" }
        ]
        initial_context = {
            "analysis": {"tokens": tokens},
            "pipeline_history": ["morph_analyzer"]
        }
        
        result_context = self.analyzer.analyze(initial_context)
        
        self.assertIn("chunks", result_context["analysis"])
        chunks = result_context["analysis"]["chunks"]
        
        # 2つのチャンクが生成されることを期待
        self.assertEqual(len(chunks), 2)
        
        # 1つ目のチャンクは「猫が」
        self.assertEqual(len(chunks[0]), 2)
        self.assertEqual(chunks[0][0]["surface"], "猫")
        self.assertEqual(chunks[0][1]["surface"], "が")
        
        # 2つ目のチャンクは「歩く」
        self.assertEqual(len(chunks[1]), 1)
        self.assertEqual(chunks[1][0]["surface"], "歩く")

        self.assertIn("syntactic_analyzer", result_context["pipeline_history"])
        self.assertEqual(len(result_context.get("errors", [])), 0)

    def test_multiple_noun_phrases(self):
        """
        ハッピーパス: 複数の名詞句を含む文をテストする。「太郎が花子にリンゴを渡した」
        """
        tokens = [
            {"surface": "太郎", "pos": "名詞,固有名詞,人名,名", "base": "太郎"},
            {"surface": "が", "pos": "助詞,格助詞,一般,*", "base": "が"},
            {"surface": "花子", "pos": "名詞,固有名詞,人名,名", "base": "花子"},
            {"surface": "に", "pos": "助詞,格助詞,一般,*", "base": "に"},
            {"surface": "リンゴ", "pos": "名詞,一般,*,*", "base": "リンゴ"},
            {"surface": "を", "pos": "助詞,格助詞,一般,*", "base": "を"},
            {"surface": "渡した", "pos": "動詞,自立,*,*", "base": "渡す"},
        ]
        initial_context = {"analysis": {"tokens": tokens}}
        
        result_context = self.analyzer.analyze(initial_context)
        
        self.assertIn("chunks", result_context["analysis"])
        chunks = result_context["analysis"]["chunks"]

        self.assertEqual(len(chunks), 4) # 「太郎が」「花子に」「リンゴを」「渡した」
        self.assertEqual(len(chunks[0]), 2) # 太郎が
        self.assertEqual(chunks[0][0]["surface"], "太郎")
        self.assertEqual(len(chunks[1]), 2) # 花子に
        self.assertEqual(chunks[1][0]["surface"], "花子")
        self.assertEqual(len(chunks[2]), 2) # リンゴを
        self.assertEqual(chunks[2][0]["surface"], "リンゴ")
        self.assertEqual(len(chunks[3]), 1) # 渡した
        self.assertEqual(chunks[3][0]["surface"], "渡した")

    def test_edge_case_empty_tokens(self):
        """
        エッジケース: 空のトークンリストを処理する。
        """
        initial_context = {"analysis": {"tokens": []}}
        
        result_context = self.analyzer.analyze(initial_context)
        
        self.assertIn("chunks", result_context["analysis"])
        self.assertEqual(len(result_context["analysis"]["chunks"]), 0)
        self.assertIn("syntactic_analyzer", result_context["pipeline_history"])

    def test_edge_case_no_tokens(self):
        """
        エッジケース: contextにtokensキーが存在しない。
        """
        initial_context = {"analysis": {}}
        
        result_context = self.analyzer.analyze(initial_context)
        
        self.assertIn("errors", result_context)
        self.assertGreater(len(result_context["errors"]), 0)
        self.assertEqual(result_context["errors"][0]["module"], "syntactic_analyzer")
        self.assertNotIn("chunks", result_context["analysis"])
        self.assertNotIn("syntactic_analyzer", result_context.get("pipeline_history", []))

if __name__ == '__main__':
    unittest.main()
