# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List

from src.code_verification.runtime_oracle_test_builder import build_runtime_oracle_test_code


def merge_runtime_oracle_dependencies(
    dependencies: List[Dict[str, str]],
    contract: Dict[str, Any],
) -> List[Dict[str, str]]:
    merged = list(dependencies)
    existing = {str(dep.get("name") or "") for dep in merged if isinstance(dep, dict)}
    if contract.get("sqlite") or contract.get("db_assertions"):
        if "Dapper" not in existing:
            merged.append({"name": "Dapper", "version": "2.1.35"})
            existing.add("Dapper")
        if "Microsoft.Data.Sqlite" not in existing:
            merged.append({"name": "Microsoft.Data.Sqlite", "version": "10.0.0"})
    return merged


def execute_runtime_oracles(
    *,
    source_code: str,
    module_name: str,
    oracle_summary: Dict[str, Any],
    verifier: Any,
    dependencies: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    cases = oracle_summary.get("cases", []) if isinstance(oracle_summary, dict) else []
    results: List[Dict[str, Any]] = []
    ready_cases = [case for case in cases if isinstance(case, dict) and case.get("status") == "ready"]
    for case in ready_cases:
        contract = case.get("contract") if isinstance(case.get("contract"), dict) else {}
        test_code = build_runtime_oracle_test_code(module_name, contract)
        runtime_result = verifier.verify_runtime(
            source_code,
            test_code,
            dependencies=merge_runtime_oracle_dependencies(dependencies or [], contract),
        )
        results.append({
            "id": case.get("id"),
            "scenario": case.get("scenario"),
            "success": bool(runtime_result.get("success")),
            "summary": runtime_result.get("summary", {}),
            "failures": runtime_result.get("failures", []),
            "error_type": runtime_result.get("error_type"),
            "message": runtime_result.get("message") or runtime_result.get("error"),
        })

    failed = [result for result in results if not result.get("success")]
    return {
        "requested": True,
        "case_count": len(ready_cases),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "valid": not failed,
        "results": results,
    }
