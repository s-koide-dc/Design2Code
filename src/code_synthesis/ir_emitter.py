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

                spec_role = self._get_spec_role(node)
                if spec_role == "WRAP" and node.get("children"):
                    wrapped = self._emit_wrapper(node, p, beam_width, p_consumed)
                    if wrapped:
                        next_candidates.extend(wrapped)
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

    def _get_spec_role(self, node: Dict[str, Any]) -> str | None:
        semantic_map = node.get("semantic_map", {}) or {}
        spec_role = semantic_map.get("spec_role")
        if isinstance(spec_role, str) and spec_role.strip():
            return spec_role.strip().upper()
        semantic_roles = semantic_map.get("semantic_roles", {}) or {}
        nested = semantic_roles.get("spec_role")
        if isinstance(nested, str) and nested.strip():
            return nested.strip().upper()
        return None

    def _emit_wrapper(
        self,
        node: Dict[str, Any],
        path: Dict[str, Any],
        beam_width: int,
        consumed_ids: set | None = None,
    ) -> List[Dict[str, Any]]:
        wrapper_path = self.synthesizer._copy_path(path)
        wrapper_consumed = (consumed_ids or set()).copy()
        wrapper_consumed.add(node.get("id"))
        wrapper_path.setdefault("consumed_ids", set()).update(wrapper_consumed)
        base_count = len(wrapper_path.get("statements", []))
        child_paths = self._emit_nodes(
            node.get("children", []),
            [wrapper_path],
            beam_width,
            consumed_ids=wrapper_consumed,
        )
        if not child_paths:
            return []

        semantic_roles = node.get("semantic_map", {}).get("semantic_roles", {}) or {}
        wrapper_kind = str(semantic_roles.get("wrapper_kind") or "wrapper").strip().lower()
        wrapper_label = wrapper_kind if wrapper_kind else "wrapper"
        results: List[Dict[str, Any]] = []
        for child_path in child_paths:
            wrapped_path = self.synthesizer._copy_path(child_path)
            wrapped_path.setdefault("consumed_ids", set()).add(node.get("id"))
            wrapped_path["completed_nodes"] = child_path.get("completed_nodes", 0) + 1
            emitted_body = list(wrapped_path.get("statements", [])[base_count:])
            wrapped_path["statements"] = list(wrapped_path.get("statements", [])[:base_count])
            wrapped_path["statements"].append(
                self._build_wrapper_statement(
                    node,
                    wrapper_label,
                    semantic_roles,
                    emitted_body,
                )
            )
            results.append(wrapped_path)
        return results

    def _build_wrapper_statement(
        self,
        node: Dict[str, Any],
        wrapper_label: str,
        semantic_roles: Dict[str, Any],
        body: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if wrapper_label == "retry":
            max_attempts = semantic_roles.get("max_retries") or semantic_roles.get("max_attempts") or 3
            try:
                max_attempts = int(max_attempts)
            except (TypeError, ValueError):
                max_attempts = 3
            if max_attempts < 1:
                max_attempts = 1
            exception_type = str(semantic_roles.get("exception_type") or "Exception").strip() or "Exception"
            max_attempts_resolution = semantic_roles.get("max_attempts_resolution")
            if not max_attempts_resolution:
                if semantic_roles.get("max_attempts") is not None or semantic_roles.get("max_retries") is not None:
                    max_attempts_resolution = "explicit_attempts"
                else:
                    max_attempts_resolution = "default_attempts"
            exception_type_resolution = semantic_roles.get("exception_type_resolution")
            if not exception_type_resolution:
                if semantic_roles.get("exception_type"):
                    exception_type_resolution = "explicit_exception_type"
                else:
                    exception_type_resolution = "default_exception_type"
            retry_delay_policy_resolution = semantic_roles.get("retry_delay_policy_resolution")
            if not retry_delay_policy_resolution:
                if (
                    semantic_roles.get("base_delay_ms") is not None
                    or semantic_roles.get("max_delay_ms") is not None
                    or semantic_roles.get("backoff_multiplier") is not None
                ):
                    retry_delay_policy_resolution = "explicit_delay_policy"
                else:
                    retry_delay_policy_resolution = "default_no_delay_policy"
            return {
                "type": "retry",
                "body": body,
                "max_attempts": max_attempts,
                "max_attempts_resolution": max_attempts_resolution,
                "exception_type": exception_type,
                "exception_type_resolution": exception_type_resolution,
                "base_delay_ms": semantic_roles.get("base_delay_ms"),
                "max_delay_ms": semantic_roles.get("max_delay_ms"),
                "backoff_multiplier": semantic_roles.get("backoff_multiplier"),
                "retry_delay_policy_resolution": retry_delay_policy_resolution,
                "node_id": node.get("id"),
                "intent": node.get("intent"),
                "wrapper_kind": wrapper_label,
            }

        if wrapper_label == "timeout":
            timeout_ms = semantic_roles.get("timeout_ms")
            try:
                timeout_ms = int(timeout_ms)
            except (TypeError, ValueError):
                timeout_ms = 30000
            if timeout_ms < 1:
                timeout_ms = 1
            timeout_resolution = semantic_roles.get("timeout_resolution")
            if not timeout_resolution:
                if semantic_roles.get("timeout_ms") is not None or semantic_roles.get("max_duration_ms") is not None or semantic_roles.get("duration_ms") is not None:
                    timeout_resolution = "explicit_timeout_ms"
                else:
                    timeout_resolution = "default_timeout_ms"
            return {
                "type": "timeout",
                "body": body,
                "timeout_ms": timeout_ms,
                "timeout_resolution": timeout_resolution,
                "node_id": node.get("id"),
                "intent": node.get("intent"),
                "wrapper_kind": wrapper_label,
            }

        if wrapper_label == "transaction":
            transaction_resolution = semantic_roles.get("transaction_resolution") or "explicit_transaction_wrapper"
            return {
                "type": "transaction",
                "body": body,
                "transaction_resolution": transaction_resolution,
                "node_id": node.get("id"),
                "intent": node.get("intent"),
                "wrapper_kind": wrapper_label,
            }

        return {
            "type": "comment",
            "text": f"wrapper:{wrapper_label}",
            "node_id": node.get("id"),
            "intent": node.get("intent"),
        }
