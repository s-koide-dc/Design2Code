
import unittest
import sys
import os
from pathlib import Path

# Adjust path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

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

    def test_generate_fake_it_python(self):
        # Fake It logic: Should extract expected value and return it
        target_code = {'current_implementation': 'def add(a, b):\n    return 0', 'method': 'add', 'file': 'calc.py'}
        analysis = {'analysis_details': {'error_message': 'Expected: 5, Actual: 0'}}
        
        # Calling _generate_fallback_implementation_fix which uses _try_extract_expected_value
        suggestion = self.engine._generate_fallback_implementation_fix(target_code, analysis)
        
        self.assertIn('return 5', suggestion.suggested_code)
        self.assertNotIn('return 0', suggestion.suggested_code)

    def test_generate_fake_it_csharp(self):
        target_code = {'current_implementation': 'public int Add(int a, int b) { return 0; }', 'method': 'Add', 'file': 'Calc.cs'}
        analysis = {'analysis_details': {'error_message': 'Expected: 100, Actual: 0'}}
        
        suggestion = self.engine._generate_fallback_implementation_fix(target_code, analysis)
        
        self.assertIn('return 100;', suggestion.suggested_code)

    def test_generate_fake_it_fallback_to_todo(self):
        # If expected value extraction fails, should fallback to TODO
        target_code = {'current_implementation': 'def complex():\n    return None', 'method': 'complex', 'file': 'logic.py'}
        analysis = {'analysis_details': {'error_message': 'Unknown error'}}
        
        suggestion = self.engine._generate_fallback_implementation_fix(target_code, analysis)
        
        # Current logic for Python fallback: replaces 'return None' (matched by regex) with 'return # TODO...'
        self.assertIn('TODO', suggestion.suggested_code)

if __name__ == '__main__':
    unittest.main()
