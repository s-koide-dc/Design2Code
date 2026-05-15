from typing import Dict, Any, Optional


def infer_iterate_metadata(
    semantic_roles: Dict[str, Any],
) -> Dict[str, Any]:
    roles = dict(semantic_roles or {})
    roles.setdefault("structure_kind", "loop")
    explicit_item_entity = roles.get("item_entity") or roles.get("iteration_item_entity")
    if isinstance(explicit_item_entity, str) and explicit_item_entity.strip():
        roles["iteration_item_entity"] = explicit_item_entity.strip()
        roles.setdefault("iteration_item_resolution", "explicit_item_entity")
    explicit_item_var = roles.get("item_var") or roles.get("iteration_item_var")
    if isinstance(explicit_item_var, str) and explicit_item_var.strip():
        roles["iteration_item_var"] = explicit_item_var.strip()
        roles.setdefault("iteration_item_var_resolution", "explicit_item_var")
    if isinstance(roles.get("source_var"), str) and roles.get("source_var", "").strip():
        roles.setdefault("iteration_source_resolution", "source_var")
    return roles


def attach_iterate_item_metadata(
    semantic_roles: Dict[str, Any],
    item_entity: Optional[str],
    resolution: Optional[str],
) -> Dict[str, Any]:
    roles = dict(semantic_roles or {})
    if not item_entity or not resolution:
        return roles
    roles["iteration_item_entity"] = str(item_entity)
    roles["iteration_item_resolution"] = str(resolution)
    return roles


def attach_iterate_source_metadata(
    semantic_roles: Dict[str, Any],
    source_node_id: Optional[str],
) -> Dict[str, Any]:
    roles = dict(semantic_roles or {})
    if roles.get("iteration_source_resolution") == "source_var":
        return roles
    if not source_node_id:
        return roles
    roles["iteration_source_node_id"] = str(source_node_id)
    roles["iteration_source_resolution"] = "input_link_collection"
    return roles


def has_iterate_source_metadata(
    semantic_roles: Dict[str, Any],
) -> bool:
    roles = semantic_roles or {}
    resolution = str(roles.get("iteration_source_resolution") or "").strip().lower()
    if resolution == "source_var":
        source_var = roles.get("source_var")
        return isinstance(source_var, str) and bool(source_var.strip())
    if resolution == "input_link_collection":
        source_node_id = roles.get("iteration_source_node_id")
        return isinstance(source_node_id, str) and bool(source_node_id.strip())
    return False
