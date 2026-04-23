# -*- coding: utf-8 -*-
import unittest
import os
from src.semantic_analyzer.semantic_analyzer import SemanticAnalyzer

class TestSemanticAnalyzerSearch(unittest.TestCase):
    def setUp(self):
        # Mock task_manager
        class MockTaskManager:
            pass
        
        # Mock config_manager
        class MockConfig:
            workspace_root = os.getcwd()
            custom_knowledge_path = os.path.join(workspace_root, "resources", "custom_knowledge.json")
            dictionary_db_path = os.path.join(workspace_root, "resources", "dictionary.db")
            
        self.analyzer = SemanticAnalyzer(MockTaskManager(), config_manager=MockConfig())

    def test_search_by_meaning(self):
        """意味による検索が機能するか"""
        results = self.analyzer.search_by_meaning("circle")
        print(f"\nSearch results for 'circle': {results}")
        self.assertTrue(len(results) > 0)
        words = [r["word"] for r in results]
        self.assertIn("○", words)

    def test_search_by_meaning_japanese(self):
        """日本語の意味による検索が機能するか"""
        results = self.analyzer.search_by_meaning("alphabet")
        print(f"\nSearch results for 'alphabet': {results}")
        self.assertTrue(len(results) > 0)

if __name__ == '__main__':
    unittest.main()