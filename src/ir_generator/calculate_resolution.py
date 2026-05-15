from typing import Dict, Any, Optional


def infer_calculate_metadata(
    semantic_roles: Dict[str, Any],
) -> Dict[str, Any]:
    roles = dict(semantic_roles or {})

    source_var = roles.get("source_var")
    if isinstance(source_var, str) and source_var.strip():
        roles.setdefault("calculate_source_resolution", "source_var")

    if roles.get("property") or roles.get("target_hint"):
        roles.setdefault("calculate_target_resolution", "explicit_target")
    else:
        roles.setdefault("calculate_target_resolution", "default_target")

    return roles


def attach_calculate_target_metadata(
    semantic_roles: Dict[str, Any],
    canonical_property: Optional[str],
    property_resolution: Optional[str],
) -> Dict[str, Any]:
    roles = dict(semantic_roles or {})
    if canonical_property and property_resolution == "schema_property":
        roles["property"] = canonical_property
        roles["calculate_target_resolution"] = "schema_property"
        return roles
    if canonical_property and property_resolution == "history_scope":
        roles["property"] = canonical_property
        roles["calculate_target_resolution"] = "history_target"
        return roles
    if roles.get("property") or roles.get("target_hint"):
        roles.setdefault("calculate_target_resolution", "explicit_target")
        return roles
    roles.setdefault("calculate_target_resolution", "default_target")
    return roles


def attach_calculate_source_metadata(
    semantic_roles: Dict[str, Any],
    source_node_id: Optional[str],
) -> Dict[str, Any]:
    roles = dict(semantic_roles or {})
    if roles.get("calculate_source_resolution") == "source_var":
        return roles
    if not source_node_id:
        roles.setdefault("calculate_source_resolution", "default_scope_var")
        return roles
    roles["calculate_source_node_id"] = str(source_node_id)
    roles["calculate_source_resolution"] = "input_link_var"
    return roles


def has_calculate_source_metadata(
    semantic_roles: Dict[str, Any],
) -> bool:
    roles = semantic_roles or {}
    resolution = str(roles.get("calculate_source_resolution") or "").strip().lower()
    if resolution == "source_var":
        source_var = roles.get("source_var")
        return isinstance(source_var, str) and bool(source_var.strip())
    if resolution == "input_link_var":
        source_node_id = roles.get("calculate_source_node_id")
        return isinstance(source_node_id, str) and bool(source_node_id.strip())
    if resolution == "default_scope_var":
        return True
    return False
