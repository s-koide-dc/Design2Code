from typing import List, Dict, Any

from src.code_synthesis.action_handlers.candidate_handler import gather_candidates
from src.code_synthesis.action_handlers.fallbacks import apply_fallbacks
from src.utils.semantic_intents import INTENT_PERSIST


def handle_io(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any]) -> List[Dict[str, Any]]:
    target_entity = node.get("target_entity", "Item")
    candidates = gather_candidates(action_synthesizer, node, path, target_entity)
    results: List[Dict[str, Any]] = []
    for m in candidates:
        if "steps" in m:
            results.extend(action_synthesizer._process_htn_plan(node, path, m["steps"]))
        else:
            res = action_synthesizer._synthesize_single_method(m, node, path, target_entity)
            if res:
                res.setdefault("consumed_ids", set()).add(node.get("id"))
                results.append(res)
    if not results:
        fallback_paths = apply_fallbacks(action_synthesizer, node, path)
        if fallback_paths is not None:
            return fallback_paths
    return results


def handle_file_persist(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any]) -> List[Dict[str, Any]] | None:
    if node.get("intent") != INTENT_PERSIST or node.get("source_kind") != "file":
        return None
    method_sig = {
        "params": [
            {"name": "path", "type": "string", "role": "path"},
            {"name": "contents", "type": "string", "role": "content"}
        ]
    }
    params = action_synthesizer.semantic_binder.bind_parameters(method_sig, node, path)
    if not params or len(params) < 2:
        return None
    new_p = action_synthesizer.synthesizer._copy_path(path)
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
        helper_name = action_synthesizer.stmt_builder.ensure_text_file_write_helper(new_p)
        success_var = action_synthesizer.stmt_builder.get_semantic_var_name(
            node,
            "bool",
            "fileWriteSucceeded",
            new_p,
            prefix="fileWriteSucceeded",
            role="status",
        )
        new_p["statements"].append({
            "type": "raw",
            "code": f"bool {success_var} = {helper_name}({params[0]}, {params[1]});",
            "node_id": node.get("id"),
            "intent": INTENT_PERSIST,
        })
        failure_action = action_synthesizer.stmt_builder._catch_action_for_policy(
            path=new_p,
            error_policy=error_policy,
        )
        if failure_action:
            new_p["statements"].append({
                "type": "raw",
                "code": f"if (!{success_var}) {failure_action}",
                "node_id": f"{node.get('id')}_write_failure",
                "intent": INTENT_PERSIST,
            })
    else:
        new_p["statements"].append(
            action_synthesizer.stmt_builder.wrap_with_try_catch(
                {
                    "type": "raw",
                    "code": f"File.WriteAllText({params[0]}, {params[1]});",
                    "node_id": node.get("id"),
                    "intent": INTENT_PERSIST
                },
                INTENT_PERSIST,
                "File.WriteAllText",
                new_p,
                error_policy=error_policy,
            )
        )
    new_p.setdefault("all_usings", set()).add("System.IO")
    new_p.setdefault("consumed_ids", set()).add(node.get("id"))
    new_p["completed_nodes"] += 1
    return [new_p]
