# -*- coding: utf-8 -*-
import unittest

from src.code_verification.runtime_oracle import (
    normalize_runtime_oracle_contract,
    summarize_runtime_oracles,
)
from src.design_parser.structured_parser import StructuredDesignParser


class TestRuntimeOracle(unittest.TestCase):
    def test_summarizes_explicit_runtime_oracle_from_expected_json(self):
        spec = {
            "test_cases": [
                {
                    "id": "tc_1",
                    "scenario": "filters output",
                    "expected": (
                        '{"runtime_oracle":{'
                        '"return":true,'
                        '"stdout":{"contains":["Alice"],"not_contains":["Bob"]},'
                        '"files":[{"path":"totals.csv","contains":["A,30"]}],'
                        '"http_requests":[{"method":"GET","url":"https://example.test/items"}]'
                        "}}"
                    ),
                }
            ]
        }

        summary = summarize_runtime_oracles(spec)

        self.assertTrue(summary["valid"], summary)
        self.assertEqual(1, summary["ready_count"])
        self.assertEqual(0, summary["invalid_count"])
        self.assertEqual(0, summary["unverified_count"])
        contract = summary["cases"][0]["contract"]
        self.assertTrue(contract["return"])
        self.assertEqual(["Alice"], contract["stdout"]["contains"])
        self.assertEqual(["Bob"], contract["stdout"]["not_contains"])
        self.assertEqual("totals.csv", contract["files"][0]["path"])
        self.assertEqual("GET", contract["http_requests"][0]["method"])

    def test_natural_language_expected_is_visible_as_unverified(self):
        spec = {
            "test_cases": [
                {
                    "id": "tc_1",
                    "scenario": "happy path",
                    "expected": "true",
                }
            ]
        }

        summary = summarize_runtime_oracles(spec)

        self.assertTrue(summary["valid"], summary)
        self.assertEqual(0, summary["ready_count"])
        self.assertEqual(1, summary["unverified_count"])
        self.assertEqual(
            "expected is not an explicit JSON runtime_oracle contract",
            summary["cases"][0]["reason"],
        )

    def test_invalid_expected_json_is_reported(self):
        spec = {
            "test_cases": [
                {
                    "id": "tc_1",
                    "scenario": "bad JSON",
                    "expected": '{"runtime_oracle":',
                }
            ]
        }

        summary = summarize_runtime_oracles(spec)

        self.assertFalse(summary["valid"], summary)
        self.assertEqual(1, summary["invalid_count"])
        self.assertTrue(summary["issues"])

    def test_rejects_unsupported_contract_keys(self):
        contract, issues = normalize_runtime_oracle_contract(
            {
                "return": True,
                "stdout": {"contains": ["ok"], "count": 1},
                "database": {"rows": 1},
            }
        )

        self.assertEqual({"return": True, "stdout": {"contains": ["ok"]}}, contract)
        self.assertIn("stdout.count is not a supported assertion", issues)
        self.assertIn("database is not a supported runtime_oracle assertion", issues)

    def test_structured_parser_preserves_explicit_oracle_json(self):
        markdown = """
# OracleModule
## 1. Purpose
Validate explicit runtime oracle.
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
1. [ACTION|DISPLAY|string|void|NONE] 値を表示する
### Test Cases
- **Scenario**: explicit oracle
- **Expected**: {"runtime_oracle":{"return":true,"stdout":{"contains":["done"]}}}
"""

        spec = StructuredDesignParser().parse_markdown(markdown)
        summary = summarize_runtime_oracles(spec)

        self.assertEqual(1, summary["ready_count"])
        self.assertTrue(summary["cases"][0]["contract"]["return"])


if __name__ == "__main__":
    unittest.main()
