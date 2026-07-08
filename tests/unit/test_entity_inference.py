# -*- coding: utf-8 -*-
import unittest

from src.utils.entity_inference import infer_target_entity


class _TokenMorphAnalyzer:
    def __init__(self, tokens):
        self.tokens = tokens

    def analyze(self, payload):
        return {"analysis": {"tokens": self.tokens}}


class TestEntityInference(unittest.TestCase):
    def test_schema_keyword_requires_token_match(self):
        schema = {
            "entities": [
                {"name": "User", "keywords": ["ユーザー"]},
                {"name": "Order", "keywords": ["注文"]},
            ]
        }
        morph = _TokenMorphAnalyzer([
            {"base": "ユーザー", "surface": "ユーザー"},
        ])

        result = infer_target_entity(
            "ユーザーを処理する",
            [],
            schema,
            morph_analyzer=morph,
            allow_history_fallback=False,
        )

        self.assertEqual("User", result)

    def test_schema_keyword_does_not_match_arbitrary_substring(self):
        schema = {
            "entities": [
                {"name": "User", "keywords": ["user"]},
                {"name": "Order", "keywords": ["order"]},
            ]
        }
        morph = _TokenMorphAnalyzer([
            {"base": "superuser", "surface": "superuser"},
        ])

        result = infer_target_entity(
            "superuser を処理する",
            [],
            schema,
            morph_analyzer=morph,
            allow_history_fallback=False,
        )

        self.assertEqual("Item", result)

    def test_history_entity_is_used_when_keyword_does_not_match(self):
        schema = {
            "entities": [
                {"name": "User", "keywords": ["user"]},
                {"name": "Order", "keywords": ["order"]},
            ]
        }

        result = infer_target_entity(
            "対象を処理する",
            [{"target_entity": "Invoice"}],
            schema,
            morph_analyzer=_TokenMorphAnalyzer([]),
        )

        self.assertEqual("Invoice", result)


if __name__ == "__main__":
    unittest.main()
