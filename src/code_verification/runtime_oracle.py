# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple


_ASSERTION_KEYS = {
    "return",
    "stdout",
    "stderr",
    "files",
    "http_requests",
}


def _parse_json_object(value: Any) -> Tuple[Dict[str, Any] | None, str | None]:
    if not isinstance(value, str):
        return None, "expected value is not a string"
    text = value.strip()
    if not text:
        return None, "expected value is empty"
    if not text.startswith("{"):
        return None, None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"expected JSON is invalid: {exc.msg}"
    if not isinstance(parsed, dict):
        return None, "expected JSON must be an object"
    return parsed, None


def _as_string_list(value: Any, path: str) -> Tuple[List[str], List[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], [f"{path} must be a list"]
    items: List[str] = []
    issues: List[str] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            items.append(item)
        else:
            issues.append(f"{path}[{index}] must be a string")
    return items, issues


def _normalize_text_assertion(value: Any, path: str) -> Tuple[Dict[str, Any], List[str]]:
    if value is None:
        return {}, []
    if not isinstance(value, dict):
        return {}, [f"{path} must be an object"]
    normalized: Dict[str, Any] = {}
    issues: List[str] = []
    for key in ("contains", "not_contains"):
        items, item_issues = _as_string_list(value.get(key), f"{path}.{key}")
        if items:
            normalized[key] = items
        issues.extend(item_issues)
    unknown = sorted(k for k in value if k not in {"contains", "not_contains"})
    for key in unknown:
        issues.append(f"{path}.{key} is not a supported assertion")
    return normalized, issues


def _normalize_files(value: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["files must be a list"]
    normalized: List[Dict[str, Any]] = []
    issues: List[str] = []
    for index, item in enumerate(value):
        path = f"files[{index}]"
        if not isinstance(item, dict):
            issues.append(f"{path} must be an object")
            continue
        file_path = item.get("path")
        if not isinstance(file_path, str) or not file_path.strip():
            issues.append(f"{path}.path must be a non-empty string")
            continue
        text_assertion, text_issues = _normalize_text_assertion(
            {key: item.get(key) for key in ("contains", "not_contains") if key in item},
            path,
        )
        file_contract = {"path": file_path.strip()}
        file_contract.update(text_assertion)
        normalized.append(file_contract)
        issues.extend(text_issues)
        unknown = sorted(k for k in item if k not in {"path", "contains", "not_contains"})
        for key in unknown:
            issues.append(f"{path}.{key} is not a supported assertion")
    return normalized, issues


def _normalize_http_requests(value: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["http_requests must be a list"]
    normalized: List[Dict[str, Any]] = []
    issues: List[str] = []
    for index, item in enumerate(value):
        path = f"http_requests[{index}]"
        if not isinstance(item, dict):
            issues.append(f"{path} must be an object")
            continue
        request: Dict[str, Any] = {}
        for key in ("method", "url"):
            value_at_key = item.get(key)
            if isinstance(value_at_key, str) and value_at_key.strip():
                request[key] = value_at_key.strip()
        if not request:
            issues.append(f"{path} must include method or url")
            continue
        normalized.append(request)
        unknown = sorted(k for k in item if k not in {"method", "url"})
        for key in unknown:
            issues.append(f"{path}.{key} is not a supported assertion")
    return normalized, issues


def normalize_runtime_oracle_contract(value: Any) -> Tuple[Dict[str, Any], List[str]]:
    if not isinstance(value, dict):
        return {}, ["runtime_oracle must be an object"]

    issues: List[str] = []
    contract: Dict[str, Any] = {}

    if "return" in value:
        contract["return"] = value["return"]

    stdout, stdout_issues = _normalize_text_assertion(value.get("stdout"), "stdout")
    stderr, stderr_issues = _normalize_text_assertion(value.get("stderr"), "stderr")
    files, file_issues = _normalize_files(value.get("files"))
    http_requests, http_issues = _normalize_http_requests(value.get("http_requests"))

    if stdout:
        contract["stdout"] = stdout
    if stderr:
        contract["stderr"] = stderr
    if files:
        contract["files"] = files
    if http_requests:
        contract["http_requests"] = http_requests

    issues.extend(stdout_issues)
    issues.extend(stderr_issues)
    issues.extend(file_issues)
    issues.extend(http_issues)

    unknown = sorted(k for k in value if k not in _ASSERTION_KEYS)
    for key in unknown:
        issues.append(f"{key} is not a supported runtime_oracle assertion")
    if not contract and not issues:
        issues.append("runtime_oracle has no assertions")
    return contract, issues


def summarize_runtime_oracles(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize explicit runtime oracle coverage from StructuredSpec test cases.

    The extractor intentionally accepts only explicit JSON contracts. Natural
    language expectations remain visible as unverified cases instead of being
    guessed through keyword matching.
    """
    test_cases = spec.get("test_cases", []) if isinstance(spec, dict) else []
    cases: List[Dict[str, Any]] = []
    issues: List[str] = []

    for index, test_case in enumerate(test_cases):
        if not isinstance(test_case, dict):
            issues.append(f"test_cases[{index}] must be an object")
            continue
        case_id = str(test_case.get("id") or f"tc_{index + 1}")
        scenario = str(test_case.get("scenario") or "")
        parsed, parse_issue = _parse_json_object(test_case.get("expected"))
        if parsed is None:
            status = "invalid" if parse_issue else "unverified"
            reason = parse_issue or "expected is not an explicit JSON runtime_oracle contract"
            case_summary = {
                "id": case_id,
                "scenario": scenario,
                "status": status,
                "reason": reason,
            }
            cases.append(case_summary)
            if status == "invalid":
                issues.append(f"{case_id}: {reason}")
            continue

        oracle = parsed.get("runtime_oracle")
        if oracle is None:
            cases.append({
                "id": case_id,
                "scenario": scenario,
                "status": "unverified",
                "reason": "expected JSON does not include runtime_oracle",
            })
            continue

        contract, contract_issues = normalize_runtime_oracle_contract(oracle)
        if contract_issues:
            cases.append({
                "id": case_id,
                "scenario": scenario,
                "status": "invalid",
                "contract": contract,
                "issues": contract_issues,
            })
            issues.extend(f"{case_id}: {issue}" for issue in contract_issues)
            continue

        cases.append({
            "id": case_id,
            "scenario": scenario,
            "status": "ready",
            "contract": contract,
        })

    ready_count = sum(1 for case in cases if case.get("status") == "ready")
    invalid_count = sum(1 for case in cases if case.get("status") == "invalid")
    unverified_count = sum(1 for case in cases if case.get("status") == "unverified")
    return {
        "case_count": len(test_cases),
        "ready_count": ready_count,
        "invalid_count": invalid_count,
        "unverified_count": unverified_count,
        "has_explicit_oracles": ready_count > 0,
        "valid": invalid_count == 0,
        "issues": issues,
        "cases": cases,
    }
