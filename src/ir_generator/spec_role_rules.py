# -*- coding: utf-8 -*-
from typing import Any, Callable, Dict, List, Optional, Tuple


def infer_spec_role(
    intent: str,
    step_text: str,
    tokens: List[Dict[str, Any]],
    logic_goals: List[Dict[str, Any]],
    infer_intent_role_cardinality: Callable[[str, List[Dict[str, Any]]], Tuple[Optional[str], Optional[str], Optional[str]]],
    node_type: Optional[str] = None,
) -> str:
    if node_type == "LOOP":
        return "ITERATE"
    if node_type == "CONDITION":
        return "CHECK"
    if intent in ["FETCH", "DATABASE_QUERY", "HTTP_REQUEST", "FILE_IO"]:
        return "FETCH"
    if intent == "JSON_DESERIALIZE":
        return "DESERIALIZE"
    if intent == "DISPLAY":
        return "DISPLAY"
    if intent == "PERSIST":
        return "PERSIST"
    if intent == "RETURN":
        return "RETURN"
    if intent == "EXISTS":
        return "CHECK"
    if intent == "CALC":
        return "CALCULATE"
    if intent == "LINQ":
        if logic_goals:
            return "FILTER"
        return "TRANSFORM"
    if intent == "TRANSFORM":
        return "TRANSFORM"

    inferred_intent, inferred_role, _ = infer_intent_role_cardinality(step_text, tokens)
    if inferred_intent == "EXISTS" or inferred_role == "CHECK":
        return "CHECK"
    if inferred_intent == "DISPLAY" or inferred_role == "DISPLAY":
        return "DISPLAY"
    if inferred_intent == "PERSIST" or inferred_role == "PERSIST":
        return "PERSIST"
    if inferred_intent == "FETCH" or inferred_role == "FETCH":
        return "FETCH"
    if inferred_intent == "LINQ":
        return "TRANSFORM" if inferred_role == "TRANSFORM" else "FILTER"
    return "ACTION"
