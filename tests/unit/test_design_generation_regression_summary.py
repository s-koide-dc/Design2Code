# -*- coding: utf-8 -*-
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.design.run_design_generation_regression import (
    QUALITY_DESIGNS,
    SMOKE_DESIGNS,
    _resolve_designs,
    runtime_oracle_requirement_issues,
    summarize_runtime_oracle_failures,
)


class TestDesignGenerationRegressionSummary(unittest.TestCase):

    def test_smoke_profile_is_a_representative_subset_of_quality_profile(self):
        self.assertEqual(4, len(SMOKE_DESIGNS))
        self.assertTrue(set(SMOKE_DESIGNS).issubset(QUALITY_DESIGNS))

    def test_explicit_designs_override_selected_profile(self):
        resolved = _resolve_designs(
            SimpleNamespace(
                designs=["scenarios/AggregationSummary.design.md"],
                profile="smoke",
            )
        )

        self.assertEqual([Path("scenarios/AggregationSummary.design.md")], resolved)

    def test_quality_profile_is_selected_when_no_design_is_specified(self):
        resolved = _resolve_designs(SimpleNamespace(designs=None, profile="quality"))

        self.assertEqual([Path(item) for item in QUALITY_DESIGNS], resolved)

    def test_runtime_oracle_requirement_accepts_fully_executed_cases(self):
        issues = runtime_oracle_requirement_issues(
            {"case_count": 2, "ready_count": 2, "unverified_count": 0, "invalid_count": 0},
            {"requested": True, "valid": True, "case_count": 2, "passed": 2, "failed": 0},
        )

        self.assertEqual([], issues)

    def test_runtime_oracle_requirement_reports_missing_and_unverified_cases(self):
        issues = runtime_oracle_requirement_issues(
            {"case_count": 2, "ready_count": 1, "unverified_count": 1, "invalid_count": 0},
            {"requested": True, "valid": True, "case_count": 1, "passed": 1, "failed": 0},
        )

        self.assertIn("runtime_oracle has 1 unverified case(s)", issues)
        self.assertIn("runtime_oracle ready cases 1 do not match test cases 2", issues)

    def test_runtime_oracle_requirement_reports_unrequested_execution(self):
        issues = runtime_oracle_requirement_issues(
            {"case_count": 1, "ready_count": 1, "unverified_count": 0, "invalid_count": 0},
            {"requested": False, "valid": True, "case_count": 0, "passed": 0, "failed": 0},
        )

        self.assertIn("runtime_oracle execution was not requested", issues)
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
