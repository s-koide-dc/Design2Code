from typing import List, Dict, Any
from src.utils.semantic_intents import INTENT_FETCH


def handle_fetch(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any]) -> List[Dict[str, Any]] | None:
    if node.get("intent") == INTENT_FETCH and node.get("source_kind") == "stdin":
        new_p = action_synthesizer.synthesizer._copy_path(path)
        out_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string", "input", new_p, prefix="input", role="content")
        new_p["statements"].append({"type": "raw", "code": f"var {out_var} = Console.ReadLine() ?? string.Empty;", "node_id": node.get("id"), "intent": INTENT_FETCH})
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
        if error_policy == "return_default":
            helper_name = action_synthesizer.stmt_builder.ensure_text_file_read_helper(new_p)
            success_var = action_synthesizer.stmt_builder.get_semantic_var_name(
                node,
                "bool",
                "fileReadSucceeded",
                new_p,
                prefix=f"{out_var}Read",
                role="status",
            )
            new_p["statements"].append({
                "type": "raw",
                "code": f"bool {success_var} = true;",
                "node_id": f"{node.get('id')}_read_status",
                "intent": INTENT_FETCH,
            })
            new_p["statements"].append({
                "type": "call",
                "method": helper_name,
                "call_expr": f"{helper_name}({params[0]}, out {success_var})",
                "args": [params[0], f"out {success_var}"],
                "node_id": node.get("id"),
                "intent": INTENT_FETCH,
                "out_var": out_var,
                "var_type": "string",
            })
            failure_action = action_synthesizer.stmt_builder._catch_action_for_policy(
                path=new_p,
                error_policy=error_policy,
                has_hoisted_result=True,
                hoisted_result_var=out_var,
                hoisted_result_type="string",
            )
            if failure_action:
                new_p["statements"].append({
                    "type": "raw",
                    "code": f"if (!{success_var}) {failure_action}",
                    "node_id": f"{node.get('id')}_read_failure",
                    "intent": INTENT_FETCH,
                })
        else:
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
