from typing import Dict, Any, List, Optional


def infer_transform_metadata(
    semantic_roles: Dict[str, Any],
) -> Dict[str, Any]:
    roles = dict(semantic_roles or {})

    ops = roles.get("ops")
    if isinstance(ops, list) and ops:
        roles.setdefault("transform_op_resolution", "explicit_ops")

    source_var = roles.get("source_var")
    if isinstance(source_var, str) and source_var.strip():
        roles.setdefault("transform_source_resolution", "source_var")

    return roles


def attach_transform_source_metadata(
    semantic_roles: Dict[str, Any],
    source_node_id: Optional[str],
) -> Dict[str, Any]:
    roles = dict(semantic_roles or {})
    if roles.get("transform_source_resolution") == "source_var":
        return roles
    if not source_node_id:
        return roles
    roles["transform_source_node_id"] = str(source_node_id)
    roles["transform_source_resolution"] = "input_link_var"
    return roles


def has_transform_source_metadata(
    semantic_roles: Dict[str, Any],
) -> bool:
    roles = semantic_roles or {}
    resolution = str(roles.get("transform_source_resolution") or "").strip().lower()
    if resolution == "source_var":
        source_var = roles.get("source_var")
        return isinstance(source_var, str) and bool(source_var.strip())
    if resolution == "input_link_var":
        source_node_id = roles.get("transform_source_node_id")
        return isinstance(source_node_id, str) and bool(source_node_id.strip())
    return False
