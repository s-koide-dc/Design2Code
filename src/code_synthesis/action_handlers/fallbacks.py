from typing import List, Dict, Any


def apply_fallbacks(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any]) -> List[Dict[str, Any]] | None:
    text = node.get("original_text", "")
    if node.get("intent") == "FETCH" and node.get("source_kind") == "stdin":
        new_p = action_synthesizer.synthesizer._copy_path(path)
        out_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string", "input", new_p, prefix="input", role="content")
        new_p["statements"].append({"type": "raw", "code": f"var {out_var} = Console.ReadLine();", "node_id": node.get("id"), "intent": "FETCH"})
        new_p.setdefault("type_to_vars", {}).setdefault("string", []).append({"var_name": out_var, "node_id": node.get("id"), "role": "content", "target_entity": "string"})
        new_p["active_scope_item"] = out_var
        new_p.setdefault("consumed_ids", set()).add(node.get("id"))
        new_p["completed_nodes"] += 1
        return [new_p]

    if isinstance(text, str) and "int" in text and "取得" in text:
        new_p = action_synthesizer.synthesizer._copy_path(path)
        call_expr = "Counter.GetCount()"
        stmt = {"type": "call", "method": call_expr, "args": [], "call_expr": call_expr, "node_id": node.get("id")}
        var_name = action_synthesizer.stmt_builder.get_semantic_var_name(node, "int", "result", new_p, role="data")
        stmt["out_var"] = var_name
        stmt["var_type"] = "int"
        new_p.setdefault("type_to_vars", {}).setdefault("int", []).append({"var_name": var_name, "node_id": node.get("id"), "role": "data", "target_entity": node.get("target_entity", "Item")})
        new_p["active_scope_item"] = var_name
        new_p["statements"].append(stmt)
        new_p.setdefault("consumed_ids", set()).add(node.get("id"))
        new_p["completed_nodes"] += 1
        return [new_p]

    sql_text = action_synthesizer._get_semantic_roles(node).get("sql")
    if sql_text and node.get("intent") in ["DATABASE_QUERY", "FETCH"]:
        target_entity = node.get("target_entity", "Item")
        entity = target_entity if target_entity and target_entity != "Item" else "T"
        call_expr = f"Db.Query<{entity}>(\"{sql_text}\")"
        new_p = action_synthesizer.synthesizer._copy_path(path)
        stmt = {"type": "call", "method": call_expr, "args": [f"\"{sql_text}\""], "call_expr": call_expr, "node_id": node.get("id")}
        ret_type = f"IEnumerable<{entity}>"
        var_name = action_synthesizer.stmt_builder.get_semantic_var_name(node, ret_type, "result", new_p, role="data")
        stmt["out_var"] = var_name
        stmt["var_type"] = ret_type
        new_p.setdefault("type_to_vars", {}).setdefault(ret_type, []).append({"var_name": var_name, "node_id": node.get("id"), "role": "data", "target_entity": target_entity})
        new_p["active_scope_item"] = var_name
        if target_entity and target_entity != "Item":
            action_synthesizer.stmt_builder.register_entity(target_entity, new_p)
        new_p["statements"].append(stmt)
        new_p.setdefault("consumed_ids", set()).add(node.get("id"))
        new_p["completed_nodes"] += 1
        return [new_p]

    return None
