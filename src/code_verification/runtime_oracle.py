# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple


_ASSERTION_KEYS = {
    "method_args",
    "fixtures",
    "return",
    "stdout",
    "stderr",
    "files",
    "http_requests",
}


_SUPPORTED_ARG_TYPES = (str, int, float, bool)


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


def _normalize_method_args(value: Any) -> Tuple[List[Any], List[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["method_args must be a list"]
    args: List[Any] = []
    issues: List[str] = []
    for index, item in enumerate(value):
        if item is None or isinstance(item, _SUPPORTED_ARG_TYPES):
            args.append(item)
        else:
            issues.append(f"method_args[{index}] must be a string, number, boolean, or null")
    return args, issues


def _normalize_fixtures(value: Any) -> Tuple[List[Dict[str, str]], List[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["fixtures must be a list"]
    fixtures: List[Dict[str, str]] = []
    issues: List[str] = []
    for index, item in enumerate(value):
        path = f"fixtures[{index}]"
        if not isinstance(item, dict):
            issues.append(f"{path} must be an object")
            continue
        fixture_path = item.get("path")
        content = item.get("content")
        if not isinstance(fixture_path, str) or not fixture_path.strip():
            issues.append(f"{path}.path must be a non-empty string")
            continue
        if not isinstance(content, str):
            issues.append(f"{path}.content must be a string")
            continue
        fixtures.append({"path": fixture_path.strip(), "content": content})
        unknown = sorted(k for k in item if k not in {"path", "content"})
        for key in unknown:
            issues.append(f"{path}.{key} is not supported")
    return fixtures, issues


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

    method_args, method_arg_issues = _normalize_method_args(value.get("method_args"))
    fixtures, fixture_issues = _normalize_fixtures(value.get("fixtures"))
    if "return" in value:
        contract["return"] = value["return"]

    stdout, stdout_issues = _normalize_text_assertion(value.get("stdout"), "stdout")
    stderr, stderr_issues = _normalize_text_assertion(value.get("stderr"), "stderr")
    files, file_issues = _normalize_files(value.get("files"))
    http_requests, http_issues = _normalize_http_requests(value.get("http_requests"))

    if method_args:
        contract["method_args"] = method_args
    if fixtures:
        contract["fixtures"] = fixtures
    if stdout:
        contract["stdout"] = stdout
    if stderr:
        contract["stderr"] = stderr
    if files:
        contract["files"] = files
    if http_requests:
        contract["http_requests"] = http_requests

    issues.extend(method_arg_issues)
    issues.extend(fixture_issues)
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


def _csharp_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _csharp_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return _csharp_string_literal(value)
    raise TypeError(f"Unsupported oracle literal type: {type(value).__name__}")


def _render_text_assertions(expression: str, assertion: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for expected in assertion.get("contains", []) or []:
        lines.append(f"        Assert.Contains({_csharp_string_literal(expected)}, {expression});")
    for expected in assertion.get("not_contains", []) or []:
        lines.append(f"        Assert.DoesNotContain({_csharp_string_literal(expected)}, {expression});")
    return lines


def build_runtime_oracle_test_code(module_name: str, contract: Dict[str, Any]) -> str:
    method_args = ", ".join(_csharp_literal(arg) for arg in contract.get("method_args", []) or [])
    fixtures = contract.get("fixtures", []) or []
    file_assertions = contract.get("files", []) or []
    has_stdout = bool(contract.get("stdout"))
    call_prefix = "var result = " if "return" in contract else ""
    lines: List[str] = [
        "using System;",
        "using System.Globalization;",
        "using System.IO;",
        "using Xunit;",
        "",
        "public class RuntimeOracleTest",
        "{",
        "    [Fact]",
        "    public void ExplicitRuntimeOraclePasses()",
        "    {",
        '        var root = Path.Combine(Path.GetTempPath(), "runtime-oracle-" + Guid.NewGuid().ToString("N"));',
        "        Directory.CreateDirectory(root);",
        "        var previousDirectory = Directory.GetCurrentDirectory();",
        "        var originalOut = Console.Out;",
        "        using var capturedOut = new StringWriter(CultureInfo.InvariantCulture);",
        "        try",
        "        {",
        "            Directory.SetCurrentDirectory(root);",
    ]
    for fixture in fixtures:
        lines.append(
            f"            File.WriteAllText({_csharp_string_literal(fixture['path'])}, {_csharp_string_literal(fixture['content'])});"
        )
    if has_stdout:
        lines.append("            Console.SetOut(capturedOut);")
    lines.extend([
        "",
        f"            {call_prefix}new GeneratedProcessor().{module_name}({method_args});",
    ])
    if "return" in contract:
        lines.append(f"            Assert.Equal({_csharp_literal(contract['return'])}, result);")
    if has_stdout:
        lines.append("            var stdout = capturedOut.ToString();")
        lines.extend(_render_text_assertions("stdout", contract["stdout"]))
    for file_assertion in file_assertions:
        file_path = _csharp_string_literal(file_assertion["path"])
        lines.append(f"            Assert.True(File.Exists({file_path}), \"Expected output file to exist: {file_assertion['path']}\");")
        if file_assertion.get("contains") or file_assertion.get("not_contains"):
            file_var = f"fileText{len(lines)}"
            lines.append(f"            var {file_var} = File.ReadAllText({file_path});")
            lines.extend(_render_text_assertions(file_var, file_assertion))
    lines.extend([
        "        }",
        "        finally",
        "        {",
        "            Console.SetOut(originalOut);",
        "            Directory.SetCurrentDirectory(previousDirectory);",
        "            if (Directory.Exists(root))",
        "                Directory.Delete(root, recursive: true);",
        "        }",
        "    }",
        "}",
    ])
    return "\n".join(lines)


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
            dependencies=dependencies or [],
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
