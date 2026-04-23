# -*- coding: utf-8 -*-
from typing import Dict, Any, List, Set


class SpecAuditor:
    """StructuredSpecと合成結果の整合性を検査する軽量監査クラス。"""

    def __init__(self, knowledge_base=None):
        self.ukb = knowledge_base

    def _load_spec_audit_config(self) -> Dict[str, Any]:
        if self.ukb and hasattr(self.ukb, "get"):
            data = self.ukb.get("spec_audit", {})
            if isinstance(data, dict):
                return data
        return {}

    def audit(self, spec: Dict[str, Any], synthesis_result: Dict[str, Any]) -> List[str]:
        issues: List[str] = []
        trace = synthesis_result.get("trace", {})
        ir_tree = trace.get("ir_tree", {})
        best_path = trace.get("best_path", {})
        blueprint = trace.get("blueprint", {})
        audit_cfg = self._load_spec_audit_config()

        steps = spec.get("steps", []) if isinstance(spec.get("steps"), list) else []
        outputs = spec.get("outputs", []) if isinstance(spec.get("outputs"), list) else []

        # 1) Step emission coverage (node_id must appear in statements)
        statements = list(best_path.get("statements", []))
        if best_path.get("deferred_statements"):
            statements.extend(best_path.get("deferred_statements", []))
        emitted_node_ids = self._collect_node_ids(statements)
        emitted_node_ids.update(self._collect_node_ids(best_path.get("hoisted_statements", [])))
        for step in steps:
            step_id = step.get("id")
            if step.get("kind") in ["END", "ELSE"]:
                continue
            if not isinstance(step_id, str):
                continue
            if not self._is_step_emitted(step_id, emitted_node_ids):
                issues.append(f"SPEC_STEP_NOT_EMITTED|{step_id}")

        # 2) Side-effect intent coverage (DB/IO/NETWORK must align with IR nodes)
        nodes = self._flatten_ir_nodes(ir_tree.get("logic_tree", []))
        for step in steps:
            step_id = step.get("id")
            side_effect = step.get("side_effect")
            if not isinstance(step_id, str) or side_effect in [None, "NONE"]:
                continue
            aligned = self._has_side_effect_alignment(step_id, side_effect, nodes)
            if not aligned:
                issues.append(f"SPEC_SIDE_EFFECT_MISSING|{step_id}|{side_effect}")

        # 3) Intent coverage (IR node intent should be reflected in emitted statements)
        stmt_intents_by_node = self._collect_stmt_intents_by_node(statements)
        for node in nodes:
            node_id = node.get("id")
            intent = node.get("intent")
            node_type = node.get("type")
            if not isinstance(node_id, str) or not isinstance(intent, str):
                continue
            if node_type in ["ELSE", "END"]:
                continue
            if intent in ["GENERAL", "ACTION"]:
                continue
            if not self._is_intent_emitted(node_id, intent, stmt_intents_by_node):
                issues.append(f"SPEC_INTENT_NOT_EMITTED|{node_id}|{intent}")

        # 4) Output type alignment (only if spec declares output format)
        expected_type = ""
        if outputs:
            expected_type = str(outputs[0].get("type_format") or "").strip()
        actual_type = self._extract_blueprint_return_type(blueprint)
        if expected_type and actual_type and not self._type_equivalent(expected_type, actual_type, spec, steps):
            last_step_id = steps[-1].get("id") if steps else "step_last"
            issues.append(f"SPEC_OUTPUT_TYPE_MISMATCH|{last_step_id}|{expected_type}|{actual_type}")

        # 5) Dataflow linkage (input_link must consume upstream output)
        if nodes:
            issues.extend(
                self._audit_input_link_usage(
                    nodes,
                    statements,
                    best_path.get("type_to_vars", {})
                )
            )

        # 6) Dataflow linkage (input_refs declared in spec should be consumed)
        if nodes and steps:
            issues.extend(
                self._audit_input_refs_usage(
                    steps,
                    nodes,
                    statements,
                    best_path.get("type_to_vars", {})
                )
            )

        return issues

    def _collect_node_ids(self, statements: List[Dict[str, Any]]) -> Set[str]:
        ids: Set[str] = set()
        for stmt in statements:
            node_id = stmt.get("node_id")
            if isinstance(node_id, str):
                ids.add(node_id)
            for key in ["body", "else_body"]:
                if isinstance(stmt.get(key), list):
                    ids.update(self._collect_node_ids(stmt[key]))
        return ids

    def _collect_stmt_intents_by_node(self, statements: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        intents: Dict[str, Set[str]] = {}
        for stmt in statements:
            node_id = stmt.get("node_id")
            intent = stmt.get("intent")
            if isinstance(node_id, str) and isinstance(intent, str) and intent:
                intents.setdefault(node_id, set()).add(intent)
            for key in ["body", "else_body"]:
                if isinstance(stmt.get(key), list):
                    nested = self._collect_stmt_intents_by_node(stmt[key])
                    for k, vals in nested.items():
                        intents.setdefault(k, set()).update(vals)
        return intents

    def _is_step_emitted(self, step_id: str, emitted_node_ids: Set[str]) -> bool:
        if step_id in emitted_node_ids:
            return True
        prefix = f"{step_id}_"
        for node_id in emitted_node_ids:
            if node_id.startswith(prefix):
                return True
        return False

    def _is_intent_emitted(self, node_id: str, intent: str, intents_by_node: Dict[str, Set[str]]) -> bool:
        if intent in intents_by_node.get(node_id, set()):
            return True
        prefix = f"{node_id}_"
        for nid, intents in intents_by_node.items():
            if nid.startswith(prefix) and intent in intents:
                return True
        return False

    def _flatten_ir_nodes(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        flat: List[Dict[str, Any]] = []
        for node in nodes:
            if isinstance(node, dict):
                flat.append(node)
                if isinstance(node.get("children"), list):
                    flat.extend(self._flatten_ir_nodes(node["children"]))
                if isinstance(node.get("else_children"), list):
                    flat.extend(self._flatten_ir_nodes(node["else_children"]))
        return flat

    def _audit_input_link_usage(self, nodes: List[Dict[str, Any]], statements: List[Dict[str, Any]], type_to_vars: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        issues: List[str] = []
        audit_cfg = self._load_spec_audit_config()
        text_by_node = self._collect_statement_texts_by_node(statements)
        roles_by_node = self._collect_stmt_roles_by_node(statements)
        outputs_by_node = self._collect_node_outputs(statements)
        upstream_vars_by_node = self._collect_node_outputs_from_types(type_to_vars)
        var_sources = self._collect_var_sources(outputs_by_node, upstream_vars_by_node)
        last_used_by_node = self._collect_last_usage_node(statements, outputs_by_node, upstream_vars_by_node)
        downstream_by_input = self._collect_downstream_by_input(nodes)
        stmt_types_by_node = self._collect_stmt_types_by_node(statements)
        accumulator_vars = self._collect_vars_by_role(type_to_vars, "accumulator")

        for node in nodes:
            node_id = node.get("id")
            input_link = node.get("input_link")
            if not isinstance(node_id, str) or not isinstance(input_link, str):
                continue
            notification_roles = audit_cfg.get("notification_roles", ["notification"])
            if node.get("intent") == "DISPLAY" and any(r in roles_by_node.get(node_id, set()) for r in notification_roles):
                continue
            upstream_outputs = set()
            upstream_outputs.update(outputs_by_node.get(input_link, set()))
            upstream_outputs.update(upstream_vars_by_node.get(input_link, set()))
            if not upstream_outputs:
                continue
            node_texts = text_by_node.get(node_id, [])
            if not node_texts:
                # Fallback: allow node-id prefix matches (e.g., step_1 vs step_1_1)
                node_texts = self._collect_texts_by_prefix(node_id, text_by_node)
            if not node_texts:
                # Allow parent loop node usage for *_inner nodes
                if node_id.endswith("_inner"):
                    parent_id = node_id.rsplit("_inner", 1)[0]
                    parent_texts = text_by_node.get(parent_id, [])
                    if not parent_texts:
                        parent_texts = self._collect_texts_by_prefix(parent_id, text_by_node)
                    if parent_texts and self._any_var_used_in_texts(upstream_outputs, parent_texts):
                        continue
                issues.append(self._format_input_link_issue(node_id, input_link, upstream_outputs, node, last_used_by_node))
                continue
            if not self._any_var_used_in_texts(upstream_outputs, node_texts):
                if node.get("intent") == "DISPLAY":
                    semantic_roles = node.get("semantic_map", {}).get("semantic_roles", {}) or {}
                    display_scope = str(semantic_roles.get("display_scope") or "").lower()
                    if display_scope in ["after_loop", "afterloop", "post_loop", "postloop"]:
                        if accumulator_vars and self._any_var_used_in_texts(accumulator_vars, node_texts):
                            continue
                if node.get("intent") == "EXISTS":
                    if self._downstream_uses_upstream(node_id, upstream_outputs, downstream_by_input, text_by_node):
                        continue
                if self._is_loop_node(input_link, stmt_types_by_node):
                    if accumulator_vars and self._any_var_used_in_texts(accumulator_vars, node_texts):
                        continue
                    if self._uses_other_upstream_output(node_texts, input_link, var_sources):
                        continue
                if self._downstream_uses_upstream(node_id, upstream_outputs, downstream_by_input, text_by_node):
                    continue
                if node_id.endswith("_inner"):
                    parent_id = node_id.rsplit("_inner", 1)[0]
                    parent_texts = text_by_node.get(parent_id, [])
                    if not parent_texts:
                        parent_texts = self._collect_texts_by_prefix(parent_id, text_by_node)
                    if parent_texts and self._any_var_used_in_texts(upstream_outputs, parent_texts):
                        continue
                issues.append(self._format_input_link_issue(node_id, input_link, upstream_outputs, node, last_used_by_node))
        return issues

    def _collect_statement_texts_by_node(self, statements: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        texts: Dict[str, List[str]] = {}
        for stmt in statements:
            node_id = stmt.get("node_id")
            code_text = self._statement_text(stmt)
            if isinstance(node_id, str) and code_text:
                texts.setdefault(node_id, []).append(code_text)
            for key in ["body", "else_body"]:
                if isinstance(stmt.get(key), list):
                    nested = self._collect_statement_texts_by_node(stmt[key])
                    for k, vals in nested.items():
                        texts.setdefault(k, []).extend(vals)
        return texts

    def _statement_text(self, stmt: Dict[str, Any]) -> str:
        if not isinstance(stmt, dict):
            return ""
        if stmt.get("type") == "assign":
            return f"{stmt.get('var_name', '')} {stmt.get('value', '')}".strip()
        if stmt.get("type") == "call":
            method = stmt.get("method", "")
            if isinstance(method, tuple):
                method = method[0]
            args = stmt.get("args", [])
            return f"{method} {' '.join([str(a) for a in args])}".strip()
        if stmt.get("type") == "foreach":
            return f"{stmt.get('source', '')} {stmt.get('item_name', '')}".strip()
        if stmt.get("type") == "if":
            return str(stmt.get("condition", "") or "").strip()
        return str(stmt.get("code", "") or stmt.get("text", "") or "")

    def _collect_node_outputs(self, statements: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        outputs: Dict[str, Set[str]] = {}
        for stmt in statements:
            node_id = stmt.get("node_id")
            if isinstance(node_id, str):
                out_var = stmt.get("out_var")
                if isinstance(out_var, str) and out_var:
                    outputs.setdefault(node_id, set()).add(out_var)
                if stmt.get("type") == "foreach":
                    item_name = stmt.get("item_name")
                    if isinstance(item_name, str) and item_name:
                        outputs.setdefault(node_id, set()).add(item_name)
                if stmt.get("type") == "raw":
                    inferred = self._infer_out_var_from_raw(stmt.get("code", ""))
                    if inferred:
                        outputs.setdefault(node_id, set()).add(inferred)
            for key in ["body", "else_body"]:
                if isinstance(stmt.get(key), list):
                    nested = self._collect_node_outputs(stmt[key])
                    for k, vals in nested.items():
                        outputs.setdefault(k, set()).update(vals)
        return outputs

    def _infer_out_var_from_raw(self, code: str) -> str:
        if not isinstance(code, str):
            return ""
        needle = "var "
        idx = code.find(needle)
        if idx == -1:
            return ""
        i = idx + len(needle)
        while i < len(code) and code[i].isspace():
            i += 1
        start = i
        while i < len(code) and (code[i].isalnum() or code[i] == "_"):
            i += 1
        name = code[start:i]
        if not name:
            return ""
        eq_idx = code.find("=", i)
        if eq_idx == -1:
            return ""
        return name

    def _collect_node_outputs_from_types(self, type_to_vars: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Set[str]]:
        outputs: Dict[str, Set[str]] = {}
        if not isinstance(type_to_vars, dict):
            return outputs
        for vars_list in type_to_vars.values():
            if not isinstance(vars_list, list):
                continue
            for item in vars_list:
                if not isinstance(item, dict):
                    continue
                node_id = item.get("node_id")
                var_name = item.get("var_name")
                if isinstance(node_id, str) and isinstance(var_name, str) and var_name:
                    outputs.setdefault(node_id, set()).add(var_name)
        return outputs

    def _collect_last_usage_node(
        self,
        statements: List[Dict[str, Any]],
        outputs_by_node: Dict[str, Set[str]],
        upstream_vars_by_node: Dict[str, Set[str]]
    ) -> Dict[str, str]:
        last_used: Dict[str, str] = {}
        var_to_source: Dict[str, str] = {}
        for node_id, vars_set in outputs_by_node.items():
            for v in vars_set:
                var_to_source[v] = node_id
        for node_id, vars_set in upstream_vars_by_node.items():
            for v in vars_set:
                if v not in var_to_source:
                    var_to_source[v] = node_id

        def walk(stmts: List[Dict[str, Any]]):
            for stmt in stmts:
                node_id = stmt.get("node_id")
                text = self._statement_text(stmt)
                if isinstance(node_id, str) and text:
                    for v, source_id in var_to_source.items():
                        if self._contains_identifier(text, v):
                            last_used[source_id] = node_id
                for key in ["body", "else_body"]:
                    if isinstance(stmt.get(key), list):
                        walk(stmt[key])

        walk(statements)
        return last_used

    def _audit_input_refs_usage(
        self,
        steps: List[Dict[str, Any]],
        nodes: List[Dict[str, Any]],
        statements: List[Dict[str, Any]],
        type_to_vars: Dict[str, List[Dict[str, Any]]]
    ) -> List[str]:
        issues: List[str] = []
        audit_cfg = self._load_spec_audit_config()
        text_by_node = self._collect_statement_texts_by_node(statements)
        roles_by_node = self._collect_stmt_roles_by_node(statements)
        outputs_by_node = self._collect_node_outputs(statements)
        upstream_vars_by_node = self._collect_node_outputs_from_types(type_to_vars)
        last_used_by_node = self._collect_last_usage_node(statements, outputs_by_node, upstream_vars_by_node)
        step_order = [s.get("id") for s in steps if isinstance(s.get("id"), str)]

        for step in steps:
            step_id = step.get("id")
            input_refs = step.get("input_refs")
            if not isinstance(step_id, str) or not isinstance(input_refs, list) or not input_refs:
                continue
            if step.get("intent") == "DISPLAY":
                notification_roles = audit_cfg.get("notification_roles", ["notification"])
                if any(r in roles_by_node.get(step_id, set()) for r in notification_roles):
                    continue
            # Aggregate node texts for this step (including inner nodes)
            step_texts = text_by_node.get(step_id, [])
            if not step_texts:
                step_texts = self._collect_texts_by_prefix(step_id, text_by_node)
            if not step_texts:
                continue
            for ref_id in input_refs:
                if not isinstance(ref_id, str):
                    continue
                if ref_id == step_id:
                    continue
                if self._ref_consumed_via_auto_node(ref_id, step_texts, text_by_node, outputs_by_node):
                    continue
                upstream_outputs = set()
                upstream_outputs.update(outputs_by_node.get(ref_id, set()))
                upstream_outputs.update(upstream_vars_by_node.get(ref_id, set()))
                if not upstream_outputs:
                    continue
                if self._any_var_used_in_texts(upstream_outputs, step_texts):
                    continue
                if self._downstream_refs_use_upstream(step_order, step_id, upstream_outputs, text_by_node):
                    continue
                outputs_str = ",".join(sorted(upstream_outputs))
                recommend = ""
                if upstream_outputs:
                    preferred = sorted(upstream_outputs)[-1]
                    recommend = f"RECOMMEND=use:{preferred}"
                last_used = last_used_by_node.get(ref_id, "")
                drop_hint = f"DROP_AT={last_used}" if last_used else ""
                issues.append(f"SPEC_INPUT_REF_UNUSED|{step_id}|{ref_id}|{outputs_str}|{recommend}|{drop_hint}")
        return issues

    def _collect_downstream_by_input(self, nodes: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        mapping: Dict[str, List[str]] = {}
        for node in nodes:
            node_id = node.get("id")
            input_link = node.get("input_link")
            if isinstance(node_id, str) and isinstance(input_link, str):
                mapping.setdefault(input_link, []).append(node_id)
        return mapping

    def _downstream_uses_upstream(
        self,
        node_id: str,
        upstream_outputs: Set[str],
        downstream_by_input: Dict[str, List[str]],
        text_by_node: Dict[str, List[str]]
    ) -> bool:
        downstream_nodes = downstream_by_input.get(node_id, [])
        for downstream_id in downstream_nodes:
            texts = text_by_node.get(downstream_id, [])
            if texts and self._any_var_used_in_texts(upstream_outputs, texts):
                return True
        return False

    def _collect_texts_by_prefix(self, node_id: str, text_by_node: Dict[str, List[str]]) -> List[str]:
        prefix = f"{node_id}_"
        collected: List[str] = []
        for k, vals in text_by_node.items():
            if k == node_id or k.startswith(prefix):
                collected.extend(vals)
        return collected

    def _ref_consumed_via_auto_node(
        self,
        ref_id: str,
        step_texts: List[str],
        text_by_node: Dict[str, List[str]],
        outputs_by_node: Dict[str, Set[str]]
    ) -> bool:
        # Accept intermediate auto nodes (e.g., step_1_json) as satisfying the ref
        auto_node_ids = [k for k in text_by_node.keys() if isinstance(k, str) and k.startswith(f"{ref_id}_")]
        if not auto_node_ids:
            return False
        auto_outputs: Set[str] = set()
        for node_id in auto_node_ids:
            auto_outputs.update(outputs_by_node.get(node_id, set()))
        if not auto_outputs:
            return False
        return self._any_var_used_in_texts(auto_outputs, step_texts)

    def _collect_stmt_types_by_node(self, statements: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        types: Dict[str, Set[str]] = {}
        for stmt in statements:
            node_id = stmt.get("node_id")
            stmt_type = stmt.get("type")
            if isinstance(node_id, str) and isinstance(stmt_type, str):
                types.setdefault(node_id, set()).add(stmt_type)
            for key in ["body", "else_body"]:
                if isinstance(stmt.get(key), list):
                    nested = self._collect_stmt_types_by_node(stmt[key])
                    for k, vals in nested.items():
                        types.setdefault(k, set()).update(vals)
        return types

    def _collect_vars_by_role(self, type_to_vars: Dict[str, List[Dict[str, Any]]], role: str) -> Set[str]:
        vars_set: Set[str] = set()
        if not isinstance(type_to_vars, dict):
            return vars_set
        for vars_list in type_to_vars.values():
            if not isinstance(vars_list, list):
                continue
            for item in vars_list:
                if not isinstance(item, dict):
                    continue
                if item.get("role") == role and isinstance(item.get("var_name"), str):
                    vars_set.add(item["var_name"])
        return vars_set

    def _collect_var_sources(
        self,
        outputs_by_node: Dict[str, Set[str]],
        upstream_vars_by_node: Dict[str, Set[str]]
    ) -> Dict[str, str]:
        var_sources: Dict[str, str] = {}
        for node_id, vars_set in outputs_by_node.items():
            for v in vars_set:
                var_sources[v] = node_id
        for node_id, vars_set in upstream_vars_by_node.items():
            for v in vars_set:
                if v not in var_sources:
                    var_sources[v] = node_id
        return var_sources

    def _is_loop_node(self, node_id: str, stmt_types_by_node: Dict[str, Set[str]]) -> bool:
        if not isinstance(node_id, str):
            return False
        types = stmt_types_by_node.get(node_id, set())
        return "foreach" in types

    def _downstream_refs_use_upstream(
        self,
        step_order: List[str],
        step_id: str,
        upstream_outputs: Set[str],
        text_by_node: Dict[str, List[str]]
    ) -> bool:
        if step_id not in step_order:
            return False
        start_idx = step_order.index(step_id) + 1
        for downstream_id in step_order[start_idx:]:
            texts = text_by_node.get(downstream_id, [])
            if not texts:
                texts = self._collect_texts_by_prefix(downstream_id, text_by_node)
            if texts and self._any_var_used_in_texts(upstream_outputs, texts):
                return True
        return False

    def _uses_other_upstream_output(
        self,
        node_texts: List[str],
        input_link: str,
        var_sources: Dict[str, str]
    ) -> bool:
        for v, source_id in var_sources.items():
            if source_id == input_link:
                continue
            for t in node_texts:
                if self._contains_identifier(t or "", v):
                    return True
        return False

    def _any_var_used_in_texts(self, vars_set: Set[str], texts: List[str]) -> bool:
        for v in vars_set:
            for t in texts:
                if self._contains_identifier(t or "", v):
                    return True
        return False

    def _contains_identifier(self, text: str, ident: str) -> bool:
        if not ident or not text:
            return False
        for token in self._tokenize_identifiers(text):
            if token == ident:
                return True
        return False

    def _tokenize_identifiers(self, text: str) -> List[str]:
        tokens: List[str] = []
        current: List[str] = []
        for ch in str(text):
            if ch.isalnum() or ch == "_":
                current.append(ch)
            else:
                if current:
                    tokens.append("".join(current))
                    current = []
        if current:
            tokens.append("".join(current))
        return tokens

    def _collect_stmt_roles_by_node(self, statements: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        roles: Dict[str, Set[str]] = {}
        for stmt in statements:
            node_id = stmt.get("node_id")
            role = stmt.get("semantic_role")
            if isinstance(node_id, str) and isinstance(role, str) and role:
                roles.setdefault(node_id, set()).add(role)
            for key in ["body", "else_body"]:
                if isinstance(stmt.get(key), list):
                    nested = self._collect_stmt_roles_by_node(stmt[key])
                    for k, vals in nested.items():
                        roles.setdefault(k, set()).update(vals)
        return roles

    def _format_input_link_issue(self, node_id: str, input_link: str, upstream_outputs: Set[str], node: Dict[str, Any], last_used_by_node: Dict[str, str]) -> str:
        outputs_str = ",".join(sorted(upstream_outputs))
        intent = node.get("intent") or ""
        target = node.get("target_entity") or ""
        detail = f"{outputs_str}" if outputs_str else ""
        recommend = ""
        if upstream_outputs:
            preferred = sorted(upstream_outputs)[-1]
            recommend = f"RECOMMEND=use:{preferred}"
        last_used = last_used_by_node.get(input_link, "")
        drop_hint = f"DROP_AT={last_used}" if last_used else ""
        return f"SPEC_INPUT_LINK_UNUSED|{node_id}|{input_link}|{intent}|{target}|{detail}|{recommend}|{drop_hint}"

    def _has_side_effect_alignment(self, step_id: str, side_effect: str, nodes: List[Dict[str, Any]]) -> bool:
        audit_cfg = self._load_spec_audit_config()
        side_effects_cfg = audit_cfg.get("side_effects", {}) if isinstance(audit_cfg.get("side_effects"), dict) else {}
        relevant = [n for n in nodes if isinstance(n.get("id"), str) and (n["id"] == step_id or n["id"].startswith(f"{step_id}_"))]
        if not relevant:
            return False
        for node in relevant:
            intent = node.get("intent")
            source_kind = node.get("source_kind")
            if side_effect in side_effects_cfg:
                cfg = side_effects_cfg.get(side_effect, {})
                intents = cfg.get("intents", [])
                kinds = cfg.get("source_kinds", [])
                if (intent in intents) or (source_kind in kinds):
                    return True
                continue
            if side_effect == "DB":
                if intent in ["DATABASE_QUERY", "PERSIST"] or source_kind == "db":
                    return True
            elif side_effect == "IO":
                if intent in ["FETCH", "PERSIST", "FILE_IO", "WRITE"] or source_kind in ["file", "env", "stdin"]:
                    return True
            elif side_effect == "NETWORK":
                if intent in ["HTTP_REQUEST"] or source_kind == "http":
                    return True
        return False

    def _extract_blueprint_return_type(self, blueprint: Dict[str, Any]) -> str:
        methods = blueprint.get("methods", []) if isinstance(blueprint.get("methods"), list) else []
        if not methods:
            return ""
        return str(methods[0].get("return_type") or "").strip()

    def _type_equivalent(self, expected: str, actual: str, spec: Dict[str, Any], steps: List[Dict[str, Any]]) -> bool:
        def normalize(v: str) -> str:
            return v.replace(" ", "").lower()
        expected_n = normalize(expected)
        actual_n = normalize(actual)
        if expected_n == actual_n:
            return True
        # Allow Task<T> wrapping when spec implies async output
        if self._spec_allows_async(spec, steps):
            inner = self._unwrap_task(actual_n)
            if inner and inner == expected_n:
                return True
        return False

    def _unwrap_task(self, actual: str) -> str:
        if actual.startswith("task<") and actual.endswith(">"):
            return actual[len("task<"):-1]
        return ""

    def _spec_allows_async(self, spec: Dict[str, Any], steps: List[Dict[str, Any]]) -> bool:
        audit_cfg = self._load_spec_audit_config()
        async_markers = audit_cfg.get("async_markers", ["async", "非同期", "task"])
        async_side_effects = set(audit_cfg.get("async_side_effects", ["IO", "NETWORK", "DB"]))
        async_intents = set(audit_cfg.get("async_intents", ["DATABASE_QUERY", "HTTP_REQUEST", "FETCH", "PERSIST", "FILE_IO"]))

        outputs = spec.get("outputs", []) if isinstance(spec.get("outputs"), list) else []
        if outputs:
            desc = str(outputs[0].get("description") or "").lower()
            fmt = str(outputs[0].get("type_format") or "").lower()
            if any(k in desc for k in async_markers):
                return True
            if fmt.startswith("task"):
                return True
        for step in steps:
            if step.get("side_effect") in async_side_effects:
                return True
            if step.get("intent") in async_intents:
                return True
        return False
