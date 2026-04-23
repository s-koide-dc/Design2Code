from typing import List, Dict, Any

from src.code_synthesis.action_handlers.candidate_handler import gather_candidates
from src.code_synthesis.action_handlers.fallbacks import apply_fallbacks


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
    if node.get("intent") != "PERSIST" or node.get("source_kind") != "file":
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
    new_p["statements"].append({
        "type": "raw",
        "code": f"File.WriteAllText({params[0]}, {params[1]});",
        "node_id": node.get("id"),
        "intent": "PERSIST"
    })
    new_p.setdefault("all_usings", set()).add("System.IO")
    new_p.setdefault("consumed_ids", set()).add(node.get("id"))
    new_p["completed_nodes"] += 1
    return [new_p]
