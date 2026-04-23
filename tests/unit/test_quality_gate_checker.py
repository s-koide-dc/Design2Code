import unittest
from unittest.mock import MagicMock, patch, mock_open
import xml.etree.ElementTree as ET
import sys
import os
from pathlib import Path

# Adjust path to import QualityGateChecker
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.cicd_integrator.quality_gate_checker import QualityGateChecker

class TestQualityGateChecker(unittest.TestCase):
    def setUp(self):
        self.checker = QualityGateChecker()

    def test_check_test_results_trx_failed(self):
        # Mock finding TRX file
        with patch.object(self.checker, '_find_files', return_value=['results.trx']), \
             patch('xml.etree.ElementTree.parse') as mock_parse:
            
            # Mock XML structure for Failed TRX
            mock_tree = MagicMock()
            mock_root = MagicMock()
            mock_parse.return_value = mock_tree
            mock_tree.getroot.return_value = mock_root
            
            # Setup Results element with Failed result
            mock_result = MagicMock()
            mock_result.get.return_value = 'Failed'
            mock_results_container = [mock_result]
            
            # Mock find behavior for namespace
            def side_effect_find(path, ns):
                if 'Results' in path:
                    return mock_results_container
                return None
            
            mock_root.find.side_effect = side_effect_find
            
            # Act
            result = self.checker._check_test_results()
            
            # Assert
            self.assertFalse(result['all_tests_pass'])

    def test_check_test_results_junit_failed(self):
        # Use side_effect function to return based on input pattern
        def side_effect_find_files(pattern):
            if "junit.xml" in pattern:
                return ['junit.xml']
            return []

        with patch.object(self.checker, '_find_files', side_effect=side_effect_find_files), \
             patch('xml.etree.ElementTree.parse') as mock_parse:
            
            mock_tree = MagicMock()
            mock_root = MagicMock()
            mock_parse.return_value = mock_tree
            mock_tree.getroot.return_value = mock_root
            
            # <testsuite failures="1" ...>
            mock_root.get.side_effect = lambda key, default: '1' if key == 'failures' else '0'
            
            result = self.checker._check_test_results()
            self.assertFalse(result['all_tests_pass'])

    def test_check_coverage_cobertura(self):
        def side_effect_find_files(pattern):
            if "coverage.xml" in pattern:
                return ['coverage.xml']
            return []

        with patch.object(self.checker, '_find_files', side_effect=side_effect_find_files), \
             patch('xml.etree.ElementTree.parse') as mock_parse:
            
            mock_tree = MagicMock()
            mock_root = MagicMock()
            mock_parse.return_value = mock_tree
            mock_tree.getroot.return_value = mock_root
            
            # <coverage line-rate="0.85">
            mock_root.get.return_value = '0.85'
            
            result = self.checker._check_coverage_results()
            self.assertEqual(result['coverage'], 85.0)

    def test_check_coverage_json_summary(self):
        def side_effect_find_files(pattern):
            if "coverage.json" in pattern:
                return ['coverage.json']
            return []

        with patch.object(self.checker, '_find_files', side_effect=side_effect_find_files), \
             patch('builtins.open', mock_open(read_data='{"summary": {"line_coverage": 75.5}}')):
            
            result = self.checker._check_coverage_results()
            self.assertEqual(result['coverage'], 75.5)

    def test_check_coverage_json_python(self):
        def side_effect_find_files(pattern):
            if "coverage.json" in pattern:
                return ['coverage.json']
            return []

        with patch.object(self.checker, '_find_files', side_effect=side_effect_find_files), \
             patch('builtins.open', mock_open(read_data='{"totals": {"percent_covered": 92.0}}')):
            
            result = self.checker._check_coverage_results()
            self.assertEqual(result['coverage'], 92.0)

    def test_collect_metrics_integration(self):
        # Test that _collect_metrics calls the parsing methods
        with patch.object(self.checker, '_check_test_results', return_value={'all_tests_pass': True}), \
             patch.object(self.checker, '_check_coverage_results', return_value={'coverage': 80.0}), \
             patch.object(self.checker, '_check_quality_results', return_value={'quality_score': 8.5}):
            
            metrics = self.checker._collect_metrics()
            
            self.assertTrue(metrics['all_tests_pass'])
            self.assertEqual(metrics['coverage'], 80.0)
            self.assertEqual(metrics['quality_score'], 8.5)

if __name__ == '__main__':
    unittest.main()