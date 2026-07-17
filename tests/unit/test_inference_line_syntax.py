import unittest

from src.design_parser.inference_line_syntax import find_bracket_end, strip_leading_numbering


class TestInferenceLineSyntax(unittest.TestCase):
    def test_finds_closing_bracket_after_json_string_content(self):
        text = '[semantic_roles:{"message":"[keep]"}] display'
        self.assertEqual(text.index("] display"), find_bracket_end(text))

    def test_strips_number_or_list_marker(self):
        self.assertEqual("処理する", strip_leading_numbering("1. 処理する"))
        self.assertEqual("処理する", strip_leading_numbering("- 処理する"))
