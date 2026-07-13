# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List

from src.code_verification.semantic_assertions import evaluate_blueprint_contract, flatten_statements

DEFAULT_MAINTAINABILITY_THRESHOLDS: Dict[str, int] = {
    "max_operation_method_line_count": 80,
    "max_operation_method_try_count": 4,
    "max_operation_method_catch_count": 8,
    "total_line_count": 200,
    "blueprint_statement_count": 40,
}


def _has_marker(text: str, marker: str) -> bool:
    return isinstance(text, str) and text.find(marker) >= 0


def _collect_policy_issues(code: str, blueprint: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    if _has_marker(code, "// TODO"):
        issues.append("generated code contains TODO marker")
    if _has_marker(code, "NotImplementedException"):
        issues.append("generated code contains NotImplementedException")

    methods = blueprint.get("methods", []) if isinstance(blueprint, dict) else []
    body = methods[0].get("body", []) if methods else []
    for stmt in flatten_statements(body):
        if not isinstance(stmt, dict):
            continue
        raw_code = str(stmt.get("code") or "")
        if _has_marker(raw_code, "// TODO"):
            issues.append(f"blueprint node {stmt.get('node_id') or '<unknown>'} contains TODO marker")
        if _has_marker(raw_code, "NotImplementedException"):
            issues.append(f"blueprint node {stmt.get('node_id') or '<unknown>'} contains NotImplementedException")
    return issues


def _count_token_occurrences(text: str, token: str) -> int:
    if not text or not token:
        return 0
    count = 0
    start = 0
    while True:
        index = text.find(token, start)
        if index < 0:
            return count
        count += 1
        start = index + len(token)


def _coerce_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_type_name(name: str) -> str:
    return str(name or "").split("<", 1)[0].strip()


def _is_method_signature_line(line: str) -> bool:
    text = line.strip()
    access_modifiers = ("public ", "private ", "internal ", "protected ")
    if not text.startswith(access_modifiers):
        return False
    if " class " in f" {text} " or " struct " in f" {text} ":
        return False
    if "(" not in text or ")" not in text:
        return False
    if text.endswith(";"):
        return False
    return True


def _type_name_from_line(line: str) -> str:
    text = str(line or "").strip()
    if not text:
        return ""
    tokens = text.replace("{", " ").replace(":", " ").split()
    for index, token in enumerate(tokens):
        if token not in {"class", "struct"}:
            continue
        if index + 1 < len(tokens):
            return _normalize_type_name(tokens[index + 1])
        return ""
    return ""


def _class_name_from_line(line: str) -> str:
    text = str(line or "").strip()
    if not text:
        return ""
    tokens = text.replace("{", " ").replace(":", " ").split()
    for index, token in enumerate(tokens):
        if token != "class":
            continue
        if index + 1 < len(tokens):
            return _normalize_type_name(tokens[index + 1])
        return ""
    return ""


def _collect_class_names(code: str) -> List[str]:
    names: List[str] = []
    for line in (code or "").splitlines():
        name = _class_name_from_line(line)
        if name and name not in names:
            names.append(name)
    return names


def _collect_type_names(code: str) -> List[str]:
    names: List[str] = []
    for line in (code or "").splitlines():
        name = _type_name_from_line(line)
        if name and name not in names:
            names.append(name)
    return names


def _find_enclosing_type(lines: List[str], method_index: int) -> str:
    type_stack: List[Dict[str, Any]] = []
    depth = 0
    for index, line in enumerate(lines):
        if index > method_index:
            break
        type_name = _type_name_from_line(line)
        if type_name:
            type_stack.append({"name": type_name, "start_depth": depth, "opened": False})
        for char in line:
            if char == "{":
                depth += 1
                if type_stack and not type_stack[-1].get("opened"):
                    type_stack[-1]["opened"] = True
            elif char == "}":
                depth -= 1
        while type_stack and type_stack[-1].get("opened") and depth <= type_stack[-1]["start_depth"]:
            type_stack.pop()
    if type_stack:
        return str(type_stack[-1].get("name") or "")
    return ""


def _accessibility_from_signature(signature: str) -> str:
    text = str(signature or "").strip()
    for modifier in ("public", "private", "internal", "protected"):
        if text == modifier or text.startswith(f"{modifier} "):
            return modifier
    return ""


def _is_generated_helper_method(
    *,
    declaring_type: str,
    name: str,
    accessibility: str,
    is_constructor: bool,
) -> bool:
    if is_constructor:
        return False
    if declaring_type == "GeneratedErrorLog":
        return True
    if declaring_type == "GeneratedOperationResult":
        return True
    if declaring_type == "GeneratedProcessor" and accessibility != "public":
        return True
    helper_prefixes = (
        "ReadGenerated",
        "WriteGenerated",
        "SendGenerated",
        "RunGenerated",
        "Deserialize",
    )
    return any(str(name or "").startswith(prefix) for prefix in helper_prefixes)


def _extract_method_observations(code: str) -> List[Dict[str, Any]]:
    observations: List[Dict[str, Any]] = []
    lines = (code or "").splitlines()
    type_names = _collect_type_names(code or "")
    index = 0
    while index < len(lines):
        line = lines[index]
        if not _is_method_signature_line(line):
            index += 1
            continue

        signature = line.strip()
        name = signature.split("(", 1)[0].split()[-1]
        declaring_type = _find_enclosing_type(lines, index)
        accessibility = _accessibility_from_signature(signature)
        is_constructor = name in type_names
        kind = "constructor" if is_constructor else "method"
        if _is_generated_helper_method(
            declaring_type=declaring_type,
            name=name,
            accessibility=accessibility,
            is_constructor=is_constructor,
        ):
            kind = "helper"
        start_line = index + 1
        depth = 0
        seen_open = False
        body_lines: List[str] = []
        cursor = index
        while cursor < len(lines):
            current = lines[cursor]
            body_lines.append(current)
            for char in current:
                if char == "{":
                    depth += 1
                    seen_open = True
                elif char == "}":
                    depth -= 1
            cursor += 1
            if seen_open and depth <= 0:
                break

        body_text = "\n".join(body_lines)
        observations.append(
            {
                "name": name,
                "kind": kind,
                "declaring_class": declaring_type,
                "accessibility": accessibility,
                "start_line": start_line,
                "line_count": len(body_lines),
                "catch_count": _count_token_occurrences(body_text, "catch ("),
                "return_count": _count_token_occurrences(body_text, "return "),
                "try_count": _count_token_occurrences(body_text, "try"),
            }
        )
        index = max(cursor, index + 1)
    return observations


def _collect_maintainability_observations(code: str, blueprint: Dict[str, Any]) -> Dict[str, Any]:
    methods = _extract_method_observations(code or "")
    class_names = _collect_class_names(code or "")
    return _summarize_maintainability(
        methods=methods,
        class_count=len(class_names),
        total_line_count=len((code or "").splitlines()),
        blueprint=blueprint,
    )


def _method_observations_from_source_metrics(source_metrics: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    if not isinstance(source_metrics, dict):
        return []
    if source_metrics.get("status") == "success" and isinstance(source_metrics.get("metrics"), dict):
        metrics = source_metrics.get("metrics") or {}
    else:
        metrics = source_metrics
    members = metrics.get("members", [])
    if not isinstance(members, list):
        return []

    observations: List[Dict[str, Any]] = []
    for member in members:
        if not isinstance(member, dict):
            continue
        raw_kind = str(member.get("kind") or "method")
        name = str(member.get("name") or "")
        declaring_type = str(member.get("declaring_type") or member.get("declaringType") or "")
        accessibility = str(member.get("accessibility") or "")
        is_constructor = raw_kind == "constructor"
        kind = "constructor" if is_constructor else "method"
        if _is_generated_helper_method(
            declaring_type=declaring_type,
            name=name,
            accessibility=accessibility,
            is_constructor=is_constructor,
        ):
            kind = "helper"
        observations.append(
            {
                "name": name,
                "kind": kind,
                "declaring_class": declaring_type,
                "declaring_type_kind": member.get("declaring_type_kind") or member.get("declaringTypeKind"),
                "accessibility": accessibility,
                "start_line": _coerce_int(member.get("start_line") or member.get("startLine")),
                "line_count": _coerce_int(member.get("line_count") or member.get("lineCount")),
                "catch_count": _coerce_int(member.get("catch_count") or member.get("catchCount")),
                "return_count": _coerce_int(member.get("return_count") or member.get("returnCount")),
                "try_count": _coerce_int(member.get("try_count") or member.get("tryCount")),
            }
        )
    return observations


def _collect_maintainability_from_source_metrics(
    source_metrics: Dict[str, Any],
    blueprint: Dict[str, Any],
) -> Dict[str, Any]:
    metrics = source_metrics.get("metrics", source_metrics) if isinstance(source_metrics, dict) else {}
    if not isinstance(metrics, dict):
        metrics = {}
    methods = _method_observations_from_source_metrics(source_metrics)
    return _summarize_maintainability(
        methods=methods,
        class_count=_coerce_int(metrics.get("class_count") or metrics.get("classCount")),
        total_line_count=_coerce_int(metrics.get("total_line_count") or metrics.get("totalLineCount")),
        blueprint=blueprint,
    )


def _summarize_maintainability(
    *,
    methods: List[Dict[str, Any]],
    class_count: int,
    total_line_count: int,
    blueprint: Dict[str, Any],
) -> Dict[str, Any]:
    operation_methods = [method for method in methods if method.get("kind") == "method"]
    constructors = [method for method in methods if method.get("kind") == "constructor"]
    helper_methods = [method for method in methods if method.get("kind") == "helper"]
    method_count = len(methods)
    max_method_lines = max((m["line_count"] for m in methods), default=0)
    max_catch_count = max((m["catch_count"] for m in methods), default=0)
    max_try_count = max((m["try_count"] for m in methods), default=0)
    max_operation_method_lines = max((m["line_count"] for m in operation_methods), default=0)
    max_operation_try_count = max((m["try_count"] for m in operation_methods), default=0)
    max_operation_catch_count = max((m["catch_count"] for m in operation_methods), default=0)
    blueprint_methods = blueprint.get("methods", []) if isinstance(blueprint, dict) else []
    blueprint_statement_count = 0
    for method in blueprint_methods:
        if isinstance(method, dict):
            blueprint_statement_count += len(flatten_statements(method.get("body", [])))

    return {
        "method_count": method_count,
        "class_count": class_count,
        "constructor_count": len(constructors),
        "helper_method_count": len(helper_methods),
        "operation_method_count": len(operation_methods),
        "total_line_count": total_line_count,
        "max_method_line_count": max_method_lines,
        "max_method_try_count": max_try_count,
        "max_method_catch_count": max_catch_count,
        "max_operation_method_line_count": max_operation_method_lines,
        "max_operation_method_try_count": max_operation_try_count,
        "max_operation_method_catch_count": max_operation_catch_count,
        "blueprint_statement_count": blueprint_statement_count,
        "methods": methods,
    }


def _threshold_value(thresholds: Dict[str, int], metric: str) -> int | None:
    value = thresholds.get(metric)
    if isinstance(value, int):
        return value
    return None


def _append_threshold_finding(
    findings: List[Dict[str, Any]],
    *,
    maintainability: Dict[str, Any],
    thresholds: Dict[str, int],
    metric: str,
    message: str,
) -> None:
    limit = _threshold_value(thresholds, metric)
    if limit is None:
        return
    actual = maintainability.get(metric, 0)
    if not isinstance(actual, int):
        return
    if actual <= limit:
        return
    findings.append(
        {
            "metric": metric,
            "actual": actual,
            "limit": limit,
            "severity": "warning",
            "message": message,
        }
    )


def _evaluate_maintainability_findings(
    maintainability: Dict[str, Any],
    thresholds: Dict[str, int] | None,
) -> List[Dict[str, Any]]:
    effective_thresholds = dict(DEFAULT_MAINTAINABILITY_THRESHOLDS)
    if thresholds:
        effective_thresholds.update(thresholds)

    findings: List[Dict[str, Any]] = []
    _append_threshold_finding(
        findings,
        maintainability=maintainability,
        thresholds=effective_thresholds,
        metric="max_operation_method_line_count",
        message="operation method line count exceeds maintainability threshold",
    )
    _append_threshold_finding(
        findings,
        maintainability=maintainability,
        thresholds=effective_thresholds,
        metric="max_operation_method_try_count",
        message="operation method try block count exceeds maintainability threshold",
    )
    _append_threshold_finding(
        findings,
        maintainability=maintainability,
        thresholds=effective_thresholds,
        metric="max_operation_method_catch_count",
        message="operation method catch count exceeds maintainability threshold",
    )
    _append_threshold_finding(
        findings,
        maintainability=maintainability,
        thresholds=effective_thresholds,
        metric="total_line_count",
        message="generated code line count exceeds maintainability threshold",
    )
    _append_threshold_finding(
        findings,
        maintainability=maintainability,
        thresholds=effective_thresholds,
        metric="blueprint_statement_count",
        message="blueprint statement count exceeds maintainability threshold",
    )
    return findings


def evaluate_generation_quality(
    *,
    code: str,
    verification: Dict[str, Any],
    blueprint: Dict[str, Any],
    spec_issues: List[str] | None = None,
    source_metrics: Dict[str, Any] | None = None,
    fail_on_warnings: bool = True,
    fail_on_maintainability: bool = False,
    maintainability_thresholds: Dict[str, int] | None = None,
) -> Dict[str, Any]:
    """Evaluate generated-code quality beyond compile success.

    The checks intentionally consume structured compiler diagnostics and blueprint
    statements. Text marker checks are limited to exact generated-code sentinels
    that this project already treats as unresolved output.
    """
    issues: List[str] = []
    warnings = verification.get("warnings", []) if isinstance(verification, dict) else []
    errors = verification.get("errors", []) if isinstance(verification, dict) else []
    spec_issues = spec_issues or []

    if errors:
        issues.append(f"compiler errors present: {len(errors)}")
    if fail_on_warnings and warnings:
        codes = []
        for warning in warnings:
            code_value = warning.get("code") if isinstance(warning, dict) else None
            if code_value and code_value not in codes:
                codes.append(code_value)
        suffix = f" ({', '.join(codes)})" if codes else ""
        issues.append(f"compiler warnings present: {len(warnings)}{suffix}")
    if spec_issues:
        issues.append(f"spec audit issues present: {len(spec_issues)}")

    issues.extend(_collect_policy_issues(code or "", blueprint or {}))
    issues.extend(evaluate_blueprint_contract(blueprint or {}, {"disallow_placeholder_fetch": True}))
    if isinstance(source_metrics, dict) and source_metrics.get("status") == "success":
        maintainability = _collect_maintainability_from_source_metrics(source_metrics, blueprint or {})
        maintainability["analysis_source"] = "roslyn"
    else:
        maintainability = _collect_maintainability_observations(code or "", blueprint or {})
        maintainability["analysis_source"] = "python_fallback"
    maintainability["findings"] = _evaluate_maintainability_findings(
        maintainability,
        maintainability_thresholds,
    )
    if fail_on_maintainability and maintainability["findings"]:
        issues.append(f"maintainability findings present: {len(maintainability['findings'])}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "spec_issue_count": len(spec_issues),
        "checks": {
            "compiler_warnings": fail_on_warnings,
            "compiler_errors": True,
            "spec_issues": True,
            "unresolved_markers": True,
            "placeholder_fetch": True,
            "maintainability_observation": True,
            "maintainability_thresholds": fail_on_maintainability,
        },
        "maintainability": maintainability,
    }
