from typing import List, Dict, Any

from src.code_synthesis.action_handlers.calc_ops import process_calc_node
from src.code_synthesis.action_handlers.action_utils import tag_intent_for_node
from src.utils.semantic_intents import INTENT_CALC


def handle_calc(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any]) -> List[Dict[str, Any]]:
    res = process_calc_node(action_synthesizer, node, path)
    for p in res:
        tag_intent_for_node(p.get("statements", []), node.get("id"), INTENT_CALC)
    for p in res:
        p["rank_tuple"] = (p["rank_tuple"][0] + 10, p["rank_tuple"][1], p["rank_tuple"][2], p["rank_tuple"][3] + 1.0)
    return res
