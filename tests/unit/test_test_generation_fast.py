# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
import shutil
import json

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
    def test_python_generation_rejects_missing_method_signature(self, mock_analyze):
        """Python解析に引数情報がない場合は未完成テストを生成しない。"""
        
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
        
        self.assertEqual(result['status'], 'error')
        self.assertEqual(
            "test_generation_unresolved",
            result["error"]["type"],
        )
        self.assertEqual(
            "python_method_signature_not_available",
            result["error"]["reason"],
        )
        self.assertEqual([], list(os.scandir(os.path.join(
            self.test_dir,
            "tests",
            "generated",
        ))))

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

    def test_malformed_explicit_json_is_not_reported_as_success(self):
        design_path = os.path.join(self.test_dir, "Sample.design.md")
        with open(design_path, "w", encoding="utf-8") as design:
            design.write(
                "# Sample\n"
                "## Test Cases\n"
                "- **Scenario**: malformed\n"
                "- **Input**: {invalid\n"
                "- **Expected**: {invalid\n"
            )

        result = self.generator.generate_tests_from_design(design_path)

        self.assertEqual(result["status"], "warning")
        self.assertTrue(
            any(
                diagnostic["operation"] == "parse_input_json"
                for diagnostic in result["generation_diagnostics"]
            )
        )
        with open(result["output_file"], encoding="utf-8") as generated:
            generated_code = generated.read()
        compile(generated_code, result["output_file"], "exec")

if __name__ == '__main__':
    unittest.main()
