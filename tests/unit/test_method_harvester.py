# -*- coding: utf-8 -*-
import unittest
import os
import json
from src.code_synthesis.method_harvester import MethodHarvester
from src.config.config_manager import ConfigManager

class TestMethodHarvester(unittest.TestCase):

    def setUp(self):
        self.cm = ConfigManager()
        self.harvester = MethodHarvester(self.cm)

    def test_side_effect_detection(self):
        """副作用の検知ロジックのテスト"""
        
        # 1. 危険な操作を含むダミーデータ
        m_dangerous = {
            "name": "DeleteUserFile",
            "bodyCode": "public void DeleteUserFile(string path) { File.Delete(path); }",
            "modifiers": ["public"],
            "accessibility": "Public",
            "returnType": "void",
            "parameters": [{"name": "path", "type": "string"}],
            "metrics": {"cyclomaticComplexity": 1}
        }
        
        entry = self.harvester._create_method_entry(m_dangerous, "App.FileService")
        self.assertTrue(entry["has_side_effects"])
        self.assertIn("side-effect", entry["tags"])

        # 2. 安全な操作のみのデータ
        m_safe = {
            "name": "CalculateSum",
            "bodyCode": "public int CalculateSum(int a, int b) { return a + b; }",
            "modifiers": ["public"],
            "accessibility": "Public",
            "returnType": "int",
            "parameters": [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
            "metrics": {"cyclomaticComplexity": 1}
        }
        
        entry_safe = self.harvester._create_method_entry(m_safe, "App.MathService")
        self.assertFalse(entry_safe["has_side_effects"])
        self.assertNotIn("side-effect", entry_safe["tags"])

    def test_dependency_resolution_with_nuget(self):
        """NuGet API を使った未知の依存関係解決のテスト"""
        m_with_using = {
            "name": "ParseYaml",
            "bodyCode": "public void ParseYaml() { }",
            "modifiers": ["public"],
            "accessibility": "Public",
            "returnType": "void",
            "parameters": [],
            "metrics": {"cyclomaticComplexity": 1}
        }
        
        # YamlDotNet は static map にはないが NuGet にはある
        entry = self.harvester._create_method_entry(m_with_using, "App.YamlService", usings=["YamlDotNet.Serialization"])
        
        self.assertIn("YamlDotNet", entry["dependencies"])

    def test_create_method_entry_returns_none_for_pruned_api(self):
        """source harvest でも共通 policy により低価値 API を保存対象にしない"""
        entry = self.harvester._create_method_entry(
            {
                "name": "GetHashCode",
                "bodyCode": "public override int GetHashCode() { return 0; }",
                "modifiers": ["public"],
                "accessibility": "Public",
                "returnType": "int",
                "parameters": [],
                "metrics": {"cyclomaticComplexity": 1},
            },
            "App.ValueObject",
        )

        audit = self.harvester.policy.get_audit_summary()
        self.assertIsNone(entry)
        self.assertEqual(audit["prune_reasons"]["object_protocol"], 1)

if __name__ == '__main__':
    unittest.main()
