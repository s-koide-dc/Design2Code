# -*- coding: utf-8 -*-
import json
import os
import copy
from typing import List, Dict, Any, Tuple, Optional

from src.utils.logic_auditor import LogicAuditor
from src.code_synthesis.type_system import TypeSystem
from src.utils.text_parser import extract_first_quoted_literal
from src.utils.entity_inference import infer_target_entity
from src.utils.stdout_guard import debug_print
from src.ir_generator.check_resolution import (
    normalize_check_operator,
    infer_null_check_subject_metadata,
    infer_check_target_entity,
    infer_check_metadata,
)
from src.ir_generator.promotion_rules import (
    has_calculation_intent_signal,
    has_filter_lexical_signal,
    has_filter_predicate_logic,
    has_upstream_collection_context,
    infer_filter_property,
    should_promote_to_filter,
    should_promote_to_calculate,
)
from src.ir_generator.target_resolution import (
    extract_entity_property_names,
    find_property_owner_entities,
    infer_calculate_target_entity,
    resolve_property_provenance,
)
from src.ir_generator.spec_role_rules import infer_spec_role
from src.ir_generator.return_resolution import (
    infer_return_metadata,
    has_literal_return_metadata,
    attach_return_source_metadata,
)
from src.ir_generator.transform_resolution import (
    infer_transform_metadata,
    attach_transform_source_metadata,
    has_transform_source_metadata,
)
from src.ir_generator.calculate_resolution import (
    infer_calculate_metadata,
    attach_calculate_target_metadata,
    attach_calculate_source_metadata,
    has_calculate_source_metadata,
)
from src.ir_generator.display_resolution import infer_display_property_metadata
from src.ir_generator.iterate_resolution import (
    infer_iterate_metadata,
    attach_iterate_source_metadata,
    has_iterate_source_metadata,
    attach_iterate_item_metadata,
)
from src.ir_generator.wrapper_resolution import infer_wrapper_metadata, has_wrapper_metadata_hint
from src.utils.semantic_intents import (
    INTENT_ACTION,
    INTENT_CALC,
    INTENT_DATABASE_QUERY,
    INTENT_DISPLAY,
    INTENT_EXISTS,
    INTENT_FETCH,
    INTENT_FILE_IO,
    INTENT_FILTER,
    INTENT_GENERAL,
    INTENT_RETURN,
    INTENT_HTTP_REQUEST,
    INTENT_JSON_DESERIALIZE,
    INTENT_LINQ,
    INTENT_PERSIST,
    INTENT_TRANSFORM,
    NODE_ACTION,
    NODE_CONDITION,
    NODE_ELSE,
    NODE_END,
    NODE_LOOP,
    ROLE_ACTION,
    ROLE_CALC,
    ROLE_CHECK,
    ROLE_DISPLAY,
    ROLE_FETCH,
    ROLE_FILTER,
    ROLE_ITERATE,
    ROLE_PERSIST,
    ROLE_READ,
    ROLE_RETURN,
    ROLE_TRANSFORM,
    ROLE_WRITE,
)

class SynthesisIntentDetector:
    """自然言語の概念（セマンティック・クラス）を技術的インテントにマッピングするクラス"""
    def __init__(self, vector_engine, knowledge_base=None):
        self.vector_engine = vector_engine
        self.kb = knowledge_base
        self.prototype_vectors = {}
        self.intent_semantic_clusters = {}
        if self.kb:
            if hasattr(self.kb, 'get'): self.intent_semantic_clusters = self.kb.get("common_patterns", {})
            elif hasattr(self.kb, 'canonical_data'): self.intent_semantic_clusters = self.kb.canonical_data.get("common_patterns", {})
        self._prepare_vectors_from_clusters()

    def _prepare_vectors_from_clusters(self):
        if not self.vector_engine: return
        for intent, phrases in self.intent_semantic_clusters.items():
            vectors = []
            for p in phrases:
                vec = self.vector_engine.get_sentence_vector([p])
                if vec is not None: vectors.append(vec)
            if vectors: self.prototype_vectors[intent] = vectors

    def detect(self, text: str, tokens: List[Dict[str, Any]] = None) -> Tuple[str, float]:
        if not self.vector_engine or not self.prototype_vectors:
            return INTENT_GENERAL, 0.0
        meaningful_words = [t["base"] for t in tokens if t["pos"].startswith(("名詞", "動詞"))] if tokens else [text]
        query_vec = self.vector_engine.get_sentence_vector(meaningful_words)
        if query_vec is None: return INTENT_GENERAL, 0.0
        best_intent, max_sim = INTENT_GENERAL, 0.0
        for intent, vectors in self.prototype_vectors.items():
            for v in vectors:
                sim = self.vector_engine.vector_similarity(query_vec, v)
                if sim > max_sim: max_sim = sim; best_intent = intent
        return best_intent, max_sim

class IRGenerator:
    """決定論的構文解析とセマンティック解析を組み合わせたIR生成クラス"""
    def __init__(self, config, knowledge_base=None, method_store=None, entity_schema=None, morph_analyzer=None, matcher=None):
        from src.morph_analyzer.morph_analyzer import MorphAnalyzer
        self.config = config
        self.morph_analyzer = morph_analyzer or MorphAnalyzer(config_manager=config)
        self.matcher = matcher
        self.ukb = knowledge_base 
        self.method_store = method_store
        self.logic_auditor = LogicAuditor(
            morph_analyzer=self.morph_analyzer,
            vector_engine=getattr(matcher, "vector_engine", None),
            knowledge_base=knowledge_base
        )
        self.entity_schema = entity_schema or {}
        self.intent_detector = SynthesisIntentDetector(getattr(matcher, 'vector_engine', None), knowledge_base=knowledge_base)
        self.type_system = TypeSystem()
        generation_cfg = {}
        if hasattr(config, "get_section"):
            generation_cfg = config.get_section("generation") or {}
        if not isinstance(generation_cfg, dict):
            generation_cfg = {}
        self.strict_semantics = bool(generation_cfg.get("strict_semantics", False))
        env_flag = os.environ.get("STRICT_SEMANTICS", "").lower()
        if env_flag in ["1", "true", "yes"]:
            self.strict_semantics = True

    def from_structured_spec(self, structured_spec: Dict[str, Any], intent_hint: str = None) -> Dict[Any, Any]:
        return self.generate(structured_spec, intent_hint=intent_hint)

    def generate(self, structured_spec: Dict[str, Any], intent_hint: str = None) -> Dict[Any, Any]:
        # Backward compatibility: allow list of step strings or dicts
        simple_list_input = False
        if isinstance(structured_spec, list):
            simple_list_input = True
            structured_spec = {"steps": structured_spec, "inputs": [], "outputs": [], "data_sources": []}
        strict_requested = isinstance(structured_spec, dict) and bool(structured_spec.get("strict_semantics"))
        design_steps = structured_spec.get("steps", [])
        inputs = structured_spec.get("inputs", [])
        outputs = structured_spec.get("outputs", [])
        data_sources = structured_spec.get("data_sources", [])
        nodes = []; context_history = []; block_stack = []
        last_node_id = None; main_entity = "Item"
        source_map = {ds["id"]: ds["kind"] for ds in data_sources}

        for idx, raw_step in enumerate(design_steps):
            # Phase 1: Raw step normalization and clause extraction
            raw_text = raw_step.get("text", "") if isinstance(raw_step, dict) else str(raw_step)
            if "[data_source|" in raw_text or any(inp.get("description") == raw_text for inp in inputs): continue
            if self.strict_semantics and strict_requested and isinstance(raw_step, dict):
                has_ops = bool((raw_step.get("semantic_roles") or {}).get("ops"))
                has_explicit = bool(raw_step.get("explicit_intent") or raw_step.get("explicit_semantic_roles"))
                if not has_ops and not has_explicit:
                    raise ValueError(f"Missing explicit intent/ops for step {raw_step.get('id')}: {raw_text}")
            if isinstance(raw_step, dict) and raw_step.get("semantic_roles", {}).get("ops"):
                clauses = [{"text": raw_text, "type": NODE_ACTION, "has_body": False}]
            else:
                clauses = self._extract_hierarchical_clauses(raw_text)
            if (
                isinstance(raw_step, dict)
                and clauses
                and has_wrapper_metadata_hint(raw_step.get("semantic_roles", {}) or {})
                and clauses[0].get("type") == NODE_ACTION
            ):
                wrapper_tokens = self.morph_analyzer.tokenize(raw_text) if self.morph_analyzer else []
                clauses[0]["has_body"] = clauses[0].get("has_body") or self._has_body_marker(raw_text, wrapper_tokens)
            if not clauses and isinstance(raw_step, dict) and raw_step.get("kind") in [NODE_END, NODE_ELSE]:
                clauses = [{"text": "", "type": raw_step.get("kind"), "has_body": True}]
            heuristics = self.ukb.get("entity_heuristics", {}) if (self.ukb and hasattr(self.ukb, 'get')) else {}
            if not isinstance(heuristics, dict):
                heuristics = {}
            
            step_intent_tag = raw_step.get("intent") if isinstance(raw_step, dict) else None
            if isinstance(step_intent_tag, str) and step_intent_tag in [INTENT_GENERAL, INTENT_ACTION, ""]:
                step_intent_tag = None
            source_ref = raw_step.get("source_ref") if isinstance(raw_step, dict) else None
            source_kind = raw_step.get("source_kind") if isinstance(raw_step, dict) else None
            if not source_kind and source_ref:
                source_kind = source_map.get(source_ref)
            
            # 27.422: Infer source_kind from extension if missing
            if not source_kind and source_ref:
                if any(ext in str(source_ref).lower() for ext in [".json", ".txt", ".csv", ".xml"]):
                    source_kind = "file"
                elif str(source_ref).lower().startswith("http"):
                    source_kind = "http"

            for sub_idx, c_info in enumerate(clauses):
                # Phase 2: Step-local semantic analysis and structure typing
                c_text = c_info["text"]; c_type = c_info["type"]
                step_entry = copy.deepcopy(raw_step) if isinstance(raw_step, dict) else {"text": c_text}
                step_entry["text"] = c_text
                
                # 27.154: Pass source_kind to analyze_step to ensure intent elevation
                analysis = self._analyze_step_integrated(
                    c_text,
                    context_history,
                    step_intent_tag or intent_hint,
                    source_kind=source_kind,
                    output_type_hint=step_entry.get("output_type"),
                )
                
                node_type = step_entry.get("kind") or c_type or analysis["node_type"]
                if step_entry.get("kind") in [NODE_ACTION, INTENT_GENERAL]:
                    if step_intent_tag:
                        node_type = NODE_ACTION
                    elif c_type in [NODE_CONDITION, NODE_ELSE, NODE_END, NODE_LOOP]:
                        node_type = c_type
                if sub_idx > 0 and node_type in [NODE_LOOP, NODE_CONDITION]:
                    node_type = NODE_ACTION
                
                target_entity = step_entry.get("target_entity") or analysis["target_entity"]
                weak_entities = heuristics.get("weak_entities", ["Item", "object"])
                if target_entity in weak_entities:
                    if analysis["target_entity"] not in weak_entities:
                        target_entity = analysis["target_entity"]
                    elif main_entity not in weak_entities:
                        target_entity = main_entity
                if target_entity not in weak_entities:
                    main_entity = target_entity
                final_semantic_map = copy.deepcopy(analysis["semantic_map"])
                if isinstance(step_entry, dict) and "semantic_roles" in step_entry:
                    if "semantic_roles" not in final_semantic_map:
                        final_semantic_map["semantic_roles"] = {}
                    for k, v in step_entry["semantic_roles"].items():
                        if v: final_semantic_map["semantic_roles"][k] = v
                if source_ref and source_kind == "file":
                    final_semantic_map.setdefault("semantic_roles", {}).setdefault("path", source_ref)
                if source_ref and source_kind == "env":
                    final_semantic_map.setdefault("semantic_roles", {}).setdefault("name", source_ref)

                analysis, final_semantic_map, target_entity = self._resolve_role_specific_semantics(
                    analysis,
                    final_semantic_map,
                    target_entity,
                    node_type,
                    c_info.get("has_body", False),
                    c_text,
                    source_kind,
                    source_ref,
                    context_history,
                    weak_entities,
                )
                
            # 27.162: STRICT INTENT LOCK.
            # Phase 4: Final intent/runtime-role coercion
            # This is the last place where coarse intent is normalized before
            # chaining, cardinality, and node emission are finalized.
            final_intent, final_role, source_kind = self._coerce_final_intent_and_role(
                step_intent_tag,
                analysis.get("intent", INTENT_GENERAL),
                analysis.get("role", ROLE_ACTION),
                node_type,
                final_semantic_map,
                source_kind,
            )
            analysis["role"] = final_role

            # Compute chaining after intent resolution to allow RETURN literals without upstream linkage
            is_chaining = (analysis.get("is_chaining") or sub_idx > 0)
            if final_intent == INTENT_RETURN and not analysis.get("is_chaining"):
                is_chaining = False
            is_notification = final_intent == INTENT_DISPLAY and bool(
                final_semantic_map.get("semantic_roles", {}).get("notification")
            )
            last_collection_id = self._find_last_collection_node_id(context_history)
            last_context_output = ""
            if context_history:
                last_context_output = str(context_history[-1].get("output_type") or "").lower()
            prefer_scalar_input = last_context_output in ["string", "int", "long", "decimal", "double", "float", "bool"]
            want_collection_input = (node_type == "LOOP" or final_intent in ["LINQ", "DISPLAY", "TRANSFORM", "CALC"])
            if final_intent == "PERSIST":
                want_collection_input = not prefer_scalar_input
            input_link = self._determine_structural_input_link(
                block_stack,
                is_chaining,
                last_node_id,
                last_collection_id,
                want_collection_input,
                is_notification,
                final_intent,
            )
            if isinstance(step_entry, dict) and step_entry.get("input_refs"):
                if final_intent == "PERSIST":
                    input_link = step_entry["input_refs"][0]
            if final_intent == "RETURN":
                tokens = analysis.get("tokens") or []
                semantic_roles = final_semantic_map.get("semantic_roles", {}) or {}
                if has_literal_return_metadata(semantic_roles) or self._is_literal_return(c_text, tokens):
                    input_link = None
                else:
                    return_source_node_id = self._resolve_semantic_source_node_id(nodes, input_link)
                    final_semantic_map["semantic_roles"] = attach_return_source_metadata(
                        semantic_roles,
                        return_source_node_id,
                    )
            elif final_intent == "TRANSFORM":
                semantic_roles = final_semantic_map.get("semantic_roles", {}) or {}
                if not has_transform_source_metadata(semantic_roles):
                    transform_source_node_id = self._resolve_semantic_source_node_id(nodes, input_link)
                    final_semantic_map["semantic_roles"] = attach_transform_source_metadata(
                        semantic_roles,
                        transform_source_node_id,
                    )
            elif final_intent == "CALC":
                semantic_roles = final_semantic_map.get("semantic_roles", {}) or {}
                if not has_calculate_source_metadata(semantic_roles):
                    calculate_source_node_id = self._resolve_semantic_source_node_id(nodes, input_link)
                    final_semantic_map["semantic_roles"] = attach_calculate_source_metadata(
                        semantic_roles,
                        calculate_source_node_id,
                    )
            elif node_type == "LOOP":
                semantic_roles = final_semantic_map.get("semantic_roles", {}) or {}
                if not has_iterate_source_metadata(semantic_roles):
                    iterate_source_node_id = self._resolve_semantic_source_node_id(nodes, input_link)
                    final_semantic_map["semantic_roles"] = attach_iterate_source_metadata(
                        semantic_roles,
                        iterate_source_node_id,
                    )

            # Phase 5: Node emission and structural attachment
            # If explicit input_link exists, avoid forcing "{context}" content
            if input_link and final_semantic_map.get("semantic_roles", {}).get("content") == "{context}":
                del final_semantic_map["semantic_roles"]["content"]

            output_type_hint = step_entry.get("output_type") or analysis.get("output_type")
            source_kind = self._resolve_final_source_kind(source_kind, final_intent, final_semantic_map, context_history)
            node_id = step_entry.get('id', f"step_{idx+1}")
            if len(clauses) > 1: node_id = f"{node_id}_{sub_idx+1}"
            
            node = self._build_ir_node(
                node_id,
                node_type,
                c_text,
                final_intent,
                analysis["role"],
                analysis["cardinality"],
                target_entity,
                step_entry.get("output_type") or analysis.get("output_type"),
                output_type_hint,
                source_kind,
                source_ref,
                final_semantic_map,
                input_link,
            )
            if step_entry.get("explicit_method_id"):
                node["explicit_method_id"] = step_entry.get("explicit_method_id")
            if step_entry.get("explicit_method_name"):
                node["explicit_method_name"] = step_entry.get("explicit_method_name")

            if final_intent == "PERSIST" and prefer_scalar_input and last_node_id:
                if node.get("input_link") != last_node_id:
                    node["input_link"] = last_node_id
            
            # 27.440: Phase 7 F-1 Auto-Chaining for JSON Deserialization
            if not simple_list_input:
                auto_json_node = self._maybe_insert_json_deserialize_node(
                    nodes,
                    block_stack,
                    node,
                    node_id,
                    final_intent,
                    source_kind,
                    c_text,
                    target_entity,
                    context_history,
                )
                if auto_json_node is not None:
                    last_node_id = auto_json_node["id"]
                    continue

            # 27.450: Phase 7 F-1 Auto-Chaining for JSON Serialization (Reverse of 27.440)
            # If intent is PERSIST and we have a COLLECTION coming in,
            # we need to serialize the collection to string first.
            is_coll_input = self._has_collection_input_context(context_history)
            
            debug_print(
                f"[DEBUG] IRGen: node_id={node_id}, intent={final_intent}, "
                f"is_coll_input={is_coll_input}, source_kind={source_kind}"
            )
            if not simple_list_input:
                self._maybe_insert_json_serialize_node(
                    nodes,
                    block_stack,
                    node,
                    node_id,
                    final_intent,
                    source_kind,
                    target_entity,
                    input_link,
                    last_node_id,
                    context_history,
                    is_coll_input,
                )
                        
            if node_type == "ELSE":
                self._handle_else_clause(block_stack, context_history, c_text, main_entity, source_kind, node_id)
                continue
            if node_type == "END":
                self._handle_end_clause(block_stack)
                continue
            skipped_node_id = self._maybe_skip_redundant_database_query(
                nodes,
                last_node_id,
                final_intent,
                target_entity,
                final_semantic_map,
                context_history,
                c_text,
            )
            if skipped_node_id:
                last_node_id = skipped_node_id
                continue
            self._attach_node_to_structure(nodes, block_stack, node)
            if node_type in ["CONDITION", "LOOP"] or c_info.get("has_body"):
                self._push_structural_block(block_stack, node)
            self._append_context_history(
                context_history,
                c_text,
                target_entity,
                node.get("cardinality"),
                node.get("output_type"),
                node.get("source_kind"),
                node["id"],
                node.get("semantic_map", {}).get("semantic_roles", {}),
            )
            last_node_id = node["id"]
        return {"logic_tree": nodes, "inputs": inputs or [], "outputs": outputs or [], "data_sources": data_sources}

    def _find_node_by_id(self, nodes: List[Dict[str, Any]], target_id: str) -> Optional[Dict[str, Any]]:
        for node in nodes:
            if node.get("id") == target_id:
                return node
            for child_key in ["children", "else_children"]:
                if child_key in node and isinstance(node[child_key], list):
                    found = self._find_node_by_id(node[child_key], target_id)
                    if found:
                        return found
        return None

    # Domain: Orchestration Control
    # These helpers keep clause-control and duplicate suppression readable
    # while leaving the top-level generation flow intact.
    def _append_context_history(
        self,
        context_history: List[Dict[str, Any]],
        text: str,
        target_entity: str,
        cardinality: Optional[str],
        output_type: Optional[str],
        source_kind: Optional[str],
        node_id: Optional[str] = None,
        extra_semantics: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = {
            "text": text,
            "target_entity": target_entity,
            "cardinality": cardinality,
            "output_type": output_type,
            "source_kind": source_kind,
            "node_id": node_id,
        }
        if isinstance(extra_semantics, dict):
            item_entity = str(extra_semantics.get("iteration_item_entity") or "").strip()
            item_resolution = str(extra_semantics.get("iteration_item_resolution") or "").strip()
            item_var = str(extra_semantics.get("iteration_item_var") or "").strip()
            item_var_resolution = str(extra_semantics.get("iteration_item_var_resolution") or "").strip()
            if item_entity:
                entry["item_entity"] = item_entity
            if item_resolution:
                entry["item_resolution"] = item_resolution
            if item_var:
                entry["item_var"] = item_var
            if item_var_resolution:
                entry["item_var_resolution"] = item_var_resolution
        context_history.append(entry)

    def _handle_else_clause(
        self,
        block_stack: List[Dict[str, Any]],
        context_history: List[Dict[str, Any]],
        step_text: str,
        main_entity: str,
        source_kind: Optional[str],
        node_id: str,
    ) -> None:
        if block_stack:
            self._activate_else_branch(block_stack)
        self._append_context_history(
            context_history,
            step_text,
            main_entity,
            "SINGLE",
            None,
            source_kind,
            node_id,
        )

    def _handle_end_clause(self, block_stack: List[Dict[str, Any]]) -> None:
        if block_stack:
            block_stack.pop()

    def _maybe_skip_redundant_database_query(
        self,
        nodes: List[Dict[str, Any]],
        last_node_id: Optional[str],
        final_intent: str,
        target_entity: str,
        final_semantic_map: Dict[str, Any],
        context_history: List[Dict[str, Any]],
        step_text: str,
    ) -> Optional[str]:
        if final_intent != "DATABASE_QUERY" or not last_node_id:
            return None
        prev_node = self._find_node_by_id(nodes, last_node_id)
        prev_map = prev_node.get("semantic_map", {}) if isinstance(prev_node, dict) else {}
        prev_sql = prev_map.get("semantic_roles", {}).get("sql")
        curr_sql = final_semantic_map.get("semantic_roles", {}).get("sql")
        if prev_node and prev_node.get("intent") == INTENT_DATABASE_QUERY and prev_node.get("target_entity") == target_entity and prev_sql and curr_sql and prev_sql == curr_sql:
            self._append_context_history(
                context_history,
                step_text,
                target_entity,
                prev_node.get("cardinality"),
                prev_node.get("output_type"),
                prev_node.get("source_kind"),
                None,
                prev_map.get("semantic_roles", {}),
            )
            return prev_node.get("id")
        return None

    # Domain: Final Intent / Runtime Role Coercion
    # These rules normalize coarse intent into the runtime-facing form used for
    # chaining and node emission, while preserving spec-role semantics upstream.
    def _coerce_final_intent_and_role(
        self,
        step_intent_tag: Optional[str],
        analysis_intent: str,
        analysis_role: str,
        node_type: str,
        final_semantic_map: Dict[str, Any],
        source_kind: Optional[str],
    ) -> Tuple[str, str, Optional[str]]:
        final_intent = step_intent_tag or analysis_intent
        role = analysis_role
        if final_semantic_map.get("spec_role") == "CHECK":
            final_intent = INTENT_EXISTS
        is_explicit_intent = isinstance(step_intent_tag, str) and bool(step_intent_tag)
        if node_type in [NODE_CONDITION, NODE_ACTION] and final_intent in [INTENT_GENERAL, INTENT_HTTP_REQUEST, INTENT_FILTER]:
            if not (is_explicit_intent and step_intent_tag in [INTENT_HTTP_REQUEST, INTENT_DATABASE_QUERY, INTENT_PERSIST, INTENT_FETCH]):
                if any(lg.get("type") in ["numeric", "string", "logic"] for lg in final_semantic_map.get("logic", [])):
                    final_intent = INTENT_LINQ
        elif node_type == NODE_CONDITION and final_intent in [INTENT_GENERAL, INTENT_HTTP_REQUEST]:
            final_intent = INTENT_LINQ
        if final_intent in [INTENT_GENERAL, INTENT_ACTION] and "url" in final_semantic_map.get("semantic_roles", {}):
            final_intent = INTENT_HTTP_REQUEST
            source_kind = source_kind or "http"
        if final_intent in [INTENT_GENERAL, INTENT_ACTION] and "sql" in final_semantic_map.get("semantic_roles", {}):
            final_intent = INTENT_PERSIST
            source_kind = source_kind or "db"
        if node_type == NODE_LOOP:
            final_intent = INTENT_GENERAL
            role = ROLE_ITERATE
        elif final_semantic_map.get("spec_role") == "WRAP":
            final_intent = INTENT_GENERAL
            role = ROLE_ACTION
        if step_intent_tag == INTENT_DATABASE_QUERY:
            has_sql = "sql" in final_semantic_map.get("semantic_roles", {})
            if source_kind != "db" and not has_sql:
                final_intent = INTENT_FETCH
        if final_intent == INTENT_PERSIST:
            role = ROLE_PERSIST
        elif final_intent in [INTENT_DATABASE_QUERY, INTENT_FETCH]:
            role = ROLE_FETCH
        elif final_intent == INTENT_DISPLAY:
            role = ROLE_DISPLAY
        elif final_intent == INTENT_EXISTS:
            role = ROLE_CHECK
        elif final_intent == INTENT_HTTP_REQUEST:
            if "payload" in final_semantic_map.get("semantic_roles", {}) or "content" in final_semantic_map.get("semantic_roles", {}):
                role = ROLE_PERSIST
        return final_intent, role, source_kind

    # Domain: Node Emission
    # These helpers prepare source/cardinality/runtime shape immediately before
    # node creation without moving auto-inserted nodes out of the main flow.
    def _resolve_final_source_kind(
        self,
        source_kind: Optional[str],
        final_intent: str,
        final_semantic_map: Dict[str, Any],
        context_history: List[Dict[str, Any]],
    ) -> Optional[str]:
        if not source_kind:
            if "path" in final_semantic_map.get("semantic_roles", {}):
                path_val = final_semantic_map["semantic_roles"]["path"]
                if any(ext in str(path_val).lower() for ext in [".json", ".txt", ".csv", ".xml"]):
                    source_kind = "file"
            elif "url" in final_semantic_map.get("semantic_roles", {}):
                source_kind = "http"
        if not source_kind and final_intent in [INTENT_PERSIST, INTENT_FILE_IO, "WRITE", INTENT_FETCH]:
            for entry in reversed(context_history or []):
                if entry.get("source_kind"):
                    return entry["source_kind"]
        return source_kind

    def _compute_final_cardinality(
        self,
        analysis_cardinality: str,
        node_type: str,
        final_intent: str,
        output_type_hint: Optional[str],
    ) -> str:
        final_cardinality = analysis_cardinality
        if node_type == NODE_LOOP:
            final_cardinality = "COLLECTION"
        if final_cardinality == "SINGLE" and final_intent in [INTENT_LINQ, INTENT_DATABASE_QUERY, INTENT_JSON_DESERIALIZE]:
            if self._is_collection_type(output_type_hint):
                final_cardinality = "COLLECTION"
        if output_type_hint in ["string", "int", "long", "decimal", "double", "float", "bool"]:
            final_cardinality = "SINGLE"
        if final_cardinality == "COLLECTION" and node_type != NODE_LOOP:
            if final_intent not in [INTENT_LINQ, INTENT_DATABASE_QUERY, INTENT_JSON_DESERIALIZE, INTENT_FETCH]:
                if not self._is_collection_type(output_type_hint):
                    final_cardinality = "SINGLE"
        return final_cardinality

    def _build_ir_node(
        self,
        node_id: str,
        node_type: str,
        original_text: str,
        final_intent: str,
        role: str,
        analysis_cardinality: str,
        target_entity: str,
        output_type: Optional[str],
        output_type_hint: Optional[str],
        source_kind: Optional[str],
        source_ref: Optional[str],
        final_semantic_map: Dict[str, Any],
        input_link: Optional[str],
    ) -> Dict[str, Any]:
        final_cardinality = self._compute_final_cardinality(
            analysis_cardinality,
            node_type,
            final_intent,
            output_type_hint,
        )
        return {
            "id": node_id,
            "type": node_type,
            "original_text": original_text,
            "intent": final_intent,
            "role": role,
            "cardinality": final_cardinality,
            "target_entity": target_entity,
            "output_type": output_type,
            "source_kind": source_kind,
            "source_ref": source_ref,
            "semantic_map": final_semantic_map,
            "input_link": input_link,
            "children": [],
            "else_children": [],
        }

    # Domain: Role-Specific Semantic Resolution
    # This stage enriches the step-local semantic map before runtime coercion.
    def _resolve_role_specific_semantics(
        self,
        analysis: Dict[str, Any],
        final_semantic_map: Dict[str, Any],
        target_entity: str,
        node_type: str,
        has_body: bool,
        step_text: str,
        source_kind: Optional[str],
        source_ref: Optional[str],
        context_history: List[Dict[str, Any]],
        weak_entities: List[str],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        if node_type == "LOOP":
            final_semantic_map["spec_role"] = "ITERATE"
            final_semantic_map["semantic_roles"] = infer_iterate_metadata(
                final_semantic_map.get("semantic_roles", {}) or {},
            )
            semantic_roles = final_semantic_map.get("semantic_roles", {}) or {}
            upstream_item_entity = None
            item_resolution = None
            explicit_item_entity = str(semantic_roles.get("iteration_item_entity") or "").strip()
            explicit_item_resolution = str(semantic_roles.get("iteration_item_resolution") or "").strip()
            if explicit_item_entity:
                upstream_item_entity = explicit_item_entity
                item_resolution = explicit_item_resolution or "explicit_item_entity"
            elif context_history:
                last_context = context_history[-1]
                last_output_type = str(last_context.get("output_type") or "")
                last_target_entity = str(last_context.get("target_entity") or "")
                inner = self.type_system.extract_generic_inner(last_output_type)
                if inner:
                    upstream_item_entity = inner
                    item_resolution = "collection_inner"
                elif last_target_entity and last_target_entity not in weak_entities and last_context.get("cardinality") == "COLLECTION":
                    upstream_item_entity = last_target_entity
                    item_resolution = "history_collection_entity"
            if upstream_item_entity:
                final_semantic_map["semantic_roles"] = attach_iterate_item_metadata(
                    semantic_roles,
                    upstream_item_entity,
                    item_resolution,
                )
                if target_entity in weak_entities:
                    target_entity = upstream_item_entity
        elif node_type == "CONDITION":
            final_semantic_map["spec_role"] = "CHECK"
            final_semantic_map.setdefault("semantic_roles", {}).setdefault("structure_kind", "condition")
        elif has_body and node_type == "ACTION" and self._is_wrapper_action(
            analysis.get("tokens") or [],
            final_semantic_map.get("semantic_roles", {}) or {},
        ):
            final_semantic_map["spec_role"] = "WRAP"
            semantic_roles = infer_wrapper_metadata(
                analysis.get("tokens") or [],
                final_semantic_map.get("semantic_roles", {}) or {},
            )
            final_semantic_map["semantic_roles"] = semantic_roles

        if final_semantic_map.get("spec_role") == "CHECK":
            check_meta = self._infer_check_metadata(
                step_text,
                analysis.get("tokens") or [],
                final_semantic_map.get("logic", []) or [],
                source_kind,
                source_ref,
                target_entity,
                node_type,
            )
            for meta_key, meta_value in check_meta.items():
                if meta_value is not None:
                    final_semantic_map[meta_key] = meta_value
            if check_meta.get("check_kind") == "comparison_check":
                canonical_property, property_resolution = self._resolve_property_provenance(
                    check_meta.get("check_subject"),
                    target_entity,
                )
                if canonical_property and property_resolution == "schema_property":
                    final_semantic_map["check_subject"] = canonical_property
                    final_semantic_map["subject_resolution"] = "schema_property"
                elif canonical_property and property_resolution == "history_scope":
                    final_semantic_map["check_subject"] = canonical_property
                    final_semantic_map["subject_resolution"] = "history_subject"
            target_entity = self._infer_check_target_entity(target_entity, check_meta, context_history, weak_entities)

        if final_semantic_map.get("spec_role") == "RETURN":
            final_semantic_map["semantic_roles"] = infer_return_metadata(
                step_text,
                analysis.get("tokens") or [],
                final_semantic_map.get("semantic_roles", {}) or {},
            )

        if final_semantic_map.get("spec_role") == "TRANSFORM":
            final_semantic_map["semantic_roles"] = infer_transform_metadata(
                final_semantic_map.get("semantic_roles", {}) or {},
            )

        if final_semantic_map.get("spec_role") == "CALCULATE":
            final_semantic_map["semantic_roles"] = infer_calculate_metadata(
                final_semantic_map.get("semantic_roles", {}) or {},
            )

        if final_semantic_map.get("spec_role") == "DISPLAY":
            final_semantic_map["semantic_roles"] = infer_display_property_metadata(
                self.entity_schema,
                analysis.get("tokens") or [],
                final_semantic_map.get("semantic_roles", {}) or {},
                target_entity,
            )

        if self._should_promote_to_calculate(
            analysis.get("intent", "GENERAL"),
            node_type,
            step_text,
            analysis.get("tokens") or [],
            final_semantic_map.get("logic", []) or [],
            final_semantic_map.get("semantic_roles", {}) or {},
        ):
            analysis["intent"] = "CALC"
            analysis["role"] = "CALC"
            final_semantic_map["spec_role"] = "CALCULATE"
            calculate_roles = final_semantic_map.get("semantic_roles", {}) or {}
            calculate_base_entity = calculate_roles.get("target_entity") or target_entity
            target_entity, entity_resolution = self._infer_calculate_target_entity(
                calculate_base_entity,
                calculate_roles,
                context_history,
                weak_entities,
            )
            semantic_roles = final_semantic_map.setdefault("semantic_roles", {})
            semantic_roles["target_entity"] = target_entity
            semantic_roles["entity_resolution"] = entity_resolution
            canonical_property, property_resolution = self._resolve_property_provenance(
                semantic_roles.get("property") or semantic_roles.get("target_hint"),
                target_entity,
            )
            final_semantic_map["semantic_roles"] = attach_calculate_target_metadata(
                semantic_roles,
                canonical_property,
                property_resolution,
            )

        return analysis, final_semantic_map, target_entity

    def _has_collection_input_context(self, context_history: List[Dict[str, Any]]) -> bool:
        if not context_history:
            return False
        return context_history[-1].get("cardinality") == "COLLECTION"

    def _append_node_in_current_structure(
        self,
        nodes: List[Dict[str, Any]],
        block_stack: List[Dict[str, Any]],
        node: Dict[str, Any],
    ) -> None:
        if block_stack:
            parent = block_stack[-1]
            parent["node"][parent["target"]].append(node)
            return
        nodes.append(node)

    def _maybe_insert_json_deserialize_node(
        self,
        nodes: List[Dict[str, Any]],
        block_stack: List[Dict[str, Any]],
        node: Dict[str, Any],
        node_id: str,
        final_intent: str,
        source_kind: Optional[str],
        step_text: str,
        target_entity: str,
        context_history: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        output_type = node.get("output_type")
        if not output_type or not any(k in output_type for k in ["List", "[]", "IEnumerable", "Collection"]):
            return None
        if final_intent not in ["FETCH", "HTTP_REQUEST", "FILE_IO"] or source_kind not in ["file", "http", "api"]:
            return None

        node["output_type"] = "string"
        self._append_node_in_current_structure(nodes, block_stack, node)

        json_node = copy.deepcopy(node)
        json_node["id"] = f"{node_id}_json"
        json_node["intent"] = "JSON_DESERIALIZE"
        json_node["role"] = "TRANSFORM"
        json_node["output_type"] = output_type
        json_node["source_kind"] = "memory"
        json_node["semantic_map"]["semantic_roles"] = {}
        json_node["semantic_map"]["spec_role"] = "DESERIALIZE"
        inner = self.type_system.extract_generic_inner(str(output_type))
        if inner:
            json_node["target_entity"] = inner
        elif str(output_type).endswith("[]"):
            json_node["target_entity"] = str(output_type)[:-2].strip()

        self._append_node_in_current_structure(nodes, block_stack, json_node)
        context_history.append({
            "text": step_text,
            "target_entity": target_entity,
            "cardinality": "COLLECTION",
            "output_type": output_type,
            "source_kind": "memory",
            "node_id": json_node["id"],
        })
        return json_node

    def _is_string_like_upstream_output(
        self,
        nodes: List[Dict[str, Any]],
        input_link: Optional[str],
        last_node_id: Optional[str],
        context_history: List[Dict[str, Any]],
    ) -> bool:
        prev_ref = input_link or last_node_id
        if prev_ref:
            prev_node = self._find_node_by_id(nodes, prev_ref)
            if prev_node:
                if str(prev_node.get("output_type") or "").lower() == "string":
                    return True
                if prev_node.get("intent") == "DISPLAY":
                    return True
        if context_history:
            return str(context_history[-1].get("output_type") or "").lower() == "string"
        return False

    def _maybe_insert_json_serialize_node(
        self,
        nodes: List[Dict[str, Any]],
        block_stack: List[Dict[str, Any]],
        node: Dict[str, Any],
        node_id: str,
        final_intent: str,
        source_kind: Optional[str],
        target_entity: str,
        input_link: Optional[str],
        last_node_id: Optional[str],
        context_history: List[Dict[str, Any]],
        is_coll_input: bool,
    ) -> None:
        if final_intent not in ["PERSIST", "FILE_IO", "WRITE"] or source_kind not in ["file", "http", "api"]:
            return
        is_poco_input = bool(target_entity and target_entity != "Item")
        if not (is_coll_input or node.get("cardinality") == "COLLECTION" or is_poco_input):
            return
        if self._is_string_like_upstream_output(nodes, input_link, last_node_id, context_history):
            return

        serialize_node = copy.deepcopy(node)
        serialize_node["id"] = f"{node_id}_ser"
        serialize_node["intent"] = "TRANSFORM"
        serialize_node["role"] = "TRANSFORM"
        serialize_node["output_type"] = "string"
        serialize_node["source_kind"] = "memory"
        serialize_node["semantic_map"]["semantic_roles"] = {}
        serialize_node["semantic_map"]["spec_role"] = "SERIALIZE"
        self._append_node_in_current_structure(nodes, block_stack, serialize_node)
        node["input_link"] = serialize_node["id"]
        node["cardinality"] = "SINGLE"

    # Domain: Structural Dependency
    # These helpers keep chaining and block-attachment rules local without
    # moving the whole generate() control flow out of the main path.
    def _find_last_collection_node_id(self, history: List[Dict[str, Any]]) -> Optional[str]:
        for entry in reversed(history or []):
            if entry.get("cardinality") == "COLLECTION" and entry.get("node_id"):
                return entry.get("node_id")
        return None

    def _determine_structural_input_link(
        self,
        block_stack: List[Dict[str, Any]],
        is_chaining: bool,
        last_node_id: Optional[str],
        last_collection_id: Optional[str],
        want_collection_input: bool,
        is_notification: bool,
        final_intent: str,
    ) -> Optional[str]:
        if not (is_chaining and last_node_id):
            return None
        if is_notification and final_intent == "DISPLAY":
            return None

        active_block = block_stack[-1] if block_stack else None
        if active_block and active_block.get("target") == "else_children":
            return active_block.get("branch_last_id") or active_block.get("branch_base")
        if active_block and active_block.get("branch_last_id"):
            return active_block.get("branch_last_id")
        if active_block and active_block.get("branch_base") and active_block.get("branch_last_id") is None:
            return active_block.get("branch_base")
        if want_collection_input and last_collection_id:
            return last_collection_id
        return last_node_id

    def _activate_else_branch(self, block_stack: List[Dict[str, Any]]) -> None:
        for entry in reversed(block_stack):
            if entry["node"]["type"] == "CONDITION":
                entry["target"] = "else_children"
                entry["branch_base"] = entry["node"]["id"]
                entry["branch_last_id"] = None
                return

    def _attach_node_to_structure(
        self,
        nodes: List[Dict[str, Any]],
        block_stack: List[Dict[str, Any]],
        node: Dict[str, Any],
    ) -> None:
        if block_stack:
            parent = block_stack[-1]
            parent["node"][parent["target"]].append(node)
            parent["branch_last_id"] = node["id"]
            return
        nodes.append(node)

    def _push_structural_block(self, block_stack: List[Dict[str, Any]], node: Dict[str, Any]) -> None:
        block_stack.append({
            "node": node,
            "target": "children",
            "branch_base": node["id"],
            "branch_last_id": None,
        })

    def _find_node_by_id(self, nodes: List[Dict[str, Any]], node_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not node_id:
            return None
        for node in nodes or []:
            if node.get("id") == node_id:
                return node
            found = self._find_node_by_id(node.get("children", []), node_id)
            if found:
                return found
            found = self._find_node_by_id(node.get("else_children", []), node_id)
            if found:
                return found
        return None

    def _resolve_semantic_source_node_id(
        self,
        nodes: List[Dict[str, Any]],
        input_link: Optional[str],
    ) -> Optional[str]:
        if not input_link:
            return None
        linked = self._find_node_by_id(nodes, input_link)
        if not linked:
            return input_link
        linked_spec_role = str(linked.get("semantic_map", {}).get("spec_role") or "").strip().upper()
        if linked_spec_role == "CHECK" and linked.get("input_link"):
            return str(linked.get("input_link"))
        return input_link

    def _extract_hierarchical_clauses(self, text: str) -> List[Dict[str, Any]]:
        if not text:
            return []
        tokens = []
        if self.morph_analyzer:
            tokens = self.morph_analyzer.tokenize(text)
        clause_type, has_body = self._detect_control_clause(text, tokens)
        return [{"text": text, "type": clause_type, "has_body": has_body}]

    def _detect_control_clause(self, text: str, tokens: List[Dict[str, Any]]) -> Tuple[str, bool]:
        has_body = self._has_body_marker(text, tokens)
        if self._is_end_clause(tokens):
            return "END", False
        if self._is_else_clause(tokens):
            return "ELSE", has_body
        if self._is_condition_clause(tokens):
            return "CONDITION", has_body
        if self._is_retry_wrapper(tokens) and has_body:
            return "ACTION", True
        if self._is_loop_clause(tokens):
            return "LOOP", has_body
        return "ACTION", False

    def _token_bases(self, tokens: List[Dict[str, Any]]) -> List[str]:
        bases = []
        for t in tokens or []:
            base = t.get("base")
            if base:
                bases.append(str(base))
        return bases

    def _token_surfaces(self, tokens: List[Dict[str, Any]]) -> List[str]:
        surfaces = []
        for t in tokens or []:
            surf = t.get("surface")
            if surf:
                surfaces.append(str(surf))
        return surfaces

    def _contains_base(self, tokens: List[Dict[str, Any]], candidates: List[str]) -> bool:
        base_set = set(str(c) for c in candidates)
        return any(b in base_set for b in self._token_bases(tokens))

    def _contains_surface(self, tokens: List[Dict[str, Any]], candidates: List[str]) -> bool:
        surf_set = set(str(c) for c in candidates)
        return any(s in surf_set for s in self._token_surfaces(tokens))

    def _contains_sequence(self, tokens: List[Dict[str, Any]], sequence: List[str], use_base: bool = True) -> bool:
        items = self._token_bases(tokens) if use_base else self._token_surfaces(tokens)
        if not sequence or not items:
            return False
        seq = [str(s) for s in sequence]
        for i in range(0, len(items) - len(seq) + 1):
            if items[i:i + len(seq)] == seq:
                return True
        return False

    def _has_body_marker(self, text: str, tokens: List[Dict[str, Any]]) -> bool:
        stripped = str(text).strip()
        if stripped.endswith(":") or stripped.endswith("："):
            return True
        # "以下の処理を行う/繰り返す" の構造をトークンで確認
        if self._contains_base(tokens, ["以下", "処理"]) and self._contains_base(tokens, ["行う", "実行", "繰り返す"]):
            return True
        return False

    def _is_condition_clause(self, tokens: List[Dict[str, Any]]) -> bool:
        return (
            self._contains_base(tokens, ["もし"]) or
            self._contains_base(tokens, ["場合"]) or
            self._contains_base(tokens, ["ならば"]) or
            self._contains_sequence(tokens, ["なら", "ば"])
        )

    def _is_else_clause(self, tokens: List[Dict[str, Any]]) -> bool:
        if self._contains_base(tokens, ["以外"]):
            return True
        if self._contains_sequence(tokens, ["そう", "で", "なけれ", "ば"], use_base=False):
            return True
        return False

    def _is_end_clause(self, tokens: List[Dict[str, Any]]) -> bool:
        return self._contains_base(tokens, ["終える", "終わる", "終了", "完了"])

    def _is_loop_clause(self, tokens: List[Dict[str, Any]]) -> bool:
        # Avoid treating LINQ select/transform expressions as explicit loops.
        if self._contains_surface(tokens, ["Select", "select", "SQL", "sql"]) or self._contains_base(tokens, ["変換", "選択", "抽出", "SQL", "sql"]):
            return False
        if self._contains_base(tokens, ["各", "それぞれ", "毎", "毎回"]):
            return True
        if self._contains_base(tokens, ["対する"]) and self._contains_base(tokens, ["各", "それぞれ"]):
            return True
        return False

    def _is_retry_wrapper(self, tokens: List[Dict[str, Any]]) -> bool:
        return (
            self._contains_surface(tokens, ["リトライ"])
            or self._contains_base(tokens, ["再試行"])
            or self._contains_sequence(tokens, ["再", "試行"], use_base=False)
            or self._contains_sequence(tokens, ["再", "試行"])
        )

    def _is_wrapper_action(self, tokens: List[Dict[str, Any]], semantic_roles: Dict[str, Any]) -> bool:
        if has_wrapper_metadata_hint(semantic_roles):
            return True
        return self._is_retry_wrapper(tokens)

    def _starts_with_digit(self, value: Optional[str]) -> bool:
        if value is None:
            return False
        s = str(value).strip()
        return bool(s) and s[0].isdigit()

    def _extract_first_number(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        s = str(text)
        i = 0
        while i < len(s):
            if s[i].isdigit():
                j = i
                while j < len(s) and s[j].isdigit():
                    j += 1
                if j < len(s) and s[j] == ".":
                    k = j + 1
                    if k < len(s) and s[k].isdigit():
                        while k < len(s) and s[k].isdigit():
                            k += 1
                        return s[i:k]
                return s[i:j]
            i += 1
        return None

    # Domain: Promotion Rules
    # FILTER and CALCULATE promotions both sit above the lexical baseline and
    # below final intent coercion.
    def _has_calculation_intent_signal(self, text: str, tokens: List[Dict[str, Any]]) -> bool:
        return has_calculation_intent_signal(text, tokens)

    def _has_filter_lexical_signal(self, text: str, tokens: List[Dict[str, Any]]) -> bool:
        return has_filter_lexical_signal(text, tokens)

    def _has_filter_predicate_logic(self, logic_goals: List[Dict[str, Any]]) -> bool:
        return has_filter_predicate_logic(logic_goals)

    def _has_upstream_collection_context(self, history: List[Dict[str, Any]], output_type_hint: Optional[str] = None) -> bool:
        return has_upstream_collection_context(history, output_type_hint, self._is_collection_type)

    def _infer_filter_property(self, tokens: List[Dict[str, Any]], logic_goals: List[Dict[str, Any]]) -> Optional[str]:
        return infer_filter_property(tokens, logic_goals)

    def _should_promote_to_filter(
        self,
        current_intent: str,
        step_text: str,
        tokens: List[Dict[str, Any]],
        logic_goals: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
        output_type_hint: Optional[str] = None,
    ) -> bool:
        return should_promote_to_filter(
            current_intent,
            step_text,
            tokens,
            logic_goals,
            history,
            output_type_hint,
            self._is_collection_type,
        )

    def _should_promote_to_calculate(
        self,
        current_intent: str,
        node_type: str,
        step_text: str,
        tokens: List[Dict[str, Any]],
        logic_goals: List[Dict[str, Any]],
        semantic_roles: Dict[str, Any],
    ) -> bool:
        return should_promote_to_calculate(
            current_intent,
            node_type,
            step_text,
            tokens,
            logic_goals,
            semantic_roles,
        )

    def _extract_entity_property_names(self, entity_def: Dict[str, Any]) -> List[str]:
        return extract_entity_property_names(entity_def)

    def _find_property_owner_entities(self, property_name: Optional[str]) -> List[str]:
        return find_property_owner_entities(self.entity_schema, property_name)

    # Domain: Target Resolution
    # Schema-backed owner resolution and history fallback remain local here
    # because CALCULATE target selection is still an upstream IR concern.
    def _infer_calculate_target_entity(
        self,
        current_entity: Optional[str],
        semantic_roles: Dict[str, Any],
        history: List[Dict[str, Any]],
        weak_entities: List[str],
    ) -> Tuple[str, str]:
        return infer_calculate_target_entity(self.entity_schema, current_entity, semantic_roles, history, weak_entities)

    def _resolve_property_provenance(
        self,
        property_name: Optional[str],
        current_entity: Optional[str],
    ) -> Tuple[Optional[str], Optional[str]]:
        return resolve_property_provenance(self.entity_schema, property_name, current_entity)

    def _is_collection_type(self, type_hint: Optional[str]) -> bool:
        if not type_hint:
            return False
        t = self.type_system.normalize_type(str(type_hint))
        return any(k in t for k in ["IEnumerable", "List", "ICollection", "IList", "Collection", "[]"])

    # Domain: Spec Role
    # This helper defines the specification-facing role independently from
    # downstream runtime role coercions.
    def _infer_spec_role(
        self,
        intent: str,
        step_text: str,
        tokens: List[Dict[str, Any]],
        logic_goals: List[Dict[str, Any]],
        node_type: Optional[str] = None,
    ) -> str:
        return infer_spec_role(
            intent,
            step_text,
            tokens,
            logic_goals,
            self._infer_intent_role_cardinality,
            node_type=node_type,
        )

    # Domain: CHECK Resolution
    # Condition-node metadata is kept together so subject/kind/provenance
    # evolve as one research unit.
    def _normalize_check_operator(self, operator_name: Optional[str]) -> Optional[str]:
        return normalize_check_operator(operator_name)

    def _infer_null_check_subject_metadata(self, tokens: List[Dict[str, Any]], target_entity: Optional[str]) -> Tuple[str, str]:
        return infer_null_check_subject_metadata(tokens, target_entity)

    def _infer_check_target_entity(
        self,
        target_entity: Optional[str],
        check_meta: Dict[str, Any],
        history: List[Dict[str, Any]],
        weak_entities: List[str],
    ) -> str:
        return infer_check_target_entity(target_entity, check_meta, history, weak_entities)

    def _infer_check_metadata(
        self,
        step_text: str,
        tokens: List[Dict[str, Any]],
        logic_goals: List[Dict[str, Any]],
        source_kind: Optional[str],
        source_ref: Optional[str],
        target_entity: Optional[str],
        node_type: Optional[str],
    ) -> Dict[str, Any]:
        return infer_check_metadata(
            step_text,
            tokens,
            logic_goals,
            source_kind,
            source_ref,
            target_entity,
            node_type,
        )

    # Domain: Step Analysis Orchestration
    # This is the upstream integration point where generic intent inference,
    # role-specific promotions, and semantic metadata assembly meet.
    def _analyze_step_integrated(self, step_text: str, history: list, intent_hint: str = None, source_kind: str = None, output_type_hint: str = None) -> Dict[str, Any]:
        tokens = []
        if self.morph_analyzer:
            res = self.morph_analyzer.analyze({"original_text": step_text})
            tokens = res.get("analysis", {}).get("tokens", [])
        
        v_intent, sim = self.intent_detector.detect(step_text, tokens=tokens)
        if intent_hint and intent_hint != INTENT_GENERAL: v_intent = intent_hint
        
        # 27.155: PRE-SPLIT INTENT ELEVATION.
        if v_intent in [INTENT_FETCH, INTENT_PERSIST, INTENT_GENERAL] and source_kind == "db":
            v_intent = INTENT_DATABASE_QUERY if v_intent != INTENT_PERSIST else INTENT_PERSIST

        rules = self.ukb.get("resolution_rules", {}) if (self.ukb and hasattr(self.ukb, 'get')) else {}
        intent_meta = rules.get("intent_metadata", {})
        meta = intent_meta.get(v_intent, {})
        role = meta.get("role", ROLE_ACTION)
        
        if v_intent == INTENT_HTTP_REQUEST:
            role = meta.get("role", ROLE_READ)
        elif v_intent in [INTENT_FILE_IO, INTENT_PERSIST, INTENT_FETCH]:
            if v_intent == INTENT_PERSIST:
                role = ROLE_WRITE
            elif v_intent == INTENT_FETCH:
                role = ROLE_READ
        
        cardinality = meta.get("cardinality", "SINGLE")
        logic_goals = self.logic_auditor.extract_assertion_goals([step_text])
        semantic_roles = {}
        calc_hint = None
        for goal in logic_goals:
            if goal.get("type") == "calculation":
                calc_hint = goal.get("target_hint") or goal.get("variable_hint")
                if calc_hint:
                    break
        if calc_hint:
            semantic_roles["target_hint"] = calc_hint
        # Keep a no-history entity reading in semantic metadata so later
        # resolution stages can distinguish explicit detection from fallback.
        semantic_roles.setdefault(
            "target_entity",
            self._identify_target_entity(step_text, history, allow_history_fallback=False),
        )
        intent = v_intent
        output_type = None
        inferred_intent, inferred_role, inferred_cardinality = self._infer_intent_role_cardinality(step_text, tokens)
        if intent == INTENT_GENERAL and inferred_intent:
            intent = inferred_intent
            role = inferred_role or role
        if inferred_cardinality:
            cardinality = inferred_cardinality

        # Promotion Domain:
        # CALCULATE and FILTER are both semantic promotions that may override
        # coarse lexical intent when stronger evidence is available.
        if any(lg.get("type") == "calculation" for lg in logic_goals):
            intent = INTENT_CALC; role = ROLE_CALC
            valid_goals = []
            for lg in logic_goals:
                if lg.get("type") == "calculation":
                    if not self._starts_with_digit(str(lg.get("value", ""))):
                        num_val = self._extract_first_number(lg.get("original_step", step_text))
                        if num_val:
                            lg["value"] = num_val
                    valid_goals.append(lg)
            logic_goals = valid_goals
        elif intent == INTENT_GENERAL and logic_goals:
            intent = INTENT_LINQ; role = ROLE_FILTER
        elif self._should_promote_to_filter(
            intent,
            step_text,
            tokens,
            logic_goals,
            history,
            output_type_hint=output_type_hint,
        ):
            intent = INTENT_LINQ; role = ROLE_FILTER
            filter_property = self._infer_filter_property(tokens, logic_goals)
            if filter_property:
                property_target_entity = self._identify_target_entity(step_text, history)
                canonical_property, property_resolution = self._resolve_property_provenance(
                    filter_property,
                    property_target_entity,
                )
                semantic_roles["property"] = canonical_property or filter_property
                if property_resolution == "schema_property":
                    semantic_roles["predicate_resolution"] = "schema_property"
                elif property_resolution == "history_scope":
                    semantic_roles["predicate_resolution"] = "history_predicate"
                else:
                    semantic_roles["predicate_resolution"] = "logic_goal"
            else:
                semantic_roles["predicate_resolution"] = "logic_goal"
            semantic_roles["collection_resolution"] = "explicit_input_link"
        # Explicit SQL literal inference
        if "sql" in str(step_text).lower():
            sql_literal = extract_first_quoted_literal(step_text)
            if sql_literal:
                semantic_roles["sql"] = sql_literal
                if intent not in [INTENT_PERSIST, INTENT_HTTP_REQUEST, INTENT_FILE_IO]:
                    intent = INTENT_DATABASE_QUERY
                    role = ROLE_FETCH
        if intent == INTENT_LINQ and role == ROLE_TRANSFORM and not logic_goals:
            semantic_roles.setdefault("ops", [])
            if "select" not in semantic_roles["ops"]:
                semantic_roles["ops"].append("select")
        # Encourage roles-driven binding for TRANSFORM/PERSIST when explicit content is absent
        if intent in [INTENT_TRANSFORM, INTENT_PERSIST, INTENT_FILE_IO, "WRITE"] and "content" not in semantic_roles:
            semantic_roles["content"] = "{context}"
        if intent in [INTENT_LINQ, INTENT_DATABASE_QUERY, INTENT_JSON_DESERIALIZE, INTENT_FETCH]:
            if self._is_collection_type(output_type_hint):
                cardinality = "COLLECTION"
        if cardinality == "SINGLE" and history:
            last_context = history[-1]
            if intent not in [INTENT_PERSIST, INTENT_FILE_IO]:
                if last_context.get("cardinality") == "COLLECTION" or self._is_collection_type(str(last_context.get("output_type") or "")):
                    if self._identify_target_entity(step_text, history) != "Item":
                        cardinality = "COLLECTION"
        if intent == INTENT_DISPLAY:
            output_type = "string"
        spec_role = self._infer_spec_role(intent, step_text, tokens, logic_goals)
        return {
            "node_type": NODE_ACTION,
            "intent": intent,
            "role": role,
            "cardinality": cardinality,
            "target_entity": self._identify_target_entity(step_text, history),
            "is_chaining": len(history) > 0,
            "semantic_map": {"logic": logic_goals, "semantic_roles": semantic_roles, "spec_role": spec_role},
            "output_type": output_type,
            "tokens": tokens
        }

    # Domain: Lexical Intent Baseline
    # This is intentionally coarse. Later promotion helpers may override it
    # when semantic evidence is stronger than the first lexical reading.
    def _infer_intent_role_cardinality(self, text: str, tokens: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        bases = self._token_bases(tokens)
        surfaces = self._token_surfaces(tokens)
        has_suru = "する" in bases

        fetch_nouns = {"取得", "検索", "読み込み", "読込", "読取", "抽出", "取得", "一覧"}
        persist_nouns = {"保存", "書き込み", "書き出し", "登録", "更新", "挿入", "追加"}
        display_nouns = {"表示", "出力", "印刷", "表示", "見せる"}
        exists_nouns = {"存在", "有無", "有り", "有る"}
        transform_nouns = {"変換", "変形", "変化", "選択", "抽出"}
        return_nouns = {"返却", "返戻", "返す"}

        fetch_verbs = {"取得", "読み込む", "読む", "検索する", "取得する", "取得", "取得する"}
        persist_verbs = {"保存する", "書き込む", "書き出す", "登録する", "更新する", "挿入する", "追加する"}
        display_verbs = {"表示する", "出力する", "印刷する"}
        exists_verbs = {"存在する", "ある", "有る"}
        transform_verbs = {"変換する", "変える", "抽出する", "選択する"}
        return_verbs = {"返す", "返却する", "戻す"}

        def has_noun(noun_set: set) -> bool:
            return any(b in noun_set for b in bases)

        def has_verb(verb_set: set) -> bool:
            return any(b in verb_set for b in bases)

        intent = None
        role = None

        if (has_suru and has_noun(display_nouns)) or has_verb(display_verbs):
            intent = INTENT_DISPLAY
            role = ROLE_DISPLAY
        elif (has_suru and has_noun(persist_nouns)) or has_verb(persist_verbs):
            intent = INTENT_PERSIST
            role = ROLE_PERSIST
        elif (has_suru and has_noun(return_nouns)) or has_verb(return_verbs):
            intent = INTENT_RETURN
            role = ROLE_RETURN
        elif (has_suru and has_noun(fetch_nouns)) or has_verb(fetch_verbs):
            intent = INTENT_FETCH
            role = ROLE_FETCH
        elif (has_suru and has_noun(exists_nouns)) or has_verb(exists_verbs):
            intent = INTENT_EXISTS
            role = ROLE_CHECK
        elif (has_suru and has_noun(transform_nouns)) or has_verb(transform_verbs):
            intent = INTENT_LINQ
            role = ROLE_TRANSFORM
        elif "select" in str(text).lower():
            intent = INTENT_LINQ
            role = ROLE_TRANSFORM

        cardinality = None
        if self._looks_collection(text, tokens):
            cardinality = "COLLECTION"
        if self._looks_single_by_id(text, tokens):
            cardinality = "SINGLE"

        return intent, role, cardinality

    def _looks_collection(self, text: str, tokens: List[Dict[str, Any]]) -> bool:
        bases = set(self._token_bases(tokens))
        surfaces = set(self._token_surfaces(tokens))
        if bases.intersection({"全", "各", "一覧", "全て", "すべて", "複数", "リスト", "list"}):
            return True
        if surfaces.intersection({"全員", "全て", "すべて", "リスト", "list"}):
            return True
        return False

    def _looks_single_by_id(self, text: str, tokens: List[Dict[str, Any]]) -> bool:
        if self._extract_first_number(text) is None:
            return False
        for s in self._token_surfaces(tokens):
            if str(s).lower() == "id":
                return True
        if self._contains_base(tokens, ["ID", "番号", "識別子"]):
            return True
        return False

    def _is_literal_return(self, text: str, tokens: List[Dict[str, Any]]) -> bool:
        goals = self.logic_auditor.extract_assertion_goals([text])
        if goals:
            return True
        if extract_first_quoted_literal(text) is not None:
            return True
        if self._extract_first_number(text) is not None:
            return True
        for s in self._token_surfaces(tokens):
            if str(s).lower() in ["true", "false", "null"]:
                return True
        return False

    # Domain: Target Resolution
    # The no-history / history-fallback split is controlled here so role-
    # specific resolution logic can choose the appropriate inference layer.
    def _identify_target_entity(self, text: str, history: list, allow_history_fallback: bool = True) -> str:
        return infer_target_entity(
            text,
            history,
            self.entity_schema,
            self.morph_analyzer,
            allow_history_fallback=allow_history_fallback,
        )
