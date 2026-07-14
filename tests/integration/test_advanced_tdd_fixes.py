
import unittest
import os

from src.advanced_tdd.fix_engine import CodeFixSuggestionEngine

class TestCodeFixSuggestionEngineAdvanced(unittest.TestCase):
    def setUp(self):
        config = {'code_fix': {}}
        self.engine = CodeFixSuggestionEngine(config)

    def test_extract_expected_value_numeric(self):
        msg = "Expected: 5, Actual: 0"
        val = self.engine._try_extract_expected_value(msg)
        self.assertEqual(val, "5")

    def test_extract_expected_value_string(self):
        msg = 'Expected: "hello", Actual: "world"'
        val = self.engine._try_extract_expected_value(msg)
        self.assertEqual(val, '"hello"')

    # test_extract_expected_value_assert_equals removed to avoid ambiguity

    def test_fallback_does_not_hardcode_python_expected_value(self):
        target_code = {'current_implementation': 'def add(a, b):\n    return 0', 'method': 'add', 'file': 'calc.py'}
        analysis = {'analysis_details': {'error_message': 'Expected: 5, Actual: 0'}}

        # Calling _generate_fallback_implementation_fix which uses _try_extract_expected_value
        suggestion = self.engine._generate_fallback_implementation_fix(target_code, analysis)

        self.assertEqual(suggestion.suggested_code, '')
        self.assertFalse(suggestion.auto_applicable)
        self.assertEqual(suggestion.type, 'manual_fix')

    def test_fallback_does_not_hardcode_csharp_expected_value(self):
        target_code = {'current_implementation': 'public int Add(int a, int b) { return 0; }', 'method': 'Add', 'file': 'Calc.cs'}
        analysis = {'analysis_details': {'error_message': 'Expected: 100, Actual: 0'}}

        suggestion = self.engine._generate_fallback_implementation_fix(target_code, analysis)

        self.assertEqual(suggestion.suggested_code, '')
        self.assertFalse(suggestion.auto_applicable)

    def test_fallback_does_not_generate_todo(self):
        target_code = {'current_implementation': 'def complex():\n    return None', 'method': 'complex', 'file': 'logic.py'}
        analysis = {'analysis_details': {'error_message': 'Unknown error'}}

        suggestion = self.engine._generate_fallback_implementation_fix(target_code, analysis)

        self.assertNotIn('TODO', suggestion.suggested_code)
        self.assertFalse(suggestion.auto_applicable)

if __name__ == '__main__':
    unittest.main()
