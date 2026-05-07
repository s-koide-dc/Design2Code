# -*- coding: utf-8 -*-
from typing import Dict, Any, List, Optional, Callable


def _token_bases(tokens: List[Dict[str, Any]]) -> List[str]:
    bases = []
    for token in tokens or []:
        base = token.get("base")
        if base:
            bases.append(str(base))
    return bases


def _token_surfaces(tokens: List[Dict[str, Any]]) -> List[str]:
    surfaces = []
    for token in tokens or []:
        surface = token.get("surface")
        if surface:
            surfaces.append(str(surface))
    return surfaces


def has_calculation_intent_signal(text: str, tokens: List[Dict[str, Any]]) -> bool:
    token_bases = set(_token_bases(tokens))
    token_surfaces = set(_token_surfaces(tokens))
    calc_bases = {"計算", "算出", "求める"}
    calc_surfaces = {"計算", "計算する", "算出", "算出する", "求める"}
    return bool(token_bases.intersection(calc_bases) or token_surfaces.intersection(calc_surfaces))


def has_filter_lexical_signal(text: str, tokens: List[Dict[str, Any]]) -> bool:
    token_bases = set(_token_bases(tokens))
    token_surfaces = set(_token_surfaces(tokens))
    filter_bases = {"抽出", "選択"}
    filter_surfaces = {"抽出", "抽出する", "選択", "選択する"}
    lowered = str(text or "").lower()
    return bool(
        token_bases.intersection(filter_bases)
        or token_surfaces.intersection(filter_surfaces)
        or "select" in lowered
        or "where" in lowered
    )


def has_filter_predicate_logic(logic_goals: List[Dict[str, Any]]) -> bool:
    return any(goal.get("type") in ["numeric", "string", "logic"] for goal in (logic_goals or []))


def has_upstream_collection_context(
    history: List[Dict[str, Any]],
    output_type_hint: Optional[str],
    is_collection_type: Callable[[Optional[str]], bool],
) -> bool:
    if is_collection_type(output_type_hint):
        return True
    if not history:
        return False
    last_context = history[-1]
    if last_context.get("cardinality") == "COLLECTION":
        return True
    return is_collection_type(str(last_context.get("output_type") or ""))


def infer_filter_property(tokens: List[Dict[str, Any]], logic_goals: List[Dict[str, Any]]) -> Optional[str]:
    for goal in logic_goals or []:
        target_hint = goal.get("target_hint")
        if target_hint:
            return str(target_hint)
        variable_hint = goal.get("variable_hint")
        if variable_hint and not str(variable_hint).lower().startswith("input"):
            return str(variable_hint)

    for idx, token in enumerate(tokens or []):
        base = str(token.get("base") or "").strip()
        surface = str(token.get("surface") or "").strip()
        candidate = surface or base
        if not candidate:
            continue
        if candidate in ["が", "を", "に", "より", "と", "は", "で"]:
            prev_idx = idx - 1
            while prev_idx >= 0:
                prev = tokens[prev_idx]
                prev_candidate = str(prev.get("surface") or prev.get("base") or "").strip()
                if not prev_candidate:
                    prev_idx -= 1
                    continue
                if prev_candidate not in ["ユーザー", "結果", "データ", "一覧"]:
                    return prev_candidate
                break
            break
    return None


def should_promote_to_filter(
    current_intent: str,
    step_text: str,
    tokens: List[Dict[str, Any]],
    logic_goals: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
    output_type_hint: Optional[str],
    is_collection_type: Callable[[Optional[str]], bool],
) -> bool:
    if current_intent not in ["GENERAL", "FETCH", "TRANSFORM"]:
        return False
    if not has_filter_lexical_signal(step_text, tokens):
        return False
    if not has_filter_predicate_logic(logic_goals):
        return False
    return has_upstream_collection_context(history, output_type_hint=output_type_hint, is_collection_type=is_collection_type)


def should_promote_to_calculate(
    current_intent: str,
    node_type: str,
    step_text: str,
    tokens: List[Dict[str, Any]],
    logic_goals: List[Dict[str, Any]],
    semantic_roles: Dict[str, Any],
) -> bool:
    if node_type != "ACTION":
        return False
    if current_intent not in ["GENERAL", "ACTION", "TRANSFORM"]:
        return False
    if any(goal.get("type") == "calculation" for goal in (logic_goals or [])):
        return True
    roles = semantic_roles or {}
    ops = [str(op).lower() for op in (roles.get("ops") or []) if op]
    if any(op in ["select", "map", "normalize"] for op in ops):
        return False
    if roles.get("notification") or roles.get("message") or roles.get("content"):
        return False
    if roles.get("check_kind"):
        return False
    has_target_metadata = bool(roles.get("target_hint") or roles.get("property"))
    if not has_target_metadata:
        return False
    return has_calculation_intent_signal(step_text, tokens)
