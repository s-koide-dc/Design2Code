from typing import List, Dict, Any


def handle_loop(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any], consumed_ids: set | None = None) -> List[Dict[str, Any]]:
    return action_synthesizer._process_loop_node(node, path, consumed_ids=consumed_ids)
