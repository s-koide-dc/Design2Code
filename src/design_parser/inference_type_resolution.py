"""Type-context rules shared by deterministic inference fallbacks."""

from __future__ import annotations

from typing import Any, Callable


def entity_from_structural_context(last_output_type: str | None, semantic_roles: dict[str, Any] | None, infer_from_output_type: Callable[[str | None], str]) -> str | None:
    roles = semantic_roles or {}
    role_entity = roles.get("target_entity") or roles.get("entity")
    if isinstance(role_entity, str) and role_entity.strip():
        return role_entity.strip()
    entity = infer_from_output_type(last_output_type)
    return entity or None
