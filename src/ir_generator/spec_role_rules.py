# -*- coding: utf-8 -*-
from typing import Any, Callable, Dict, List, Optional, Tuple
from src.utils.semantic_intents import (
    INTENT_CALC,
    INTENT_DATABASE_QUERY,
    INTENT_DISPLAY,
    INTENT_EXISTS,
    INTENT_FETCH,
    INTENT_FILE_IO,
    INTENT_HTTP_REQUEST,
    INTENT_JSON_DESERIALIZE,
    INTENT_LINQ,
    INTENT_PERSIST,
    INTENT_RETURN,
    INTENT_TRANSFORM,
    NODE_CONDITION,
    NODE_LOOP,
    ROLE_CHECK,
    ROLE_DISPLAY,
    ROLE_FETCH,
    ROLE_PERSIST,
    ROLE_TRANSFORM,
)


def infer_spec_role(
    intent: str,
    step_text: str,
    tokens: List[Dict[str, Any]],
    logic_goals: List[Dict[str, Any]],
    infer_intent_role_cardinality: Callable[[str, List[Dict[str, Any]]], Tuple[Optional[str], Optional[str], Optional[str]]],
    node_type: Optional[str] = None,
) -> str:
    if node_type == NODE_LOOP:
        return "ITERATE"
    if node_type == NODE_CONDITION:
        return "CHECK"
    if intent in [INTENT_FETCH, INTENT_DATABASE_QUERY, INTENT_HTTP_REQUEST, INTENT_FILE_IO]:
        return "FETCH"
    if intent == INTENT_JSON_DESERIALIZE:
        return "DESERIALIZE"
    if intent == INTENT_DISPLAY:
        return "DISPLAY"
    if intent == INTENT_PERSIST:
        return "PERSIST"
    if intent == INTENT_RETURN:
        return "RETURN"
    if intent == INTENT_EXISTS:
        return "CHECK"
    if intent == INTENT_CALC:
        return "CALCULATE"
    if intent == INTENT_LINQ:
        if logic_goals:
            return "FILTER"
        return "TRANSFORM"
    if intent == INTENT_TRANSFORM:
        return "TRANSFORM"

    inferred_intent, inferred_role, _ = infer_intent_role_cardinality(step_text, tokens)
    if inferred_intent == INTENT_EXISTS or inferred_role == ROLE_CHECK:
        return "CHECK"
    if inferred_intent == INTENT_DISPLAY or inferred_role == ROLE_DISPLAY:
        return "DISPLAY"
    if inferred_intent == INTENT_PERSIST or inferred_role == ROLE_PERSIST:
        return "PERSIST"
    if inferred_intent == INTENT_FETCH or inferred_role == ROLE_FETCH:
        return "FETCH"
    if inferred_intent == INTENT_LINQ:
        return "TRANSFORM" if inferred_role == ROLE_TRANSFORM else "FILTER"
    return "ACTION"
