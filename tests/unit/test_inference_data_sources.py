import unittest

from src.design_parser.inference_data_sources import build_file_source_ref, collect_data_sources


class TestInferenceDataSources(unittest.TestCase):
    def test_collects_only_resolved_declarations(self):
        resolved = collect_data_sources(["input", "logic", "output"], lambda line: {"input": "[data_source|in|file]", "output": "[data_source|out|file]"}.get(line, ""))
        self.assertEqual(["[data_source|in|file]", "[data_source|out|file]"], resolved)

    def test_builds_stable_file_source_ref(self):
        self.assertEqual("sales_report_csv", build_file_source_ref("data/Sales Report.csv"))
