
import unittest
import json
from unittest.mock import MagicMock, patch
from src.cicd_integrator.cicd_integrator import CICDIntegrator, AzureDevOpsGenerator, JenkinsGenerator, QualityGateManager

class TestCICDIntegrator(unittest.TestCase):
    def setUp(self):
        self.config = {
            "language_configs": {
                "csharp": {
                    "package_restore": "dotnet restore",
                    "build_command": "dotnet build",
                    "test_command": "dotnet test"
                },
                "python": {
                    "package_restore": "pip install -r requirements.txt",
                    "test_command": "python -m pytest"
                },
                "javascript": {
                    "package_restore": "npm install",
                    "build_command": "npm run build",
                    "test_command": "npm test"
                }
            },
            "quality_gates": {
                "test_coverage_threshold": 80
            }
        }
    
    def test_azure_devops_generator_csharp(self):
        generator = AzureDevOpsGenerator(self.config)
        project_info = {"language": "csharp", "name": "TestProject"}
        result = generator.generate_pipeline(project_info, {})
        
        pipeline = result["pipeline"]
        self.assertIn("steps", pipeline)
        steps = pipeline["steps"]
        
        # Check for essential steps
        self.assertTrue(any(s.get("task") == "UseDotNet@2" for s in steps))
        self.assertTrue(any("dotnet restore" in s.get("script", "") for s in steps))
        self.assertTrue(any("dotnet build" in s.get("script", "") for s in steps))
        
        # Check config generation
        config_files = generator.generate_config_files(result, project_info)
        self.assertEqual(len(config_files), 1)
        self.assertEqual(config_files[0]["path"], "azure-pipelines.yml")
        self.assertIn("vmImage: ubuntu-latest", config_files[0]["content"])

    def test_jenkins_generator_csharp(self):
        generator = JenkinsGenerator(self.config)
        project_info = {"language": "csharp", "name": "TestProject"}
        result = generator.generate_pipeline(project_info, {})
        
        # Check config generation
        config_files = generator.generate_config_files(result, project_info)
        self.assertEqual(len(config_files), 1)
        self.assertEqual(config_files[0]["path"], "Jenkinsfile")
        content = config_files[0]["content"]
        self.assertIn("pipeline {", content)
        self.assertIn("stage('Build')", content)
        self.assertIn("dotnet build", content)

    def test_quality_gate_manager(self):
        manager = QualityGateManager(self.config)
        
        # Test numeric comparison
        gate = {"condition": "coverage >= 80"}
        self.assertTrue(manager._evaluate_condition("coverage >= 80", {"coverage": 85}))
        self.assertFalse(manager._evaluate_condition("coverage >= 80", {"coverage": 75}))
        
        # Test boolean
        self.assertTrue(manager._evaluate_condition("all_tests_pass == True", {"all_tests_pass": True}))
        
        # Test complex setup and evaluation
        gates = manager.setup_gates({"test_coverage_threshold": 90}, "csharp")
        coverage_gate = next(g for g in gates if g["name"] == "coverage_check")
        self.assertEqual(coverage_gate["condition"], "coverage >= 90")

    def test_azure_devops_generator_python(self):
        generator = AzureDevOpsGenerator(self.config)
        project_info = {"language": "python", "name": "PyProject"}
        result = generator.generate_pipeline(project_info, {})
        
        steps = result["pipeline"]["steps"]
        self.assertTrue(any(s.get("task") == "UsePythonVersion@0" for s in steps))
        self.assertTrue(any("pip install -r requirements.txt" in s.get("script", "") for s in steps))
        self.assertTrue(any("python -m pytest" in s.get("script", "") for s in steps))

    def test_azure_devops_generator_javascript(self):
        generator = AzureDevOpsGenerator(self.config)
        project_info = {"language": "javascript", "name": "JSProject"}
        result = generator.generate_pipeline(project_info, {})
        
        steps = result["pipeline"]["steps"]
        self.assertTrue(any(s.get("task") == "NodeTool@0" for s in steps))
        self.assertTrue(any("npm install" in s.get("script", "") for s in steps))
        self.assertTrue(any("npm test" in s.get("script", "") for s in steps))

    def test_jenkins_generator_multiple_languages(self):
        generator = JenkinsGenerator(self.config)
        
        # Python
        py_info = {"language": "python", "name": "PyProj"}
        py_res = generator.generate_pipeline(py_info, {})
        py_content = generator.generate_config_files(py_res, py_info)[0]["content"]
        self.assertIn("pip install -r requirements.txt", py_content)
        
        # JavaScript
        js_info = {"language": "javascript", "name": "JSProj"}
        js_res = generator.generate_pipeline(js_info, {})
        js_content = generator.generate_config_files(js_res, js_info)[0]["content"]
        self.assertIn("npm install", js_content)
        self.assertIn("npm run build", js_content)

    def test_quality_gate_manager_edge_cases(self):
        manager = QualityGateManager(self.config)
        
        # Test unknown metric
        self.assertFalse(manager._evaluate_condition("unknown_metric >= 10", {"coverage": 80}))
        
        # Test malformed condition
        self.assertFalse(manager._evaluate_condition("invalid condition", {"coverage": 80}))
        
        # Test other operators
        self.assertTrue(manager._evaluate_condition("smells < 5", {"smells": 3}))
        self.assertFalse(manager._evaluate_condition("smells < 5", {"smells": 5}))
        self.assertTrue(manager._evaluate_condition("smells <= 5", {"smells": 5}))
        self.assertTrue(manager._evaluate_condition("status == 'stable'", {"status": "stable"}))
        self.assertFalse(manager._evaluate_condition("status != 'stable'", {"status": "stable"}))

if __name__ == '__main__':
    unittest.main()