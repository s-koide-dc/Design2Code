import unittest
from unittest.mock import MagicMock
from src.semantic_analyzer.semantic_analyzer import SemanticAnalyzer

class TestEntityExtractionStress(unittest.TestCase):
    def setUp(self):
        self.mock_tm = MagicMock()
        self.analyzer = SemanticAnalyzer(task_manager=self.mock_tm)

    def test_complex_paths_with_spaces(self):
        text = "「My Documents/Project Files/draft ver1.txt」を読み込んで"
        context = {"original_text": text, "analysis": {"entities": {}}}
        entities = self.analyzer._extract_entities(text, [], context, "FILE_READ") # Pass a dummy intent
        self.assertEqual(entities["filename"]["value"], "My Documents/Project Files/draft ver1.txt")

    def test_multiple_entities_with_particles(self):
        text = "old_data_backup_2024.csvをnew_data.csvにコピーして"
        context = {"original_text": text, "analysis": {"entities": {}}}
        entities = self.analyzer._extract_entities(text, [], context, "FILE_COPY") # Pass FILE_COPY intent
        self.assertEqual(entities["source_filename"]["value"], "old_data_backup_2024.csv")
        self.assertEqual(entities["destination_filename"]["value"], "new_data.csv")

    def test_deeply_nested_paths(self):
        text = "src/modules/core/utils/config/settings.jsonの内容を表示"
        context = {"original_text": text, "analysis": {"entities": {}}}
        entities = self.analyzer._extract_entities(text, [], context, "FILE_READ") # Pass a dummy intent
        # Use message to debug
        self.assertEqual(entities["filename"]["value"], "src/modules/core/utils/config/settings.json", f"Extracted: {entities}")

    def test_japanese_filename_with_extension(self):
        text = "「議事録_20260115.docx」を作成"
        context = {"original_text": text, "analysis": {"entities": {}}}
        entities = self.analyzer._extract_entities(text, [], context, "FILE_CREATE") # Pass a dummy intent
        self.assertEqual(entities["filename"]["value"], "議事録_20260115.docx")

    def test_ambiguous_destination(self):
        text = "開発用/テストファイル.txtを本番用/完了ファイル.txtにリネームして"
        context = {"original_text": text, "analysis": {"entities": {}}}
        entities = self.analyzer._extract_entities(text, [], context, "FILE_MOVE") # Pass FILE_MOVE intent
        self.assertEqual(entities["source_filename"]["value"], "開発用/テストファイル.txt")
        self.assertEqual(entities["destination_filename"]["value"], "本番用/完了ファイル.txt")

if __name__ == "__main__":
    unittest.main()
