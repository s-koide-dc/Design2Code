# -*- coding: utf-8 -*-
import unittest
import os
from src.code_synthesis.dynamic_harvester import DynamicHarvester
from src.utils.nuget_client import NuGetClient
from src.config.config_manager import ConfigManager

class TestNuGetHarvesting(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()
        self.harvester = DynamicHarvester(self.config)
        self.nuget_client = NuGetClient(self.config)

    def test_harvest_csv_helper(self):
        """Test harvesting from CsvHelper if available in cache"""
        pkg_name = "CsvHelper"
        # Manual check for local version if API fails
        version = "33.1.0"
            
        dlls = self.nuget_client.get_package_dlls(pkg_name, version)
        if not dlls:
            self.skipTest(f"CsvHelper {version} DLLs not found in local cache")
            
        print(f"Found DLLs: {dlls}")
        methods = self.harvester.harvest_from_package(pkg_name, version)
        self.assertTrue(len(methods) > 0)
        
        # Check for a well-known method like Read
        read_methods = [m for m in methods if "Read" in m["name"]]
        self.assertTrue(len(read_methods) > 0)
        print(f"Harvested {len(methods)} methods from {pkg_name}")

if __name__ == "__main__":
    unittest.main()
