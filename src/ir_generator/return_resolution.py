# -*- coding: utf-8 -*-
from typing import Dict, Any, List, Optional

from src.utils.text_parser import extract_first_quoted_literal


def _extract_first_number(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    s = str(text)
    i = 0
    while i < len(s):
        if s[i].isdigit():
            j = i
            while j < len(s) and s[j].isdigit():
                j += 1
            if j < len(s) and s[j] == ".":
                k = j + 1
                if k < len(s) and s[k].isdigit():
                    while k < len(s) and s[k].isdigit():
                        k += 1
                    return s[i:k]
            return s[i:j]
        i += 1
    return None


def _is_numeric_literal(value: Optional[str]) -> bool:
    s = str(value or "").strip()
    if not s:
        return False
    dot_count = 0
    digit_count = 0
    for ch in s:
        if ch == ".":
            dot_count += 1
            if dot_count > 1:
                return False
            continue
        if not ch.isdigit():
            return False
        digit_count += 1
    return digit_count > 0


def _token_values(tokens: List[Dict[str, Any]]) -> List[str]:
    values: List[str] = []
    for token in tokens or []:
        surface = str(token.get("surface") or "").strip()
        base = str(token.get("base") or "").strip()
        if surface:
            values.append(surface)
        if base and base != surface:
            values.append(base)
    return values


def _infer_explicit_return_resolution(return_value: Any, existing_resolution: Optional[str]) -> Optional[str]:
    if existing_resolution:
        return str(existing_resolution)
    if return_value is None:
        return None
    lowered = str(return_value).strip().lower()
    if lowered in ["true", "false"]:
        return "literal_boolean"
    if lowered == "null":
        return "literal_null"
    if _is_numeric_literal(return_value):
        return "literal_numeric"
    return "explicit_literal"


def infer_return_metadata(
    step_text: str,
    tokens: List[Dict[str, Any]],
    semantic_roles: Dict[str, Any],
) -> Dict[str, Any]:
    roles = dict(semantic_roles or {})

    explicit_source_var = str(roles.get("source_var") or "").strip()
    if explicit_source_var:
        roles["return_value"] = explicit_source_var
        roles["return_value_resolution"] = "source_var"
        return roles

    if "return_value" in roles:
        resolution = _infer_explicit_return_resolution(
            roles.get("return_value"),
            roles.get("return_value_resolution"),
        )
        if resolution:
            roles["return_value_resolution"] = resolution
        return roles

    quoted = extract_first_quoted_literal(step_text)
    if quoted is not None:
        roles["return_value"] = quoted
        roles["return_value_resolution"] = "quoted_literal"
        return roles

    lowered_values = [value.lower() for value in _token_values(tokens)]
    if "null" in lowered_values:
        roles["return_value"] = "null"
        roles["return_value_resolution"] = "literal_null"
        return roles
    if "true" in lowered_values:
        roles["return_value"] = "true"
        roles["return_value_resolution"] = "literal_boolean"
        return roles
    if "false" in lowered_values:
        roles["return_value"] = "false"
        roles["return_value_resolution"] = "literal_boolean"
        return roles

    number = _extract_first_number(step_text)
    if number is not None:
        roles["return_value"] = number
        roles["return_value_resolution"] = "literal_numeric"
        return roles

    return roles


def attach_return_source_metadata(
    semantic_roles: Dict[str, Any],
    source_node_id: Optional[str],
) -> Dict[str, Any]:
    roles = dict(semantic_roles or {})
    if not source_node_id:
        return roles
    if "return_value" in roles or "return_source_node_id" in roles:
        return roles
    roles["return_source_node_id"] = str(source_node_id)
    roles["return_value_resolution"] = "input_link_var"
    return roles


def has_literal_return_metadata(semantic_roles: Dict[str, Any]) -> bool:
    resolution = str((semantic_roles or {}).get("return_value_resolution") or "").strip().lower()
    return resolution in [
        "literal_boolean",
        "literal_null",
        "literal_numeric",
        "quoted_literal",
        "explicit_literal",
    ]
