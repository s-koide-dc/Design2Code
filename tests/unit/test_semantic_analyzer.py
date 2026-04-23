import unittest
import json
import tempfile
import os
from unittest.mock import MagicMock, patch
from src.semantic_analyzer.semantic_analyzer import SemanticAnalyzer

class TestSemanticAnalyzer(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.knowledge_path = os.path.join(self.test_dir.name, 'knowledge.json')
        
        self.knowledge_data = {
            "天気": "空の状態",
            "晴れ": "雲が少ない状態"
        }
        with open(self.knowledge_path, 'w', encoding='utf-8') as f:
            json.dump(self.knowledge_data, f, ensure_ascii=False)
            
        # Mock the TaskManager for SemanticAnalyzer initialization
        mock_task_manager = MagicMock()
        self.analyzer = SemanticAnalyzer(task_manager=mock_task_manager, knowledge_file_path=self.knowledge_path)
        
        # Patch _get_meaning to only return what's in our test knowledge
        self.patcher_meaning = patch.object(SemanticAnalyzer, '_get_meaning')
        self.mock_get_meaning = self.patcher_meaning.start()
        self.mock_get_meaning.side_effect = lambda word: self.knowledge_data.get(word)

    def tearDown(self):
        self.patcher_meaning.stop()
        self.test_dir.cleanup()

    def test_happy_path_topic_extraction(self):
        chunks = [
            [{"surface": "今日", "pos": "名詞,副詞可能,*,*", "base": "今日"}],
            [{"surface": "の", "pos": "助詞,連体化,*,*", "base": "の"}],
            [{"surface": "天気", "pos": "名詞,一般,*,*", "base": "天気"}],
            [{"surface": "は", "pos": "助詞,係助詞,*,*", "base": "は"}],
            [{"surface": "晴れ", "pos": "名詞,一般,*,*", "base": "晴れ"}],
            [{"surface": "です", "pos": "助動詞,*,*,*", "base": "です"}]
        ]
        initial_context = {
            "analysis": {"chunks": chunks},
            "pipeline_history": ["morph_analyzer", "syntactic_analyzer"]
        }
        
        result_context = self.analyzer.analyze(initial_context)
        
        self.assertIn("topics", result_context["analysis"])
        topics = result_context["analysis"]["topics"]
        
        def get_topic(text):
            for t in topics:
                if t["text"] == text:
                    return t
            return None

        t_today = get_topic("今日")
        self.assertIsNotNone(t_today)
        self.assertIsNone(t_today["meaning"])
        
        t_weather = get_topic("天気")
        self.assertIsNotNone(t_weather)
        self.assertEqual(t_weather["meaning"], "空の状態")
        
        t_sunny = get_topic("晴れ")
        self.assertIsNotNone(t_sunny)
        self.assertEqual(t_sunny["meaning"], "雲が少ない状態")

        self.assertIn("semantic_analyzer", result_context["pipeline_history"])
        self.assertEqual(len(result_context.get("errors", [])), 0)

    def test_no_nouns(self):
        chunks = [
            [{"surface": "走る", "pos": "動詞,自立,*,*", "base": "走る"}],
            [{"surface": "速く", "pos": "形容詞,自立,*,*", "base": "速い"}]
        ]
        initial_context = {"analysis": {"chunks": chunks}}
        
        result_context = self.analyzer.analyze(initial_context)
        
        self.assertEqual(result_context["analysis"]["topics"], [])

    def test_edge_case_empty_chunks(self):
        initial_context = {"analysis": {"chunks": []}}
        result_context = self.analyzer.analyze(initial_context)
        self.assertEqual(len(result_context["analysis"]["topics"]), 0)

    def test_edge_case_no_chunks(self):
        initial_context = {"analysis": {}}
        result_context = self.analyzer.analyze(initial_context)
        self.assertGreater(len(result_context["errors"]), 0)

    # --- Agentic Features Tests with Confidence ---

    def test_entity_extraction_filename_with_confidence(self):
        """Verify regex extraction of filenames with confidence."""
        initial_context = {
            "original_text": "data.csv を作成して",
            "analysis": {"chunks": []}
        }
        result = self.analyzer.analyze(initial_context)
        self.assertIn("filename", result["analysis"]["entities"])
        self.assertEqual(result["analysis"]["entities"]["filename"]["value"], "data.csv")
        self.assertEqual(result["analysis"]["entities"]["filename"]["confidence"], 0.9)

    def test_entity_extraction_content_with_confidence(self):
        """Verify regex extraction of content in brackets with confidence."""
        initial_context = {
            "original_text": "中身は『Hello AI』にして",
            "analysis": {"chunks": []}
        }
        result = self.analyzer.analyze(initial_context)
        self.assertIn("content", result["analysis"]["entities"])
        self.assertEqual(result["analysis"]["entities"]["content"]["value"], "Hello AI")
        self.assertEqual(result["analysis"]["entities"]["content"]["confidence"], 0.9)

    def test_entity_extraction_command_with_confidence(self):
        """Verify regex extraction of commands in quotes with confidence."""
        initial_context = {
            "original_text": "「dir /w」を実行して",
            "analysis": {"chunks": []}
        }
        result = self.analyzer.analyze(initial_context)
        self.assertIn("command", result["analysis"]["entities"])
        self.assertEqual(result["analysis"]["entities"]["command"]["value"], "dir /w")
        self.assertEqual(result["analysis"]["entities"]["command"]["confidence"], 0.9)

    def test_anaphora_resolution_with_confidence(self):
        """Verify resolution of 'それ' using history with confidence."""
        history = [
            {"entities": {"filename": {"value": "previous.txt", "confidence": 0.95}}} # history already has confidence
        ]
        initial_context = {
            "original_text": "それを読み込んで",
            "history": history,
            "analysis": {"chunks": []}
        }
        result = self.analyzer.analyze(initial_context)
        self.assertIn("filename", result["analysis"]["entities"])
        self.assertEqual(result["analysis"]["entities"]["filename"]["value"], "previous.txt")
        # When resolving from history, if history already has confidence, it should be preserved.
        self.assertEqual(result["analysis"]["entities"]["filename"]["confidence"], 0.95)

        # Test case where history only has value, should get default history_confidence
        history_plain_value = [
            {"entities": {"filename": "another.txt"}} # history without confidence in entity dict
        ]
        initial_context_plain_value = {
            "original_text": "それを編集",
            "history": history_plain_value,
            "analysis": {"chunks": []}
        }
        result_plain_value = self.analyzer.analyze(initial_context_plain_value)
        self.assertIn("filename", result_plain_value["analysis"]["entities"])
        self.assertEqual(result_plain_value["analysis"]["entities"]["filename"]["value"], "another.txt")
        self.assertEqual(result_plain_value["analysis"]["entities"]["filename"]["confidence"], 0.8) # Default history confidence

    def test_anaphora_resolution_priority_with_confidence(self):
        """Verify that direct entities override history resolution, and confidence is from direct."""
        history = [
            {"entities": {"filename": {"value": "old.txt", "confidence": 0.85}}}
        ]
        initial_context = {
            "original_text": "new_file.txt ではなく、それを読み込んで", 
            "history": history,
            "analysis": {"chunks": []}
        }
        # Direct match for "new_file.txt" should take precedence and its confidence should be used.
        result = self.analyzer.analyze(initial_context)
        self.assertIn("filename", result["analysis"]["entities"])
        self.assertEqual(result["analysis"]["entities"]["filename"]["value"], "new_file.txt")
        self.assertEqual(result["analysis"]["entities"]["filename"]["confidence"], 0.9) # Base confidence for direct regex

    def test_state_dependent_filename_confidence_boost(self):
        """Verify state-dependent confidence boost for filename."""
        initial_context = {
            "original_text": "report.docx を作って",
            "task": {"name": "FILE_CREATE", "state": "AWAITING_FILENAME"},
            "analysis": {"chunks": []}
        }
        result = self.analyzer.analyze(initial_context)
        self.assertIn("filename", result["analysis"]["entities"])
        self.assertEqual(result["analysis"]["entities"]["filename"]["value"], "report.docx")
        # Base confidence 0.9 + boost 0.1 = 1.0
        self.assertAlmostEqual(result["analysis"]["entities"]["filename"]["confidence"], 1.0)

    def test_state_dependent_filename_no_boost_without_state(self):
        """Verify no confidence boost if not in specific state."""
        initial_context = {
            "original_text": "image.png を表示",
            "task": {"name": "FILE_READ"}, # Not AWAITING_FILENAME
            "analysis": {"chunks": []}
        }
        result = self.analyzer.analyze(initial_context)
        self.assertIn("filename", result["analysis"]["entities"])
        self.assertEqual(result["analysis"]["entities"]["filename"]["value"], "image.png")
        self.assertAlmostEqual(result["analysis"]["entities"]["filename"]["confidence"], 0.9)


if __name__ == '__main__':
    unittest.main()