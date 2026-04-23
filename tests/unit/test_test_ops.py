# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch
import os
from src.test_operations.test_operations import TestAndCoverageOperations

class TestTestAndCoverageOperations(unittest.TestCase):
    def setUp(self):
        self.mock_ae = MagicMock()
        # Mocking _get_entity_value to return the input itself for simplicity
        self.mock_ae._get_entity_value.side_effect = lambda x, default=None: x.get("value") if isinstance(x, dict) else x if x is not None else default
        self.mock_ae._safe_join.side_effect = lambda x: x # Mock simple path joining
        
        self.ops = TestAndCoverageOperations(self.mock_ae)

    def test_measure_coverage_success(self):
        """measure_coverage の正常系テスト"""
        context = {}
        parameters = {
            "project_path": "src/",
            "language": "python"
        }
        
        # Mock CoverageAnalyzer response
        mock_result = {
            "status": "success",
            "coverage_summary": {"line_coverage": 85.5, "branch_coverage": 70.0},
            "reports": {"json_report": "reports/coverage.json"}
        }
        self.mock_ae.coverage_analyzer.analyze_project.return_value = mock_result
        
        with patch('os.path.exists', return_value=True):
            result_context = self.ops.measure_coverage(context, parameters)
            
        self.assertEqual(result_context["action_result"]["status"], "success")
        self.assertIn("85.5%", result_context["action_result"]["message"])
        self.mock_ae.coverage_analyzer.analyze_project.assert_called_once()

    def test_measure_coverage_missing_path(self):
        """プロジェクトパス不足時のエラーハンドリング"""
        context = {}
        parameters = {} # No project_path
        
        result_context = self.ops.measure_coverage(context, parameters)
        self.assertEqual(result_context["action_result"]["status"], "error")
        self.assertIn("プロジェクトパスが指定されていません", result_context["action_result"]["message"])

    def test_analyze_coverage_gaps_success(self):
        """analyze_coverage_gaps の正常系テスト"""
        context = {}
        parameters = {
            "project_path": "src/",
            "language": "python"
        }
        
        mock_result = {
            "status": "success",
            "gap_analysis": {
                "uncovered_files": [{"file": "module_a.py", "uncovered_methods": ["func1"]}],
                "missing_test_scenarios": [{"target_method": "func1", "scenario": "edge case"}]
            },
            "recommendations": [{"priority": "high"}]
        }
        self.mock_ae.coverage_analyzer.analyze_project.return_value = mock_result
        
        with patch('os.path.exists', return_value=True):
            result_context = self.ops.analyze_coverage_gaps(context, parameters)
            
        self.assertEqual(result_context["action_result"]["status"], "success")
        self.assertIn("ギャップ分析が完了しました", result_context["action_result"]["message"])
        self.assertIn("module_a.py", result_context["action_result"]["message"])

    def test_generate_coverage_report_success(self):
        """generate_coverage_report の正常系テスト"""
        context = {}
        parameters = {
            "project_path": "src/",
            "output_formats": "json,html"
        }
        
        mock_result = {
            "status": "success",
            "reports": {"json": "path/to/json", "html": "path/to/html"},
            "coverage_summary": {"line_coverage": 90.0},
            "quality_metrics": {"quality_score": 8.5, "technical_debt": "low"}
        }
        self.mock_ae.coverage_analyzer.analyze_project.return_value = mock_result
        
        with patch('os.path.exists', return_value=True):
            result_context = self.ops.generate_coverage_report(context, parameters)
            
        self.assertEqual(result_context["action_result"]["status"], "success")
        self.assertIn("90.0%", result_context["action_result"]["message"])
        self.assertIn("品質スコア: 8.5/10", result_context["action_result"]["message"])

if __name__ == "__main__":
    unittest.main()
