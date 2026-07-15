# -*- coding: utf-8 -*-
import unittest
import json
from src.utils.nuget_client import NuGetClient

class TestNuGetClient(unittest.TestCase):

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def setUp(self):
        def fake_urlopen(url, timeout):
            del timeout
            if "YamlDotNet.Serialization" in url:
                return self.FakeResponse({
                    "data": [{"id": "YamlDotNet", "version": "16.2.0"}],
                })
            if "Newtonsoft.Json" in url:
                return self.FakeResponse({
                    "data": [{"id": "Newtonsoft.Json", "version": "13.0.3"}],
                })
            return self.FakeResponse({"data": []})

        self.client = NuGetClient(urlopen=fake_urlopen)

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
