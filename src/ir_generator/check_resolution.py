# -*- coding: utf-8 -*-
from typing import Dict, Any, List, Optional, Tuple

from src.utils.text_parser import extract_first_quoted_literal


def normalize_check_operator(operator_name: Optional[str]) -> Optional[str]:
    op = str(operator_name or "").strip()
    if not op:
        return None
    mapping = {
        "Greater": ">",
        "Less": "<",
        "Equal": "==",
        "NotEqual": "!=",
        "GreaterEqual": ">=",
        "LessEqual": "<=",
    }
    return mapping.get(op, op)


def infer_null_check_subject_metadata(tokens: List[Dict[str, Any]], target_entity: Optional[str]) -> Tuple[str, str]:
    null_markers = {"null", "Null", "NULL"}
    subject = None
    for idx, token in enumerate(tokens or []):
        surface = str(token.get("surface") or "")
        base = str(token.get("base") or "")
        if surface not in null_markers and base not in null_markers:
            continue
        for prev_idx in range(idx - 1, -1, -1):
            prev = tokens[prev_idx]
            prev_surface = str(prev.get("surface") or "").strip()
            prev_base = str(prev.get("base") or "").strip()
            candidate = prev_surface or prev_base
            if not candidate:
                continue
            if candidate in ["が", "は", "を", "に", "なら", "ば", "もし"]:
                continue
            if candidate.lower() in ["if", "then"]:
                continue
            subject = candidate
            break
        if subject:
            break
    if subject:
        return subject, "explicit_subject"
    if target_entity and target_entity != "Item":
        return str(target_entity).lower(), "history_subject"
    return "value", "default_subject"


def infer_check_target_entity(
    target_entity: Optional[str],
    check_meta: Dict[str, Any],
    history: List[Dict[str, Any]],
    weak_entities: List[str],
) -> str:
    current = target_entity or "Item"
    if current not in weak_entities:
        return current

    check_kind = str(check_meta.get("check_kind") or "").strip().lower()
    subject = str(check_meta.get("check_subject") or "").strip()
    if check_kind == "null_check" and subject and subject.lower() not in ["value", "item", "result", "context"]:
        if subject.isidentifier():
            return subject[:1].upper() + subject[1:]

    for hist in reversed(history or []):
        hist_entity = hist.get("target_entity")
        if hist_entity and hist_entity not in weak_entities:
            return hist_entity
    return current


def infer_check_metadata(
    step_text: str,
    tokens: List[Dict[str, Any]],
    logic_goals: List[Dict[str, Any]],
    source_kind: Optional[str],
    source_ref: Optional[str],
    target_entity: Optional[str],
    node_type: Optional[str],
) -> Dict[str, Any]:
    text = str(step_text or "")
    lowered = text.lower()
    if node_type != "CONDITION" and "null" not in lowered and "存在" not in text and not logic_goals:
        return {}

    token_bases = {str(t.get("base") or "") for t in (tokens or [])}
    metadata: Dict[str, Any] = {}

    if "null" in lowered:
        null_subject, null_resolution = infer_null_check_subject_metadata(tokens, target_entity)
        metadata["check_kind"] = "null_check"
        metadata["check_subject"] = null_subject
        metadata["expected_truth"] = False
        metadata["subject_resolution"] = null_resolution
        return metadata

    if "存在" in token_bases or "有る" in token_bases or "ある" in token_bases or "存在" in text:
        quoted = extract_first_quoted_literal(text)
        metadata["check_kind"] = "exists_check"
        metadata["check_subject"] = quoted or source_ref or (target_entity if target_entity and target_entity != "Item" else "value")
        metadata["expected_truth"] = True
        if quoted:
            metadata["subject_resolution"] = "quoted_literal"
        elif source_ref:
            metadata["subject_resolution"] = "explicit_subject"
        elif target_entity and target_entity != "Item":
            metadata["subject_resolution"] = "history_subject"
        else:
            metadata["subject_resolution"] = "default_subject"
        resolved_source_ref = source_ref or quoted
        if resolved_source_ref:
            metadata["source_ref"] = resolved_source_ref
        resolved_source_kind = source_kind
        if not resolved_source_kind and quoted and any(ext in quoted.lower() for ext in [".json", ".txt", ".csv", ".xml"]):
            resolved_source_kind = "file"
        if resolved_source_kind:
            metadata["source_kind"] = resolved_source_kind
        return metadata

    for goal in logic_goals:
        goal_type = goal.get("type")
        operator = normalize_check_operator(goal.get("operator"))
        expected_value = goal.get("expected_value")
        subject = goal.get("target_hint") or goal.get("variable_hint")
        if goal_type in ["numeric", "string"] and operator and expected_value not in [None, ""]:
            metadata["check_kind"] = "comparison_check"
            metadata["check_subject"] = subject or (target_entity if target_entity and target_entity != "Item" else "value")
            metadata["check_operator"] = operator
            metadata["check_value"] = str(expected_value)
            metadata["expected_truth"] = True
            metadata["subject_resolution"] = "explicit_subject" if subject else ("history_subject" if target_entity and target_entity != "Item" else "default_subject")
            return metadata

    if node_type == "CONDITION":
        quoted = extract_first_quoted_literal(text)
        metadata["check_kind"] = "exists_check"
        metadata["check_subject"] = quoted or source_ref or (target_entity if target_entity and target_entity != "Item" else "value")
        metadata["expected_truth"] = True
        if quoted:
            metadata["subject_resolution"] = "quoted_literal"
        elif source_ref:
            metadata["subject_resolution"] = "explicit_subject"
        elif target_entity and target_entity != "Item":
            metadata["subject_resolution"] = "history_subject"
        else:
            metadata["subject_resolution"] = "default_subject"
        resolved_source_ref = source_ref or quoted
        if resolved_source_ref:
            metadata["source_ref"] = resolved_source_ref
        resolved_source_kind = source_kind
        if not resolved_source_kind and quoted and any(ext in quoted.lower() for ext in [".json", ".txt", ".csv", ".xml"]):
            resolved_source_kind = "file"
        if resolved_source_kind:
            metadata["source_kind"] = resolved_source_kind
        return metadata

    return {}
