# -*- coding: utf-8 -*-
from typing import List, Dict, Any

class IREmitter:
    def __init__(self, synthesizer):
        self.synthesizer = synthesizer
        self.type_system = synthesizer.type_system
        
    def emit(self, ir_tree: Dict[str, Any], initial_candidates: List[Dict[str, Any]], beam_width: int = 5, consumed_ids: set = None) -> List[Dict[str, Any]]:
        logic_tree = ir_tree.get("logic_tree", [])
        if not logic_tree: return initial_candidates
        return self._emit_nodes(logic_tree, initial_candidates, beam_width, consumed_ids=consumed_ids)

    def _emit_nodes(self, nodes: List[Dict[str, Any]], candidates: List[Dict[str, Any]], beam_width: int, consumed_ids: set = None) -> List[Dict[str, Any]]:
        current_candidates = candidates
        
        # 27.58: Ensure all initial paths in this emission level inherit the external consumed_ids
        if consumed_ids:
            for p in current_candidates:
                if "consumed_ids" not in p: p["consumed_ids"] = set()
                p["consumed_ids"].update(consumed_ids)
        
        for i, node in enumerate(nodes):
            if node.get("skip_synthesis"): continue
            
            # 27.51: Skip node if it was already processed by a parent via its specific ID
            if consumed_ids and node.get("id") in consumed_ids:
                continue

            next_candidates = []
            
            # 27.17: Proactive bridging - peek next node's intent to bias current node synthesis
            future_hint = None
            if i + 1 < len(nodes):
                next_node = nodes[i+1]
                next_intent = next_node.get("intent")
                if next_node.get("type") == "LOOP": future_hint = "COLLECTION_REQUIRED"
                elif next_intent == "JSON_DESERIALIZE": future_hint = "STRING_REQUIRED"
                elif next_intent == "CALC": future_hint = "NUMERIC_REQUIRED"

            for p in current_candidates:
                # Check path-specific consumption
                p_consumed = p.get("consumed_ids", set())
                if node.get("id") in p_consumed:
                    cp = self.synthesizer._copy_path(p)
                    cp["completed_nodes"] += 1
                    next_candidates.append(cp)
                    continue

                # --- Inter-node Type Bridging (Deprecated in Phase 27) ---
                # 27.310: Do not automatically bridge with JSON_DESERIALIZE inside emitters.
                # This causes recursive loops. ActionSynthesizer should handle transformations.
                
                res = self.synthesizer.action_synthesizer.process_node(node, p, future_hint=future_hint, consumed_ids=p_consumed)
                if not res: continue
                next_candidates.extend(res)

            if next_candidates:
                current_candidates = sorted(next_candidates, key=lambda x: (x.get("completed_nodes", 0)), reverse=True)[:beam_width]
                
        return current_candidates
