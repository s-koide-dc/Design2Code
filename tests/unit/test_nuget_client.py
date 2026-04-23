# -*- coding: utf-8 -*-
import unittest
from src.utils.nuget_client import NuGetClient

class TestNuGetClient(unittest.TestCase):

    def setUp(self):
        self.client = NuGetClient()

    def test_resolve_common_package(self):
        """有名なパッケージが解決できるか"""
        result = self.client.resolve_package("Newtonsoft.Json")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Newtonsoft.Json")

    def test_resolve_unknown_namespace(self):
        """未知のパッケージが解決できるか (YamlDotNet)"""
        result = self.client.resolve_package("YamlDotNet.Serialization")
        self.assertIsNotNone(result)
        # YamlDotNet がヒットすることを期待
        self.assertIn("YamlDotNet", result["name"])

    def test_resolve_invalid_query(self):
        """無効なクエリで None が返るか"""
        result = self.client.resolve_package("ThisIsHopefullyNotARealPackageName12345")
        self.assertIsNone(result)

    def test_caching(self):
        """キャッシュが機能しているか (2回目はAPIを叩かないはずだが動作で確認)"""
        res1 = self.client.resolve_package("Newtonsoft.Json")
        res2 = self.client.resolve_package("Newtonsoft.Json")
        self.assertEqual(res1, res2)
        self.assertIn("Newtonsoft.Json", self.client._cache)

if __name__ == '__main__':
    unittest.main()
