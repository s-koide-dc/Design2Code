# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List


class SemanticAssertionError(ValueError):
    pass


def flatten_statements(statements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    flat: List[Dict[str, Any]] = []

    for stmt in statements or []:
        if not isinstance(stmt, dict):
            continue
        flat.append(stmt)

        stmt_type = stmt.get("type")
        if stmt_type == "if":
            flat.extend(flatten_statements(stmt.get("body", [])))
            flat.extend(flatten_statements(stmt.get("else_body", [])))
        elif stmt_type == "foreach" or stmt_type == "while":
            flat.extend(flatten_statements(stmt.get("body", [])))
        elif stmt_type == "try":
            flat.extend(flatten_statements(stmt.get("body", [])))
            flat.extend(flatten_statements(stmt.get("else_body", [])))

    return flat


def _collect_string_values(statement: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for key in ["method", "condition", "source", "value", "var_name", "out_var"]:
        val = statement.get(key)
        if isinstance(val, str):
            values.append(val)

    args = statement.get("args", [])
    if isinstance(args, list):
        for arg in args:
            if isinstance(arg, str):
                values.append(arg)

    return values


def evaluate_blueprint_contract(blueprint: Dict[str, Any], contract: Dict[str, Any]) -> List[str]:
    methods = blueprint.get("methods", []) if isinstance(blueprint, dict) else []
    if not methods:
        return ["blueprint has no methods"]

    body = methods[0].get("body", [])
    flat = flatten_statements(body)
    issues: List[str] = []

    if contract.get("disallow_placeholder_fetch"):
        for stmt in flat:
            if stmt.get("type") != "call":
                continue
            method = str(stmt.get("method", ""))
            if method.startswith("Enumerable.Empty"):
                issues.append("placeholder fetch (Enumerable.Empty) is used")
                break

    required_calls = contract.get("require_call_methods", [])
    for required in required_calls:
        found = False
        for stmt in flat:
            if stmt.get("type") == "call" and str(stmt.get("method", "")).endswith(required):
                found = True
                break
        if not found:
            issues.append(f"required call is missing: {required}")

    display_property = contract.get("require_display_property")
    if isinstance(display_property, str) and display_property:
        found_prop_display = False
        for stmt in flat:
            if stmt.get("type") != "call":
                continue
            if not str(stmt.get("method", "")).endswith("Console.WriteLine"):
                continue
            args = stmt.get("args", [])
            if any(isinstance(a, str) and f".{display_property}" in a for a in args):
                found_prop_display = True
                break
        if not found_prop_display:
            issues.append(f"displayed value does not include property: {display_property}")

    required_var_usages = contract.get("require_var_usage_from_methods", [])
    for rule in required_var_usages:
        source_method = str(rule.get("method_suffix", ""))
        if not source_method:
            continue
        source_vars: List[str] = []
        source_stmt_ids = set()
        for stmt in flat:
            if stmt.get("type") == "call" and str(stmt.get("method", "")).endswith(source_method):
                out_var = stmt.get("out_var")
                if isinstance(out_var, str) and out_var:
                    source_vars.append(out_var)
                    source_stmt_ids.add(id(stmt))

        if not source_vars:
            issues.append(f"source method for variable usage check is missing: {source_method}")
            continue

        used = False
        for stmt in flat:
            if id(stmt) in source_stmt_ids:
                continue
            values = _collect_string_values(stmt)
            for var_name in source_vars:
                if any(var_name in v for v in values):
                    used = True
                    break
            if used:
                break
        if not used:
            issues.append(f"output variable from {source_method} is not consumed")

    return issues


def evaluate_or_raise(blueprint: Dict[str, Any], contract: Dict[str, Any]) -> None:
    issues = evaluate_blueprint_contract(blueprint, contract)
    if issues:
        raise SemanticAssertionError("; ".join(issues))



