# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
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
        elif stmt_type == "try" or stmt_type == "try_catch":
            flat.extend(flatten_statements(stmt.get("body", [])))
            flat.extend(flatten_statements(stmt.get("else_body", [])))
            flat.extend(flatten_statements(stmt.get("catch_body", [])))

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


def _normalize_intent(value: Any) -> str:
    """Return a canonical intent value without inferring meaning from text."""
    return value.strip().upper() if isinstance(value, str) else ""


def build_predicate_preservation_contract(structured_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Build structural predicate requirements from explicit LINQ step logic.

    The design contract is authoritative only when it supplies a non-empty
    structured ``logic`` list. Natural-language text is intentionally not used
    to invent predicates here.
    """
    requirements: List[Dict[str, Any]] = []
    steps = structured_spec.get("steps", []) if isinstance(structured_spec, dict) else []
    for step in steps:
        if not isinstance(step, dict) or _normalize_intent(step.get("intent")) != "LINQ":
            continue
        node_id = step.get("id")
        goals = step.get("logic")
        if isinstance(node_id, str) and node_id and isinstance(goals, list) and goals:
            requirements.append({"node_id": node_id, "goals": copy.deepcopy(goals)})
    return {"require_predicate_goals": requirements}


def _validate_structured_contract(contract: Dict[str, Any]) -> List[str]:
    """Validate the shape of contracts that consume blueprint provenance."""
    issues: List[str] = []
    required_intents = contract.get("require_intents", [])
    if not isinstance(required_intents, list) or not all(isinstance(item, str) and item.strip() for item in required_intents):
        issues.append("require_intents must be a list of non-empty intent names")

    required_nodes = contract.get("require_node_intents", [])
    if not isinstance(required_nodes, list):
        issues.append("require_node_intents must be a list")
    else:
        for item in required_nodes:
            if not isinstance(item, dict):
                issues.append("require_node_intents entries must be objects")
                continue
            if not isinstance(item.get("node_id"), str) or not item["node_id"].strip():
                issues.append("require_node_intents entries require node_id")
            if not _normalize_intent(item.get("intent")):
                issues.append("require_node_intents entries require intent")

    required_dataflow = contract.get("require_dataflow", [])
    if not isinstance(required_dataflow, list):
        issues.append("require_dataflow must be a list")
    else:
        for item in required_dataflow:
            if not isinstance(item, dict):
                issues.append("require_dataflow entries must be objects")
                continue
            if not isinstance(item.get("source_node_id"), str) or not item["source_node_id"].strip():
                issues.append("require_dataflow entries require source_node_id")
            if not isinstance(item.get("consumer_node_id"), str) or not item["consumer_node_id"].strip():
                issues.append("require_dataflow entries require consumer_node_id")

    required_display_properties = contract.get("require_display_properties", [])
    if not isinstance(required_display_properties, list):
        issues.append("require_display_properties must be a list")
    else:
        for item in required_display_properties:
            if not isinstance(item, dict):
                issues.append("require_display_properties entries must be objects")
                continue
            if not isinstance(item.get("node_id"), str) or not item["node_id"].strip():
                issues.append("require_display_properties entries require node_id")
            if not isinstance(item.get("property"), str) or not item["property"].strip():
                issues.append("require_display_properties entries require property")

    required_predicates = contract.get("require_predicate_goals", [])
    if not isinstance(required_predicates, list):
        issues.append("require_predicate_goals must be a list")
    else:
        for item in required_predicates:
            if not isinstance(item, dict) or not isinstance(item.get("node_id"), str) or not isinstance(item.get("goals"), list):
                issues.append("require_predicate_goals entries require node_id and goals")
    return issues


def _evaluate_structured_provenance(
    statements: List[Dict[str, Any]],
    contract: Dict[str, Any],
) -> List[str]:
    """Evaluate explicit node and intent evidence carried by the blueprint.

    This deliberately uses synthesized IR provenance (``node_id`` and ``intent``)
    rather than inspecting generated C# fragments.  Contracts therefore remain
    stable if a renderer changes its spelling, local variable names, or layout.
    """
    issues = _validate_structured_contract(contract)
    if issues:
        return issues

    observed_intents = {
        _normalize_intent(statement.get("intent"))
        for statement in statements
        if _normalize_intent(statement.get("intent"))
    }
    for intent in contract.get("require_intents", []):
        normalized = _normalize_intent(intent)
        if normalized not in observed_intents:
            issues.append(f"required intent is missing: {normalized}")

    intents_by_node: Dict[str, set[str]] = {}
    for statement in statements:
        node_id = statement.get("node_id")
        intent = _normalize_intent(statement.get("intent"))
        if isinstance(node_id, str) and node_id.strip() and intent:
            intents_by_node.setdefault(node_id, set()).add(intent)

    for requirement in contract.get("require_node_intents", []):
        node_id = requirement["node_id"].strip()
        intent = _normalize_intent(requirement["intent"])
        if intent not in intents_by_node.get(node_id, set()):
            issues.append(f"required intent {intent} is missing for node: {node_id}")

    emitted_node_ids = {
        statement.get("node_id")
        for statement in statements
        if isinstance(statement.get("node_id"), str) and statement["node_id"]
    }
    observed_dataflow = {
        (source_node_id, statement.get("node_id"))
        for statement in statements
        if isinstance(statement.get("node_id"), str)
        for source_node_id in statement.get("input_node_ids", [])
        if isinstance(source_node_id, str) and source_node_id
    }
    for requirement in contract.get("require_dataflow", []):
        source_node_id = requirement["source_node_id"].strip()
        consumer_node_id = requirement["consumer_node_id"].strip()
        if source_node_id not in emitted_node_ids:
            issues.append(f"dataflow source node is not emitted: {source_node_id}")
        if consumer_node_id not in emitted_node_ids:
            issues.append(f"dataflow consumer node is not emitted: {consumer_node_id}")
        if (source_node_id, consumer_node_id) not in observed_dataflow:
            issues.append(f"required dataflow is missing: {source_node_id} -> {consumer_node_id}")

    displayed_properties = {
        (statement.get("node_id"), statement.get("display_property"))
        for statement in statements
        if isinstance(statement.get("node_id"), str)
        and isinstance(statement.get("display_property"), str)
        and statement["display_property"]
    }
    for requirement in contract.get("require_display_properties", []):
        node_id = requirement["node_id"].strip()
        property_name = requirement["property"].strip()
        if (node_id, property_name) not in displayed_properties:
            issues.append(f"required display property is missing: {node_id}.{property_name}")

    predicates_by_node = {
        statement.get("node_id"): statement.get("predicate_goals")
        for statement in statements
        if isinstance(statement.get("node_id"), str) and isinstance(statement.get("predicate_goals"), list)
    }
    for requirement in contract.get("require_predicate_goals", []):
        node_id = requirement["node_id"].strip()
        if predicates_by_node.get(node_id) != requirement["goals"]:
            issues.append(f"required predicate goals are missing or changed for node: {node_id}")
    return issues


def evaluate_blueprint_contract(blueprint: Dict[str, Any], contract: Dict[str, Any]) -> List[str]:
    methods = blueprint.get("methods", []) if isinstance(blueprint, dict) else []
    if not methods:
        return ["blueprint has no methods"]

    body = methods[0].get("body", [])
    flat = flatten_statements(body)
    issues = _evaluate_structured_provenance(flat, contract)

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
