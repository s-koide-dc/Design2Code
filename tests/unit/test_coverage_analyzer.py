# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import os
from src.coverage_analyzer.coverage_analyzer import GapAnalyzer

class TestGapAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = GapAnalyzer("csharp") # Language specific logic might be shared, testing general logic first

    def test_identify_missing_scenarios_fully_uncovered_method(self):
        # Arrange
        coverage_data = {
            "c:/project/MyClass.cs": {
                "MyClass": {
                    "MyMethod()": {
                        "Lines": {"10": 0, "11": 0},
                        "Branches": []
                    }
                }
            }
        }
        project_path = "c:/project"
        
        # Act
        scenarios = self.analyzer._identify_missing_scenarios(coverage_data, project_path)
        
        # Assert
        self.assertEqual(len(scenarios), 1)
        scenario = scenarios[0]
        self.assertEqual(scenario["target_method"], "MyMethod")
        self.assertEqual(scenario["priority"], "high")
        self.assertIn("基本動作", scenario["scenario"])
        self.assertIn("ShouldReturnResult_WhenValidInput", scenario["suggested_test"])

    def test_identify_missing_scenarios_partially_uncovered_method(self):
        # Arrange
        coverage_data = {
            "c:/project/MyClass.cs": {
                "MyClass": {
                    "MyMethod()": {
                        "Lines": {"10": 1, "11": 0}, # Line 11 is uncovered
                        "Branches": []
                    }
                }
            }
        }
        project_path = "c:/project"
        
        # Act
        scenarios = self.analyzer._identify_missing_scenarios(coverage_data, project_path)
        
        # Assert
        self.assertEqual(len(scenarios), 1)
        scenario = scenarios[0]
        self.assertEqual(scenario["target_method"], "MyMethod")
        self.assertEqual(scenario["priority"], "medium")
        self.assertIn("エッジケース", scenario["scenario"])
        self.assertIn("ShouldHandleEdgeCase", scenario["suggested_test"])

    def test_identify_missing_scenarios_fully_covered(self):
        # Arrange
        coverage_data = {
            "c:/project/MyClass.cs": {
                "MyClass": {
                    "MyMethod()": {
                        "Lines": {"10": 1, "11": 1},
                        "Branches": []
                    }
                }
            }
        }
        project_path = "c:/project"
        
        # Act
        scenarios = self.analyzer._identify_missing_scenarios(coverage_data, project_path)
        
        # Assert
        self.assertEqual(len(scenarios), 0)

class TestQualityAnalyzer(unittest.TestCase):
    def setUp(self):
        from src.coverage_analyzer.coverage_analyzer import QualityAnalyzer
        self.analyzer = QualityAnalyzer()

    def test_calculate_quality_score(self):
        # Arrange
        coverage_data = {
            "summary": {
                "line_coverage": 80.0,
                "branch_coverage": 70.0,
                "method_coverage": 90.0
            }
        }
        gap_analysis = {
            "analysis_summary": {
                "total_uncovered_files": 0,
                "high_priority_gaps": 0
            }
        }
        
        # Act
        score = self.analyzer._calculate_quality_score(coverage_data, gap_analysis)
        
        # Assert: 80% coverage with no gaps should be reasonably high (e.g. around 8.0)
        self.assertGreaterEqual(score, 7.5)
        self.assertLessEqual(score, 8.5)

    def test_calculate_quality_score_with_penalties(self):
        # Arrange
        coverage_data = {
            "summary": {
                "line_coverage": 50.0 # Low coverage
            }
        }
        gap_analysis = {
            "analysis_summary": {
                "total_uncovered_files": 5, # Penalty
                "high_priority_gaps": 2    # Penalty
            }
        }
        
        # Act
        score = self.analyzer._calculate_quality_score(coverage_data, gap_analysis)
        
        # Assert: Should be lower than base score (5.0)
        self.assertLess(score, 5.0)

    def test_calculate_maintainability_index_approximation(self):
        # Arrange
        coverage_data = {
            "summary": {
                "line_coverage": 90.0, # High coverage
                "total_lines": 100     # Small size
            }
        }
        gap_analysis = {}

        # Act
        mi = self.analyzer._calculate_maintainability_index(coverage_data, gap_analysis)

        # Assert: Small high-coverage code should have high MI
        self.assertGreater(mi, 80)

    def test_calculate_maintainability_index_low(self):
        # Arrange
        coverage_data = {
            "summary": {
                "line_coverage": 20.0,   # Low coverage
                "total_lines": 10000     # Huge size
            }
        }
        gap_analysis = {}

        # Act
        mi = self.analyzer._calculate_maintainability_index(coverage_data, gap_analysis)

        # Assert: Large low-coverage code should have lower MI
        self.assertLess(mi, 50)


class TestCoverageAnalyzer(unittest.TestCase):
    @patch('src.coverage_analyzer.coverage_analyzer.CoverageAnalyzer._load_coverage_config')
    @patch('src.coverage_analyzer.coverage_analyzer.CoverageAnalyzer._measure_coverage')
    @patch('src.coverage_analyzer.coverage_analyzer.CoverageAnalyzer._analyze_gaps')
    @patch('src.coverage_analyzer.coverage_analyzer.CoverageAnalyzer._analyze_quality')
    @patch('src.coverage_analyzer.coverage_analyzer.CoverageAnalyzer._generate_recommendations')
    @patch('src.coverage_analyzer.coverage_analyzer.CoverageAnalyzer._generate_reports')
    def test_analyze_project_flow(self, mock_gen_reports, mock_gen_recs, mock_analyze_qual, mock_analyze_gaps, mock_measure, mock_load_config):
        # Arrange
        mock_load_config.return_value = {}
        mock_measure.return_value = {"status": "success", "coverage_data": {}, "summary": {}}
        mock_analyze_gaps.return_value = {"uncovered_files": []}
        mock_analyze_qual.return_value = {}
        mock_gen_recs.return_value = []
        mock_gen_reports.return_value = {}
        
        from src.coverage_analyzer.coverage_analyzer import CoverageAnalyzer
        analyzer = CoverageAnalyzer()
        
        # Act
        result = analyzer.analyze_project("c:/test_project", "csharp")
        
        # Assert
        self.assertEqual(result["status"], "success")
        mock_measure.assert_called_once()
        mock_analyze_gaps.assert_called_once()
        mock_analyze_qual.assert_called_once()
        mock_gen_recs.assert_called_once()
        mock_gen_reports.assert_called_once()

    @patch('src.coverage_analyzer.coverage_analyzer.CoverageAnalyzer._load_coverage_config')
    @patch('src.coverage_analyzer.coverage_analyzer.CoverageAnalyzer._measure_coverage')
    def test_analyze_project_failure(self, mock_measure, mock_load_config):
        # Arrange
        mock_load_config.return_value = {}
        mock_measure.return_value = {"status": "error", "message": "Failed"}
        
        from src.coverage_analyzer.coverage_analyzer import CoverageAnalyzer
        analyzer = CoverageAnalyzer()
        
        # Act
        result = analyzer.analyze_project("c:/test_project", "csharp")
        
        # Assert
        self.assertEqual(result["status"], "error")


class TestCSharpCoverageCollector(unittest.TestCase):
    def setUp(self):
        from src.coverage_analyzer.coverage_analyzer import CSharpCoverageCollector
        self.config = {"tool": "coverlet"}
        self.collector = CSharpCoverageCollector(self.config)

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    def test_collect_coverage_success(self, mock_json_load, mock_file_open, mock_exists, mock_subprocess):
        # Arrange
        mock_subprocess.return_value = MagicMock(returncode=0)
        mock_exists.return_value = True
        
        # Mocking Coverlet JSON output structure
        mock_reponse_data = {
            "c:/project/File.cs": {
                "Class": {
                    "Method": {
                        "Lines": {"1": 1, "2": 0},
                        "Branches": []
                    }
                }
            }
        }
        mock_json_load.return_value = mock_reponse_data
        
        # Act
        result = self.collector.collect_coverage("c:/project", {})
        
        # Assert
        self.assertEqual(result["status"], "success")
        self.assertIn("coverage_data", result)
        self.assertIn("summary", result)
        summary = result["summary"]
        self.assertEqual(summary["total_lines"], 2)
        self.assertEqual(summary["covered_lines"], 1)
        self.assertEqual(summary["line_coverage"], 50.0)

    @patch('subprocess.run')
    def test_collect_coverage_command_failure(self, mock_subprocess):
        # Arrange
        mock_subprocess.return_value = MagicMock(returncode=1, stderr="Error")
        
        # Act
        result = self.collector.collect_coverage("c:/project", {})
        
        # Assert
        self.assertEqual(result["status"], "error")
        self.assertIn("Error", result["message"])


class TestRecommendationEngine(unittest.TestCase):
    def setUp(self):
        from src.coverage_analyzer.coverage_analyzer import RecommendationEngine
        self.engine = RecommendationEngine("csharp")

    def test_generate_recommendations(self):
        # Arrange
        gap_analysis = {
            "uncovered_files": [
                {
                    "file": "File.cs",
                    "uncovered_methods": ["MethodA"],
                    "priority": "high"
                }
            ],
            "missing_test_scenarios": []
        }
        quality_metrics = {"technical_debt": "low"}
        
        # Act
        recommendations = self.engine.generate(gap_analysis, quality_metrics)
        
        # Assert
        self.assertEqual(len(recommendations), 1)
        rec = recommendations[0]
        self.assertEqual(rec["type"], "add_test")
        self.assertIn("MethodA", rec["description"])
        self.assertIn("[Fact]", rec["suggested_test_code"]) # Check if C# template is used

    def test_generate_refactor_recommendation(self):
        # Arrange
        gap_analysis = {}
        quality_metrics = {"technical_debt": "high"}
        
        # Act
        recommendations = self.engine.generate(gap_analysis, quality_metrics)
        
        # Assert
        self.assertTrue(any(r["type"] == "refactor" for r in recommendations))


class TestReporters(unittest.TestCase):
    def test_json_reporter(self):
        # Arrange
        from src.coverage_analyzer.coverage_analyzer import JSONReporter
        reporter = JSONReporter()
        
        with patch('builtins.open', mock_open()) as mock_file:
            # Act
            reporter.generate("output.json", {}, {}, {}, [])
            
            # Assert
            mock_file.assert_called_with("output.json", 'w', encoding='utf-8')
            # Check if json.dump was called (file write happened)
            handle = mock_file()
            handle.write.assert_called()

    def test_text_reporter_summary(self):
        # Arrange
        from src.coverage_analyzer.coverage_analyzer import TextReporter
        reporter = TextReporter()
        coverage_result = {"summary": {"line_coverage": 80.0}}
        gap_analysis = {
            "uncovered_files": [{}, {}],
            "analysis_summary": {"total_uncovered_files": 2}
        }
        recommendations = [{"type": "add_test"}]
        
        # Act
        summary = reporter.generate_summary(coverage_result, gap_analysis, recommendations)
        
        # Assert
        self.assertIn("80.0%", summary)
        self.assertIn("2", summary) # Uncovered files count

if __name__ == '__main__':
    unittest.main()