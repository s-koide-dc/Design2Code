from typing import Dict, Any, List, Optional
import copy


def to_csharp_string_literal(text: Optional[str]) -> str:
    if text is None:
        return "\"\""
    raw = str(text)
    escaped = raw.replace("\"", "\"\"")
    return f"@\"{escaped}\"" if "\"" in raw else f"\"{raw}\""


def safe_copy_node(node: Dict[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(node)


def is_known_state_property(prop: str) -> bool:
    if not prop:
        return False
    key = str(prop).lower()
    return key in ["status", "state", "result", "isactive", "isdisabled", "flag", "enabled", "disabled"]


def tag_intent_for_node(statements: List[Dict[str, Any]], node_id: str, intent: str) -> None:
    for stmt in statements or []:
        if isinstance(stmt, dict):
            if stmt.get("node_id") == node_id:
                stmt["intent"] = intent
            for key in ["body", "else_body", "statements"]:
                if key in stmt and isinstance(stmt[key], list):
                    tag_intent_for_node(stmt[key], node_id, intent)
