# -*- coding: utf-8 -*-
import unittest
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.pipeline_core.pipeline_core import Pipeline

class TestReverseLookupFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = Pipeline(is_test_mode=True)

    def test_reverse_lookup_intent_detection(self):
        """逆引き検索の意図抽出テスト"""
        text = "「円」の意味を持つ記号は？"
        context = {"original_text": text, "session_id": "test_session", "pipeline_history": [], "analysis": {}, "errors": []}
        context = self.pipeline.morph_analyzer.analyze(context)
        context = self.pipeline.intent_detector.detect(context)
        self.assertEqual(context["analysis"]["intent"], "REVERSE_DICTIONARY_SEARCH")

    def test_reverse_lookup_entity_extraction(self):
        """逆引き検索のエンティティ抽出テスト"""
        text = "「円」の意味を持つ記号は？"
        context = {"original_text": text, "session_id": "test_session", "pipeline_history": [], "analysis": {}, "errors": []}
        context = self.pipeline.morph_analyzer.analyze(context)
        context = self.pipeline.syntactic_analyzer.analyze(context) # Important!
        context = self.pipeline.intent_detector.detect(context)
        context = self.pipeline.semantic_analyzer.analyze(context)
        entities = context["analysis"].get("entities", {})
        self.assertIn("query", entities)
        self.assertEqual(entities["query"]["value"], "「円」")

    def test_reverse_lookup_full_flow(self):
        """逆引き検索の全体フローテスト"""
        response = self.pipeline.run("circleの意味を持つ記号は？")
        self.assertIn("○", response['response']['text'])

if __name__ == '__main__':
    unittest.main()