from typing import List, Dict, Any


def handle_fetch(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any]) -> List[Dict[str, Any]] | None:
    if node.get("intent") == "FETCH" and node.get("source_kind") == "stdin":
        new_p = action_synthesizer.synthesizer._copy_path(path)
        out_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string", "input", new_p, prefix="input", role="content")
        new_p["statements"].append({"type": "raw", "code": f"var {out_var} = Console.ReadLine();", "node_id": node.get("id"), "intent": "FETCH"})
        new_p.setdefault("type_to_vars", {}).setdefault("string", []).append({"var_name": out_var, "node_id": node.get("id"), "role": "content", "target_entity": "string"})
        new_p["active_scope_item"] = out_var
        new_p.setdefault("consumed_ids", set()).add(node.get("id"))
        new_p["completed_nodes"] += 1
        return [new_p]
    if node.get("intent") == "FETCH" and node.get("source_kind") == "file":
        method_sig = {
            "params": [{"name": "path", "type": "string", "role": "path"}]
        }
        params = action_synthesizer.semantic_binder.bind_parameters(method_sig, node, path)
        if not params:
            return None
        new_p = action_synthesizer.synthesizer._copy_path(path)
        out_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string", "content", new_p, prefix="content", role="content")
        new_p["statements"].append({
            "type": "raw",
            "code": f"var {out_var} = File.ReadAllText({params[0]});",
            "node_id": node.get("id"),
            "intent": "FETCH"
        })
        new_p.setdefault("all_usings", set()).add("System.IO")
        new_p.setdefault("type_to_vars", {}).setdefault("string", []).append({
            "var_name": out_var,
            "node_id": node.get("id"),
            "role": "content",
            "target_entity": "string"
        })
        new_p["active_scope_item"] = out_var
        new_p.setdefault("consumed_ids", set()).add(node.get("id"))
        new_p["completed_nodes"] += 1
        return [new_p]
    return None
