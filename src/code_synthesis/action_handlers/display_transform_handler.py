from typing import List, Dict, Any

from src.code_synthesis.action_handlers.display_transform_ops import process_display_transform_specialized


def handle_display_transform(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any]) -> List[Dict[str, Any]] | None:
    res = process_display_transform_specialized(action_synthesizer, node, path)
    if res is not None:
        for p in res:
            p["rank_tuple"] = (p["rank_tuple"][0] + 5, p["rank_tuple"][1], p["rank_tuple"][2], p["rank_tuple"][3] + 0.5)
        return res
    return None
