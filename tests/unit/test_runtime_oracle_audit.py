# -*- coding: utf-8 -*-
import unittest

from src.code_verification.runtime_oracle_executor import execute_runtime_oracles


class _Verifier:
    def verify_runtime(self, source_code, test_code, dependencies=None):
        return {"success": True, "stdout": "Alice\n", "summary": {"passed": 1}}


class TestRuntimeOracleAudit(unittest.TestCase):
    def test_successful_case_keeps_contract_stdout_and_fixture_hash(self):
        result = execute_runtime_oracles(
            source_code="class Sample {}",
            module_name="Sample",
            verifier=_Verifier(),
            oracle_summary={"cases": [{
                "id": "case_1", "scenario": "audit", "status": "ready",
                "contract": {"fixtures": [{"path": "users.json", "content": "[]"}], "stdout": {"contains": ["Alice"]}},
            }]},
        )
        case = result["results"][0]
        self.assertEqual("Alice\n", case["stdout"])
        self.assertEqual({"contains": ["Alice"]}, case["oracle_contract"]["stdout"])
        self.assertEqual("users.json", case["fixture_manifest"][0]["path"])
        self.assertEqual(64, len(case["fixture_manifest"][0]["sha256"]))
