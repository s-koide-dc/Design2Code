import unittest
import sys
import os
import subprocess
from unittest.mock import patch

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.advanced_tdd.failure_analyzer import TestFailureAnalyzer

class TestFailureAnalyzerLogic(unittest.TestCase):
    def setUp(self):
        self.analyzer = TestFailureAnalyzer({})

    @patch('src.advanced_tdd.failure_analyzer.subprocess.run')
    def test_execute_python_test_uses_argument_list(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout='1 passed', stderr='')

        self.analyzer._execute_test('tests/test file.py; echo injected', 'python', '.')

        command = mock_run.call_args.args[0]
        self.assertIsInstance(command, list)
        self.assertIn('tests/test file.py; echo injected', command)
        self.assertNotIn('shell', mock_run.call_args.kwargs)

    @patch('src.advanced_tdd.failure_analyzer.subprocess.run')
    def test_execute_javascript_test_passes_actual_test_file(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout='{}', stderr='')

        self.analyzer._execute_test('tests/example.test.js', 'javascript', '.')

        command = mock_run.call_args.args[0]
        self.assertIn('--testPathPattern=tests/example.test.js', command)
        self.assertNotIn('--testPathPattern={test_file}', command)
        self.assertNotIn('shell', mock_run.call_args.kwargs)

    def test_evaluate_complex_condition_and(self):
        # A && B
        condition = "x > 0 && x < 20"

        # Input: 10 -> True
        result = self.analyzer._evaluate_complex_condition(condition, 10)
        self.assertTrue(result['is_satisfied'])
        self.assertTrue(result['evaluated'])

        # Input: 30 -> False
        result = self.analyzer._evaluate_complex_condition(condition, 30)
        self.assertFalse(result['is_satisfied'])
        # Check if failed part is identified correctly
        # Note: clean_part strips spaces, so "x < 20"
        self.assertTrue(any("x < 20" in p for p in result['failed_parts']))

    def test_evaluate_complex_condition_or(self):
        # A || B
        condition = "x < 0 || x > 100"

        # Input: -5 -> True
        result = self.analyzer._evaluate_complex_condition(condition, -5)
        self.assertTrue(result['is_satisfied'])

        # Input: 101 -> True
        result = self.analyzer._evaluate_complex_condition(condition, 101)
        self.assertTrue(result['is_satisfied'])

        # Input: 50 -> False
        result = self.analyzer._evaluate_complex_condition(condition, 50)
        self.assertFalse(result['is_satisfied'])
        self.assertEqual(len(result['failed_parts']), 2) # Both failed

    def test_evaluate_complex_condition_precedence(self):
        # A && B || C
        # Should be treated as (A && B) || C
        condition = "x > 0 && x < 10 || x == 100"

        # Case 1: (True && True) || False -> True
        # Input: 5
        result = self.analyzer._evaluate_complex_condition(condition, 5)
        self.assertTrue(result['is_satisfied'])

        # Case 2: (False && False) || True -> True
        # Input: 100
        result = self.analyzer._evaluate_complex_condition(condition, 100)
        self.assertTrue(result['is_satisfied'])

        # Case 3: (True && False) || False -> False
        # Input: 50
        result = self.analyzer._evaluate_complex_condition(condition, 50)
        self.assertFalse(result['is_satisfied'])

    def test_evaluate_condition_basic(self):
        # Helper method test
        self.assertTrue(self.analyzer._evaluate_condition(10, '>', '5'))
        self.assertTrue(self.analyzer._evaluate_condition(10, '==', '10'))
        self.assertFalse(self.analyzer._evaluate_condition(10, '<', '5'))

        # String comparison
        self.assertTrue(self.analyzer._evaluate_condition("Admin", '==', '"Admin"'))
        self.assertFalse(self.analyzer._evaluate_condition("User", '==', '"Admin"'))
        self.assertFalse(self.analyzer._evaluate_condition("not-a-number", '>', '5'))

    def test_resolve_identifier_value(self):
        # Mock Roslyn Data
        roslyn_data = {
            'details_by_id': {
                'enum1': {
                    'name': 'UserRole',
                    'fullName': 'MyApp.UserRole',
                    'type': 'Enum',
                    'members': [
                        {'name': 'Admin', 'value': 1},
                        {'name': 'User', 'value': 2}
                    ]
                },
                'class1': {
                    'name': 'Constants',
                    'fullName': 'MyApp.Constants',
                    'type': 'Class',
                    'properties': [
                        {'name': 'MaxRetries', 'modifiers': ['public', 'const'], 'initializer_value': 5}
                    ]
                }
            }
        }

        # Test Enum resolution
        self.assertEqual(self.analyzer._resolve_identifier_value('UserRole.Admin', roslyn_data), 1)
        self.assertEqual(self.analyzer._resolve_identifier_value('MyApp.UserRole.User', roslyn_data), 2)

        # Test Constant resolution
        self.assertEqual(self.analyzer._resolve_identifier_value('Constants.MaxRetries', roslyn_data), 5)

        # Test Unresolved
        self.assertEqual(self.analyzer._resolve_identifier_value('Unknown.Value', roslyn_data), 'Unknown.Value')

        # Test Literal (pass-through)
        self.assertEqual(self.analyzer._resolve_identifier_value('100', roslyn_data), '100')

    def test_evaluate_condition_with_enum(self):
        roslyn_data = {
            'details_by_id': {
                'enum1': {
                    'name': 'Status',
                    'type': 'Enum',
                    'members': [{'name': 'Active', 'value': 1}]
                }
            }
        }

        # Condition: status == Status.Active
        # Input: 1 (Active)
        # Should resolve Status.Active -> 1, then compare 1 == 1
        self.assertTrue(self.analyzer._evaluate_condition(1, '==', 'Status.Active', roslyn_data))

        # Input: 0 (Inactive)
        self.assertFalse(self.analyzer._evaluate_condition(0, '==', 'Status.Active', roslyn_data))

    def test_deep_stack_analysis(self):
        # Mock Stack Trace
        # Frame 1: Service.Process (No logic, just throws)
        # Frame 2: Validator.Validate (Has logic logic that fails)
        stack_trace = """
   at MyApp.Service.Process(Int32 val) in C:\\MyApp\\Service.cs:line 20
   at MyApp.Validator.Validate(Int32 val) in C:\\MyApp\\Validator.cs:line 10
   at MyApp.Tests.MyTest.Test_WhenValueIs5() in C:\\MyApp\\Tests\\MyTest.cs:line 5
"""
        from src.advanced_tdd.models import TestFailure
        failure = TestFailure(
            test_file="MyTest.cs",
            test_method="AnyTestName",
            error_type="assertion_failure",
            error_message="Error",
            stack_trace=stack_trace
        )

        # Mock Roslyn Data
        roslyn_data = {
            'manifest': {
                'objects': [
                    {
                        'id': 'class1',
                        'filePath': 'C:\\MyApp\\Service.cs',
                    },
                    {
                        'id': 'class2',
                        'filePath': 'C:\\MyApp\\Validator.cs',
                    },
                ]
            },
            'details_by_id': {
                'class1': {
                    'name': 'Service',
                    'methods': [
                        {
                            'name': 'Process',
                            'startLine': 15,
                            'endLine': 25,
                            'branches': [],
                        }
                    ]
                },
                'class2': {
                    'name': 'Validator',
                    'methods': [
                        {
                            'name': 'Validate',
                            'startLine': 5,
                            'endLine': 15,
                            'branches': [
                            {'condition': 'val > 10'} # 5 > 10 is False -> Mismatch!
                            ],
                        }
                    ]
                }
            }
        }

        # Execute Analysis
        result = self.analyzer._analyze_logic_mismatch(
            failure,
            roslyn_data,
            {'input_values': {'val': 5}},
        )

        # Verify
        self.assertIsNotNone(result)
        self.assertEqual(result['refined_root_cause'], 'logic_mismatch_with_branch')
        self.assertEqual(result['branch_condition'], 'val > 10')
        self.assertFalse(result['is_satisfied'])
        # Check if blamed frame is Validator.cs (Frame 2)
        self.assertIn('Validator.cs', result['blamed_frame']['file'])

    def test_property_based_reasoning(self):
        from src.advanced_tdd.models import TestFailure
        failure = TestFailure(
            test_file="UserTests.cs",
            test_method="Test_WhenUserAgeIs15_ShouldFail",
            error_type="assertion_failure",
            error_message="Expected: True, Actual: False",
            stack_trace=""
        )

        # Condition: user.Age >= 18
        condition = "user.Age >= 18"

        result = self.analyzer._evaluate_complex_condition(
            condition,
            {'Age': 15},
            test_failure=failure,
        )

        self.assertTrue(result['evaluated'])
        self.assertFalse(result['is_satisfied']) # 15 >= 18 is False

        # Another case: Test_WhenUserAgeIs20 (Satisfied)
        failure_success = TestFailure(
            test_file="UserTests.cs",
            test_method="Test_WhenUserAgeIs20",
            error_type="assertion_failure",
            error_message="...",
            stack_trace=""
        )
        result_success = self.analyzer._evaluate_complex_condition(
            condition,
            {'Age': 20},
            test_failure=failure_success,
        )
        self.assertTrue(result_success['is_satisfied']) # 20 >= 18 is True

    def test_logic_analysis_requires_explicit_input_values(self):
        from src.advanced_tdd.models import TestFailure
        failure = TestFailure(
            test_file="ExampleTests.cs",
            test_method="NameContains999",
            error_type="assertion_failure",
            error_message="Expected: True, Actual: False",
            stack_trace=(
                "at Example.Check(Int32 value) "
                "in C:\\Example\\Example.cs:line 10"
            ),
        )
        roslyn_data = {
            'manifest': {
                'objects': [{
                    'id': 'example',
                    'filePath': 'C:\\Example\\Example.cs',
                }]
            },
            'details_by_id': {
                'example': {
                    'methods': [{
                        'name': 'Check',
                        'startLine': 1,
                        'endLine': 20,
                        'branches': [{'condition': 'value > 10'}],
                    }]
                }
            },
        }

        result = self.analyzer.analyze_test_failure(failure, roslyn_data)

        self.assertIsNone(result['logic_analysis'])

    def test_semantic_mismatch_uses_explicit_roles_only(self):
        from src.advanced_tdd.models import TestFailure
        failure = TestFailure(
            test_file="ExampleTests.cs",
            test_method="SerializeNamedTest",
            error_type="assertion_failure",
            error_message="Expected: value, Actual: other",
            stack_trace="",
        )

        without_role = self.analyzer.analyze_test_failure(
            failure,
            expected_intent="PARSE",
        )
        with_role = self.analyzer.analyze_test_failure(
            failure,
            expected_intent="PARSE",
            analysis_context={'executed_role': 'SERIALIZE'},
        )

        self.assertIsNone(without_role['semantic_mismatch'])
        self.assertEqual(
            with_role['semantic_mismatch']['executed_role'],
            'SERIALIZE',
        )

    def test_analyze_test_failure_adds_analysis_summary(self):
        from src.advanced_tdd.models import TestFailure
        failure = TestFailure(
            test_file="CalculatorTests.cs",
            test_method="CalculatorTests.Add_ShouldReturnSum",
            error_type="assertion_failure",
            error_message="Expected: 5, Actual: 0",
            stack_trace="   at MyApp.Calculator.Add(Int32 a, Int32 b) in C:\\MyApp\\Calculator.cs:line 12"
        )

        result = self.analyzer.analyze_test_failure(failure)

        self.assertEqual(result["status"], "success")
        summary = result["analysis_summary"]
        self.assertEqual(summary["test_method"], "CalculatorTests.Add_ShouldReturnSum")
        self.assertEqual(summary["root_cause"], "method_returns_default_value")
        self.assertEqual(summary["target_file"], "C:\\MyApp\\Calculator.cs")
        self.assertEqual(summary["line_number"], 12)

if __name__ == '__main__':
    unittest.main()
