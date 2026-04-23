# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
import shutil

from src.test_generator.test_generator import TestGenerator
from src.action_executor.action_executor import ActionExecutor
from src.config.config_manager import ConfigManager

class TestTestGenerationFast(unittest.TestCase):
    """TestGeneratorの高速なユニットテスト（モック使用）"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Create a dummy file to satisfy os.path.exists
        self.dummy_csharp = os.path.join(self.test_dir, "Calculator.cs")
        with open(self.dummy_csharp, 'w') as f: f.write("dummy")
        
        self.dummy_python = os.path.join(self.test_dir, "math_utils.py")
        with open(self.dummy_python, 'w') as f: f.write("dummy")

        self.generator = TestGenerator(workspace_root=self.test_dir)
        
        self.mock_log_manager = MagicMock()
        self.mock_config = MagicMock(spec=ConfigManager)
        self.mock_config.error_patterns_path = "dummy_errors.json"
        
        self.executor = ActionExecutor(
            log_manager=self.mock_log_manager,
            workspace_root=self.test_dir,
            config_manager=self.mock_config
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('src.test_generator.test_generator.TestGenerator._analyze_source_code')
    def test_generate_csharp_logic(self, mock_analyze):
        """C#のテスト生成ロジックの検証（AST解析をモック）"""
        
        # 期待される解析結果を定義
        mock_analyze.return_value = {
            'status': 'success',
            'language': 'csharp',
            'classes': [{
                'name': 'Calculator',
                'namespace': 'MathLibrary',
                'methods': [
                    {
                        'name': 'Add',
                        'return_type': 'int',
                        'parameters': 'int a, int b',
                        'test_scenarios': [{'type': 'happy_path', 'condition': 'Default', 'expected_behavior': 'Success'}]
                    }
                ],
                'properties': []
            }]
        }

        result = self.generator.generate_test_cases(self.dummy_csharp, language='csharp')
        
        if result['status'] != 'success':
            print(f"DEBUG: CSharp result error: {result.get('message')}")

        self.assertEqual(result['status'], 'success')
        self.assertIn('test_cases', result)
        self.assertTrue(len(result['test_cases']) > 0)
        
        # 生成されたコードの内容を確認
        code = result['test_cases'][0]['code']
        self.assertIn('using Xunit;', code)
        self.assertIn('class CalculatorTests', code)

    @patch('src.test_generator.test_generator.TestGenerator._analyze_source_code')
    def test_generate_python_logic(self, mock_analyze):
        """Pythonのテスト生成ロジックの検証"""
        
        mock_analyze.return_value = {
            'status': 'success',
            'language': 'python',
            'classes': [{
                'name': 'MathUtils',
                'methods': [
                    {
                        'name': 'multiply',
                        'test_scenarios': [{'type': 'happy_path', 'condition': 'Default', 'expected_behavior': 'Success'}]
                    }
                ]
            }]
        }

        result = self.generator.generate_test_cases(self.dummy_python, language='python')
        
        if result['status'] != 'success':
            print(f"DEBUG: Python result error: {result.get('message')}")

        self.assertEqual(result['status'], 'success')
        code = result['test_cases'][0]['code']
        self.assertIn('import unittest', code)
        self.assertIn('class TestMathUtils', code)

    def test_action_executor_bridge(self):
        """ActionExecutor経由でのテスト生成呼び出しの検証"""
        with patch.object(TestGenerator, 'generate_test_cases') as mock_gen:
            mock_gen.return_value = {'status': 'success', 'test_cases': [], 'message': 'Done'}
            
            context = {"session_id": "test_sid"}
            # ActionExecutor._generate_test_cases uses parameters.get("filename")
            parameters = {"filename": "Calculator.cs"}
            
            # Use execute_action (restored) or private method directly
            res_context = self.executor.execute_action("_generate_test_cases", context, parameters)
            
            if res_context["action_result"]["status"] != "success":
                print(f"DEBUG: Action result error: {res_context['action_result'].get('message')}")

            self.assertEqual(res_context["action_result"]["status"], "success")
            mock_gen.assert_called_once()

if __name__ == '__main__':
    unittest.main()