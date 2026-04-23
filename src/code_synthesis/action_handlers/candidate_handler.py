from typing import List, Dict, Any


def gather_candidates(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any], target_entity: str) -> List[Dict[str, Any]]:
    candidates = action_synthesizer._gather_candidates(node, path, target_entity)
    if not candidates and action_synthesizer.ukb is not None:
        try:
            candidates = action_synthesizer.ukb.search(node.get("original_text", ""), limit=10, intent=node.get("intent"), target_entity=target_entity)
        except Exception:
            candidates = []
    return candidates
