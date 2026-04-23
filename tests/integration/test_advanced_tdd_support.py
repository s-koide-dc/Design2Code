
import unittest
from unittest.mock import MagicMock, patch, ANY
import os
import json
from datetime import datetime

# Adjust import path as necessary based on project structure
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.advanced_tdd.main import AdvancedTDDSupport
from src.advanced_tdd.models import TDDGoal, CodeFixSuggestion, TestFailure
from src.advanced_tdd.ast_analyzer import ASTAnalyzer
from src.advanced_tdd.failure_analyzer import TestFailureAnalyzer
from src.advanced_tdd.safety_validator import SafetyValidator

class TestASTAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = ASTAnalyzer()

    def test_analyze_python_structure(self):
        code = """
class TestClass:
    def test_method(self, a, b):
        return a + b
"""
        result = self.analyzer.analyze_code_structure(code, 'python')
        self.assertEqual(result['status'], 'success')
        classes = result['structure']['classes']
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0]['name'], 'TestClass')
        self.assertIn('test_method', classes[0]['methods'])

    def test_analyze_csharp_structure(self):
        code = """
public class TestClass {
    public int TestMethod(int a, int b) {
        return a + b;
    }
}
"""
        result = self.analyzer.analyze_code_structure(code, 'csharp')
        self.assertEqual(result['status'], 'success')
        classes = result['structure']['classes']
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0]['name'], 'TestClass')

    def test_ast_analyzer_csharp_from_roslyn(self):
        roslyn_data = {
            'manifest': {
                'objects': [
                    {
                        'id': '1', 
                        'fullName': 'MyNs.Calculator', 
                        'type': 'Class', 
                        'startLine': 1, 
                        'endLine': 10,
                        'accessibility': 'Public'
                    }
                ]
            },
            'details_by_id': {
                '1': {
                    'id': '1',
                    'metrics': {'cyclomaticComplexity': 5, 'lineCount': 10, 'maxComplexity': 3},
                    'methods': [
                        {
                            'name': 'Add', 
                            'parameters': [], 
                            'startLine': 3, 
                            'endLine': 5,
                            'returnType': 'int',
                            'metrics': {'cyclomaticComplexity': 3, 'lineCount': 3}
                        }
                    ]
                }
            }
        }
        result = self.analyzer.analyze_code_structure("", language='csharp', roslyn_data=roslyn_data)
        self.assertEqual(result['source'], 'roslyn')
        clz = result['structure']['classes'][0]
        self.assertEqual(clz['name'], 'MyNs.Calculator')
        self.assertEqual(clz['metrics']['cyclomaticComplexity'], 5)
        
        mth = result['structure']['methods'][0]
        self.assertEqual(mth['name'], 'Add')
        self.assertEqual(mth['metrics']['cyclomaticComplexity'], 3)



        
class TestTestFailureAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = TestFailureAnalyzer({})

    def test_parse_pytest_failure(self):
        output = """
=================================== FAILURES ===================================
FAILED test_file.py::test_example - AssertionError: assert 1 == 2
    def test_example():
>       assert 1 == 2
E       assert 1 == 2
=========================== 1 failed in 0.05 seconds ===========================
"""
        # Mocking extraction logic indirectly by testing stdout parsing logic if exposed,
        # otherwise we rely on _parse_pytest_stdout which is internal but accessible for testing.
        failed_tests = self.analyzer._parse_pytest_stdout(output)
        self.assertEqual(len(failed_tests), 1)
        self.assertIn('test_file.py', failed_tests[0]['file'])
        self.assertIn('assert 1 == 2', failed_tests[0]['error_message'])

    def test_identify_root_cause_assertion(self):
        failure = TestFailure(
            test_file='test.py', test_method='test', error_type='assertion_failure',
            error_message='Expected: 5, Actual: 0', stack_trace='', line_number=1
        )
        cause = self.analyzer._identify_root_cause(failure, 'assertion_failure')
        self.assertEqual(cause, 'method_returns_default_value')

class TestSafetyValidator(unittest.TestCase):
    def setUp(self):
        self.ast_analyzer = ASTAnalyzer()
        self.validator = SafetyValidator({}, ast_analyzer=self.ast_analyzer)

    def test_safety_validator_csharp_breaking_change_structural(self):
        suggestion = CodeFixSuggestion(
            id='f1', type='method_implementation', priority='high',
            description='引数の型を変更',
            current_code='public int Add(int a, int b) { return a + b; }',
            suggested_code='public int Add(string a, string b) { return int.Parse(a) + int.Parse(b); }',
            safety_score=1.0, impact_analysis={}, auto_applicable=False
        )
        target_code = {'file': 'Calculator.cs'}
        impact = self.validator._analyze_impact_scope(suggestion, target_code)
        self.assertTrue(impact['breaking_changes'])
        self.assertIn('APIシグネチャの変更', impact['risk_factors'])

    def test_safety_validator_no_breaking_change(self):
        suggestion = CodeFixSuggestion(
            id='f1', type='method_implementation', priority='high',
            description='中身だけ変更',
            current_code='public int Add(int a, int b) { return 0; }',
            suggested_code='public int Add(int a, int b) { return a + b; }',
            safety_score=1.0, impact_analysis={}, auto_applicable=False
        )
        target_code = {'file': 'Calculator.cs'}
        impact = self.validator._analyze_impact_scope(suggestion, target_code)
        self.assertFalse(impact['breaking_changes'])

class TestAdvancedTDDIntegration(unittest.TestCase):
    def setUp(self):
        self.workspace_root = os.getcwd()
        # Mock dependencies
        self.mock_config = MagicMock()
        
        # Instantiate AdvancedTDDSupport
        self.tdd_support = AdvancedTDDSupport(self.workspace_root)
        
        # Mock the internal engine (AutonomousSynthesizer) to avoid complex setup
        self.tdd_support.tdd_engine = MagicMock()

    def test_execute_goal_driven_tdd_integration(self):
        """Verify AdvancedTDDSupport delegates to AutonomousSynthesizer"""
        goal_data = {
            'description': 'Create calculator',
            'acceptance_criteria': ['Add numbers'],
            'priority': 'High'
        }
        
        # Setup mock return from decompose_and_synthesize
        self.tdd_support.tdd_engine.decompose_and_synthesize.return_value = {
            "status": "success",
            "results": [
                {
                    "requirement": {"method_name": "Add"},
                    "result": {"status": "success", "code": "public int Add..."}
                }
            ]
        }
        
        result = self.tdd_support.execute_goal_driven_tdd(goal_data)
        
        # Verify delegation
        self.tdd_support.tdd_engine.decompose_and_synthesize.assert_called_once()
        args, _ = self.tdd_support.tdd_engine.decompose_and_synthesize.call_args
        self.assertEqual(args[0].description, 'Create calculator')
        
        # Verify result mapping
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['tdd_cycle_results']['total'], 1)
        self.assertEqual(result['tdd_cycle_results']['success'], 1)
        self.assertIn('public int Add...', result['generated_artifacts']['code'])

if __name__ == '__main__':
    unittest.main()
