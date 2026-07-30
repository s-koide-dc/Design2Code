from __future__ import annotations

import unittest

from scripts.validate.run_local_semantic_quality_gate import (
    SEMANTIC_TEST_MODULES,
    asset_dependent_integration_modules,
    test_modules,
)


class TestLocalSemanticQualityGate(unittest.TestCase):
    def test_runs_every_explicitly_asset_dependent_integration_test(self):
        excluded = asset_dependent_integration_modules()
        self.assertEqual(7, len(excluded))
        self.assertIn("tests.integration.test_documented_entrypoints", excluded)
        self.assertIn("tests.integration.test_vector_engine_real_model", excluded)

    def test_combined_suite_preserves_each_module_once(self):
        modules = test_modules()
        self.assertEqual(len(modules), len(set(modules)))
        self.assertTrue(set(SEMANTIC_TEST_MODULES).issubset(modules))
        self.assertTrue(set(asset_dependent_integration_modules()).issubset(modules))
