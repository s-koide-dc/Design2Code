# -*- coding: utf-8 -*-
import unittest
import os
import json
import shutil
from unittest.mock import patch, MagicMock
from src.code_synthesis.dependency_resolver import DependencyResolver

class TestDependencyResolver(unittest.TestCase):
    def setUp(self):
        # Mock config_manager
        class MockConfig:
            workspace_root = os.getcwd()
            dependency_map_path = os.path.join(workspace_root, "resources", "dependency_map.json")
            
        self.resolver = DependencyResolver(MockConfig())

    @patch('src.utils.nuget_client.NuGetClient.resolve_package')
    def test_analyze_build_errors(self, mock_resolve):
        """ビルドエラーからパッケージを特定できるか"""
        # YamlDotNet が見つからないエラーをシミュレート
        errors = [
            {
                "code": "CS0246",
                "message": "The type or namespace name 'YamlDotNet' could not be found...",
                "error_type": "SYMBOL_NOT_FOUND"
            }
        ]
        
        mock_resolve.return_value = {"name": "YamlDotNet", "version": "15.1.2"}
        
        missing_pkgs = self.resolver.analyze_build_errors(errors)
        
        self.assertEqual(len(missing_pkgs), 1)
        self.assertEqual(missing_pkgs[0]["name"], "YamlDotNet")
        mock_resolve.assert_called_with("YamlDotNet")

if __name__ == '__main__':
    unittest.main()
