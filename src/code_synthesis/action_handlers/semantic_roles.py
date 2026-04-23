from typing import Dict, Any


def get_semantic_roles(node: Dict[str, Any]) -> Dict[str, Any]:
    direct = node.get("semantic_roles", {}) if isinstance(node, dict) else {}
    mapped = node.get("semantic_map", {}).get("semantic_roles", {}) if isinstance(node, dict) else {}
    roles: Dict[str, Any] = {}
    if isinstance(mapped, dict):
        roles.update(mapped)
    if isinstance(direct, dict):
        for k, v in direct.items():
            if v is not None:
                roles[k] = v
    return roles
