from typing import List, Dict, Any
from src.utils.semantic_intents import INTENT_FETCH


def handle_fetch(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any]) -> List[Dict[str, Any]] | None:
    if node.get("intent") == INTENT_FETCH and node.get("source_kind") == "stdin":
        new_p = action_synthesizer.synthesizer._copy_path(path)
        out_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string", "input", new_p, prefix="input", role="content")
        new_p["statements"].append({"type": "raw", "code": f"var {out_var} = Console.ReadLine();", "node_id": node.get("id"), "intent": INTENT_FETCH})
        new_p.setdefault("type_to_vars", {}).setdefault("string", []).append({"var_name": out_var, "node_id": node.get("id"), "role": "content", "target_entity": "string"})
        new_p["active_scope_item"] = out_var
        new_p.setdefault("consumed_ids", set()).add(node.get("id"))
        new_p["completed_nodes"] += 1
        return [new_p]
    if node.get("intent") == INTENT_FETCH and node.get("source_kind") == "file":
        method_sig = {
            "params": [{"name": "path", "type": "string", "role": "path"}]
        }
        params = action_synthesizer.semantic_binder.bind_parameters(method_sig, node, path)
        if not params:
            return None
        new_p = action_synthesizer.synthesizer._copy_path(path)
        out_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string", "content", new_p, prefix="content", role="content")
        semantic_roles = action_synthesizer._get_semantic_roles(node)
        error_policy = str(
            semantic_roles.get("error_policy") or "return_default"
        ).strip().lower()
        if error_policy not in {"return_default", "rethrow", "continue"}:
            return action_synthesizer._unresolved_path(
                path,
                node,
                "invalid_error_policy",
                details={"error_policy": error_policy},
            )
        stmt = {
            "type": "raw",
            "code": f"{out_var} = File.ReadAllText({params[0]});",
            "node_id": node.get("id"),
            "intent": INTENT_FETCH,
            "out_var": out_var,
            "var_type": "string",
        }
        new_p["statements"].append(
            action_synthesizer.stmt_builder.wrap_with_try_catch(
                stmt,
                INTENT_FETCH,
                "File.ReadAllText",
                new_p,
                error_policy=error_policy,
            )
        )
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
