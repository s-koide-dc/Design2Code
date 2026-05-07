# -*- coding: utf-8 -*-
from typing import Dict, Any, List, Optional, Tuple


def extract_entity_property_definitions(entity_def: Dict[str, Any]) -> List[Tuple[str, List[str]]]:
    property_defs: List[Tuple[str, List[str]]] = []
    if not isinstance(entity_def, dict):
        return property_defs
    for raw_prop in entity_def.get("properties", []) or []:
        prop_name = None
        aliases: List[str] = []
        if isinstance(raw_prop, str):
            prop_name = raw_prop.split(":", 1)[0].strip()
        elif isinstance(raw_prop, dict):
            prop_name = raw_prop.get("name")
            aliases = [str(alias).strip() for alias in (raw_prop.get("aliases") or []) if str(alias).strip()]
        if prop_name:
            property_defs.append((str(prop_name), aliases))
    return property_defs


def extract_entity_property_names(entity_def: Dict[str, Any]) -> List[str]:
    property_names: List[str] = []
    for prop_name, _ in extract_entity_property_definitions(entity_def):
        property_names.append(prop_name)
    return property_names


def resolve_canonical_property_name(
    entity_schema: Dict[str, Any],
    property_name: Optional[str],
) -> Tuple[Optional[str], List[str]]:
    normalized_property = str(property_name or "").strip().lower()
    if not normalized_property or not isinstance(entity_schema, dict):
        return None, []

    canonical_matches: Dict[str, List[str]] = {}
    for entity_def in entity_schema.get("entities", []) or []:
        entity_name = entity_def.get("name") if isinstance(entity_def, dict) else None
        if not entity_name:
            continue
        for prop_name, aliases in extract_entity_property_definitions(entity_def):
            accepted_tokens = [prop_name] + aliases
            if any(str(token).strip().lower() == normalized_property for token in accepted_tokens):
                canonical_matches.setdefault(str(prop_name), []).append(str(entity_name))

    if len(canonical_matches) != 1:
        return None, []

    canonical_name, owners = next(iter(canonical_matches.items()))
    return canonical_name, owners


def find_property_owner_entities(entity_schema: Dict[str, Any], property_name: Optional[str]) -> List[str]:
    _, matched_entities = resolve_canonical_property_name(entity_schema, property_name)
    return matched_entities


def resolve_property_provenance(
    entity_schema: Dict[str, Any],
    property_name: Optional[str],
    current_entity: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    normalized_property = str(property_name or "").strip()
    if not normalized_property:
        return None, None

    canonical_property, matched_entities = resolve_canonical_property_name(entity_schema, normalized_property)
    if not matched_entities:
        return None, None
    if len(matched_entities) == 1:
        return canonical_property, "schema_property"

    current = str(current_entity or "").strip()
    if current and current in matched_entities:
        return canonical_property, "history_scope"

    return None, None


def infer_calculate_target_entity(
    entity_schema: Dict[str, Any],
    current_entity: Optional[str],
    semantic_roles: Dict[str, Any],
    history: List[Dict[str, Any]],
    weak_entities: List[str],
) -> Tuple[str, str]:
    current = current_entity or "Item"
    roles = semantic_roles or {}
    property_owners = find_property_owner_entities(entity_schema, roles.get("property") or roles.get("target_hint"))
    if len(property_owners) == 1:
        return property_owners[0], "unique_owner"

    if current not in weak_entities:
        return current, "explicit_entity"

    role_entity = roles.get("target_entity")
    if role_entity and role_entity not in weak_entities:
        return str(role_entity), "explicit_entity"

    if len(property_owners) > 1:
        return current, "ambiguous"

    for hist in reversed(history or []):
        hist_entity = hist.get("target_entity")
        if hist_entity and hist_entity not in weak_entities:
            return hist_entity, "history_fallback"
    return current, "history_fallback"
