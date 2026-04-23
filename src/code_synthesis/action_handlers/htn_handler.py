from typing import List, Dict, Any


def handle_htn_plan(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any], htn_plan: list) -> List[Dict[str, Any]]:
    return action_synthesizer._process_htn_plan(node, path, htn_plan)
