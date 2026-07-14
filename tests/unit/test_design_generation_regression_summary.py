# -*- coding: utf-8 -*-
import unittest

from scripts.design.run_design_generation_regression import summarize_runtime_oracle_failures


class TestDesignGenerationRegressionSummary(unittest.TestCase):
    def test_summarizes_failed_runtime_oracle_assertions(self):
        summary = summarize_runtime_oracle_failures({
            "results": [{
                "id": "tc_1",
                "scenario": "Default",
                "success": False,
                "error_type": None,
                "message": None,
                "failures": [{
                    "test_name": "RuntimeOracleTest.ExplicitRuntimeOraclePasses",
                    "message": "Assert.Contains() Failure\r\nNot found: Alice",
                    "stack_trace": "at RuntimeOracleTest.ExplicitRuntimeOraclePasses()\r\n--- end",
                }],
            }],
        })

        self.assertEqual(1, len(summary))
        self.assertEqual("tc_1", summary[0]["id"])
        self.assertEqual("Default", summary[0]["scenario"])
        self.assertIsNone(summary[0]["error_type"])
        self.assertEqual(
            "RuntimeOracleTest.ExplicitRuntimeOraclePasses",
            summary[0]["failures"][0]["test_name"],
        )
        self.assertEqual("Assert.Contains() Failure", summary[0]["failures"][0]["message"])
        self.assertEqual(
            "at RuntimeOracleTest.ExplicitRuntimeOraclePasses()",
            summary[0]["failures"][0]["stack_trace"],
        )

    def test_summarizes_invalid_runtime_oracle_contract_issues(self):
        summary = summarize_runtime_oracle_failures({
            "results": [],
            "issues": ["tc_1: return is not supported"],
        })

        self.assertEqual([{
            "id": None,
            "scenario": None,
            "error_type": "RUNTIME_ORACLE_CONTRACT_INVALID",
            "message": "tc_1: return is not supported",
            "failures": [],
        }], summary)

    def test_ignores_successful_runtime_oracle_results(self):
        summary = summarize_runtime_oracle_failures({
            "results": [{
                "id": "tc_1",
                "scenario": "Default",
                "success": True,
                "failures": [],
            }],
        })

        self.assertEqual([], summary)


if __name__ == "__main__":
    unittest.main()
