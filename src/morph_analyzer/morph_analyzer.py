import os
from typing import Any, Dict, List

from janome.tokenizer import Tokenizer

class MorphAnalyzer:
    def __init__(self, config_manager=None):
        """
        Initializes the Morphological Analyzer with Janome's standard dictionary.
        Standard dictionary is preferred for better tokenization of common words.
        """
        self.config_manager = config_manager
        self.tokenizer = Tokenizer()


    def tokenize(self, text: str) -> List[Dict[str, Any]]:
        """
        文字列を形態素解析し、トークンのリストを返す便利メソッド。
        """
        if not text: return []
        tokens_data = []
        try:
            for token in self.tokenizer.tokenize(text):
                tokens_data.append({
                    "surface": token.surface,
                    "pos": token.part_of_speech,
                    "base": token.base_form
                })
        except Exception:
            pass
        return tokens_data

    def analyze(self, context: dict) -> dict:
        """
        形態素解析を行い、コンテキストオブジェクトのanalysis.tokensを更新する。

        Args:
            context (dict): pipeline_coreで定義されたコンテキストオブジェクト。
                            original_textを含む必要がある。

        Returns:
            dict: analysis.tokensが更新されたコンテキストオブジェクト。
        """
        # contextの基本構造を保証
        context.setdefault("analysis", {})
        context.setdefault("pipeline_history", [])
        context.setdefault("errors", [])

        if "original_text" not in context or not isinstance(context["original_text"], str):
            context["errors"].append({
                "module": "morph_analyzer", 
                "message": "original_textがcontextに存在しないか、文字列ではありません。"
            })
            return context

        text = context["original_text"]
        tokens_data = []

        if text: # 空文字列でない場合のみ解析
            try:
                for token in self.tokenizer.tokenize(text):
                    tokens_data.append({
                        "surface": token.surface,
                        "pos": token.part_of_speech,
                        "base": token.base_form,
                        # 必要に応じて他の情報も追加可能
                    })
            except Exception as e:
                context["errors"].append({
                    "module": "morph_analyzer",
                    "message": f"形態素解析中にエラーが発生しました: {e}"
                })
                return context

        context["analysis"]["tokens"] = tokens_data
        context["pipeline_history"].append("morph_analyzer")

        return context

if __name__ == '__main__':
    # 単体テスト用の簡易実行
    analyzer = MorphAnalyzer()
    
    # ハッピーパス
    context1 = {"original_text": "猫が歩く", "pipeline_history": [], "analysis": {}}
    result1 = analyzer.analyze(context1)
    print("--- Happy Path ---")
    print(result1)
    assert len(result1["analysis"]["tokens"]) == 3
    assert result1["analysis"]["tokens"][0]["surface"] == "猫"
    assert "morph_analyzer" in result1["pipeline_history"]
    print("Happy Path Test Passed.")

    # エッジケース: 空文字列
    context2 = {"original_text": "", "pipeline_history": [], "analysis": {}}
    result2 = analyzer.analyze(context2)
    print("--- Edge Case (Empty String) ---")
    print(result2)
    assert len(result2["analysis"]["tokens"]) == 0
    assert "morph_analyzer" in result2["pipeline_history"]
    print("Empty String Test Passed.")

    # エッジケース: original_textがない
    context3 = {"pipeline_history": [], "analysis": {}}
    result3 = analyzer.analyze(context3)
    print("--- Edge Case (Missing original_text) ---")
    print(result3)
    assert "errors" in result3
    assert any("original_textがcontextに存在しない" in e["message"] for e in result3["errors"])
    print("Missing original_text Test Passed.")

    # エッジケース: original_textが文字列ではない
    context4 = {"original_text": 123, "pipeline_history": [], "analysis": {}}
    result4 = analyzer.analyze(context4)
    print("--- Edge Case (original_text not string) ---")
    print(result4)
    assert "errors" in result4
    assert any("original_textがcontextに存在しないか、文字列ではありません。" in e["message"] for e in result4["errors"])
    print("original_text not string Test Passed.")

    print("\nAll basic tests passed for MorphAnalyzer.")
