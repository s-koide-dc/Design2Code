# -*- coding: utf-8 -*-
from typing import Dict, Any, List

from src.ir_generator.target_resolution import resolve_property_provenance


def infer_display_property_metadata(
    entity_schema: Dict[str, Any],
    tokens: List[Dict[str, Any]],
    semantic_roles: Dict[str, Any],
    current_entity: str,
) -> Dict[str, Any]:
    roles = dict(semantic_roles or {})

    explicit_property = roles.get("property") or roles.get("display_property") or roles.get("field")
    candidates: List[str] = []
    if isinstance(explicit_property, str) and explicit_property.strip():
        candidates.append(explicit_property.strip())

    for token in tokens or []:
        if not isinstance(token, dict):
            continue
        for key in ["surface", "base"]:
            raw = token.get(key)
            if not raw:
                continue
            candidate = str(raw).strip()
            if candidate and candidate not in candidates:
                candidates.append(candidate)

    for candidate in candidates:
        canonical_property, property_resolution = resolve_property_provenance(
            entity_schema,
            candidate,
            current_entity,
        )
        if canonical_property and property_resolution:
            roles["property"] = canonical_property
            roles["display_property_resolution"] = property_resolution
            return roles

    return roles
