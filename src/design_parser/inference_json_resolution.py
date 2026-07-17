"""Deterministic JSON-deserialization fallback resolution."""

from __future__ import annotations

from typing import Any, Callable

from src.utils.semantic_intents import INTENT_JSON_DESERIALIZE, NODE_ACTION


def infer_json_deserialize_meta(line: str, last_output_type: str | None, semantic_roles: dict[str, Any] | None, allow_text_entity_inference: bool, looks_like_json_deserialize: Callable[[str], bool], entity_from_context: Callable[[str | None, dict[str, Any] | None], str | None], infer_text_entity: Callable[[str], str | None]) -> dict[str, str] | None:
    if not looks_like_json_deserialize(line):
        return None
    entity = entity_from_context(last_output_type, semantic_roles)
    if not entity and allow_text_entity_inference:
        entity = infer_text_entity(line)
    if not entity:
        return None
    return {"kind": NODE_ACTION, "intent": INTENT_JSON_DESERIALIZE, "target_entity": entity, "output_type": f"List<{entity}>", "side_effect": "NONE"}
