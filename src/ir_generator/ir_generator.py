# -*- coding: utf-8 -*-
import json
import os
import copy
from typing import List, Dict, Any, Tuple, Optional

from src.utils.logic_auditor import LogicAuditor
from src.code_synthesis.type_system import TypeSystem
from src.utils.text_parser import extract_first_quoted_literal
from src.utils.entity_inference import infer_target_entity

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
            return "GENERAL", 0.0
        meaningful_words = [t["base"] for t in tokens if t["pos"].startswith(("名詞", "動詞"))] if tokens else [text]
        query_vec = self.vector_engine.get_sentence_vector(meaningful_words)
        if query_vec is None: return "GENERAL", 0.0
        best_intent, max_sim = "GENERAL", 0.0
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
            raw_text = raw_step.get("text", "") if isinstance(raw_step, dict) else str(raw_step)
            if "[data_source|" in raw_text or any(inp.get("description") == raw_text for inp in inputs): continue
            if self.strict_semantics and strict_requested and isinstance(raw_step, dict):
                has_ops = bool((raw_step.get("semantic_roles") or {}).get("ops"))
                has_explicit = bool(raw_step.get("explicit_intent") or raw_step.get("explicit_semantic_roles"))
                if not has_ops and not has_explicit:
                    raise ValueError(f"Missing explicit intent/ops for step {raw_step.get('id')}: {raw_text}")
            if isinstance(raw_step, dict) and raw_step.get("semantic_roles", {}).get("ops"):
                clauses = [{"text": raw_text, "type": "ACTION", "has_body": False}]
            else:
                clauses = self._extract_hierarchical_clauses(raw_text)
            if not clauses and isinstance(raw_step, dict) and raw_step.get("kind") in ["END", "ELSE"]:
                clauses = [{"text": "", "type": raw_step.get("kind"), "has_body": True}]
            heuristics = self.ukb.get("entity_heuristics", {}) if (self.ukb and hasattr(self.ukb, 'get')) else {}
            if not isinstance(heuristics, dict):
                heuristics = {}
            
            step_intent_tag = raw_step.get("intent") if isinstance(raw_step, dict) else None
            if isinstance(step_intent_tag, str) and step_intent_tag in ["GENERAL", "ACTION", ""]:
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
                if step_entry.get("kind") in ["ACTION", "GENERAL"]:
                    if step_intent_tag:
                        node_type = "ACTION"
                    elif c_type in ["CONDITION", "ELSE", "END", "LOOP"]:
                        node_type = c_type
                if sub_idx > 0 and node_type in ["LOOP", "CONDITION"]:
                    node_type = "ACTION"
                
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
                
            # 27.162: STRICT INTENT LOCK.
            final_intent = step_intent_tag or analysis["intent"]
            is_explicit_intent = isinstance(step_intent_tag, str) and bool(step_intent_tag)
            if node_type in ["CONDITION", "ACTION"] and final_intent in ["GENERAL", "HTTP_REQUEST", "FILTER"]:
                if is_explicit_intent and step_intent_tag in ["HTTP_REQUEST", "DATABASE_QUERY", "PERSIST", "FETCH"]:
                    pass
                else:
                    if any(lg.get("type") in ["numeric", "string", "logic"] for lg in final_semantic_map.get("logic", [])):
                        final_intent = "LINQ"
            elif node_type == "CONDITION" and final_intent in ["GENERAL", "HTTP_REQUEST"]:
                final_intent = "LINQ"
            if final_intent in ["GENERAL", "ACTION"] and "url" in final_semantic_map.get("semantic_roles", {}):
                final_intent = "HTTP_REQUEST"
                source_kind = source_kind or "http"
            if final_intent in ["GENERAL", "ACTION"] and "sql" in final_semantic_map.get("semantic_roles", {}):
                final_intent = "PERSIST"
                source_kind = source_kind or "db"
            # Downgrade structured DB intent when no DB evidence exists
            if step_intent_tag == "DATABASE_QUERY":
                has_sql = "sql" in final_semantic_map.get("semantic_roles", {})
                if source_kind != "db" and not has_sql:
                    final_intent = "FETCH"
            if final_intent == "PERSIST":
                analysis["role"] = "PERSIST"
            elif final_intent in ["DATABASE_QUERY", "FETCH"]:
                analysis["role"] = "FETCH"
            elif final_intent == "DISPLAY":
                analysis["role"] = "DISPLAY"
            elif final_intent == "HTTP_REQUEST":
                if "payload" in final_semantic_map.get("semantic_roles", {}) or "content" in final_semantic_map.get("semantic_roles", {}):
                    analysis["role"] = "PERSIST"

            # Compute chaining after intent resolution to allow RETURN literals without upstream linkage
            is_chaining = (analysis.get("is_chaining") or sub_idx > 0)
            if final_intent == "RETURN" and not analysis.get("is_chaining"):
                is_chaining = False
            is_notification = final_intent == "DISPLAY" and bool(
                final_semantic_map.get("semantic_roles", {}).get("notification")
            )
            last_collection_id = None
            if context_history:
                for h in reversed(context_history):
                    if h.get("cardinality") == "COLLECTION" and h.get("node_id"):
                        last_collection_id = h.get("node_id")
                        break
            last_context_output = ""
            if context_history:
                last_context_output = str(context_history[-1].get("output_type") or "").lower()
            prefer_scalar_input = last_context_output in ["string", "int", "long", "decimal", "double", "float", "bool"]
            want_collection_input = (node_type == "LOOP" or final_intent in ["LINQ", "DISPLAY", "TRANSFORM", "CALC"])
            if final_intent == "PERSIST":
                want_collection_input = not prefer_scalar_input
            if is_chaining and last_node_id:
                if is_notification and final_intent == "DISPLAY":
                    input_link = None
                else:
                    input_link = last_collection_id if (want_collection_input and last_collection_id) else last_node_id
            else:
                input_link = None
            if isinstance(step_entry, dict) and step_entry.get("input_refs"):
                if final_intent == "PERSIST":
                    input_link = step_entry["input_refs"][0]
            if final_intent == "RETURN":
                tokens = analysis.get("tokens") or []
                if self._is_literal_return(c_text, tokens):
                    input_link = None

            # If explicit input_link exists, avoid forcing "{context}" content
            if input_link and final_semantic_map.get("semantic_roles", {}).get("content") == "{context}":
                del final_semantic_map["semantic_roles"]["content"]

            output_type_hint = step_entry.get("output_type") or analysis.get("output_type")
            
            # 27.425: If source_kind is still None, try to infer from semantic_roles
            if not source_kind:
                if "path" in final_semantic_map.get("semantic_roles", {}):
                    path_val = final_semantic_map["semantic_roles"]["path"]
                    if any(ext in str(path_val).lower() for ext in [".json", ".txt", ".csv", ".xml"]):
                        source_kind = "file"
                elif "url" in final_semantic_map.get("semantic_roles", {}):
                    source_kind = "http"
                    
            node_id = step_entry.get('id', f"step_{idx+1}")
            if len(clauses) > 1: node_id = f"{node_id}_{sub_idx+1}"
            
            # 27.160: FINAL CARDINALITY LOCK.
            final_cardinality = analysis["cardinality"]
            if node_type == "LOOP":
                final_cardinality = "COLLECTION"
            if final_cardinality == "SINGLE" and final_intent in ["LINQ", "DATABASE_QUERY", "JSON_DESERIALIZE"]:
                if self._is_collection_type(output_type_hint):
                    final_cardinality = "COLLECTION"
            
            # 27.426: Inherit source_kind if missing for I/O
            if not source_kind and final_intent in ["PERSIST", "FILE_IO", "WRITE", "FETCH"]:
                if context_history:
                    for h in reversed(context_history):
                        if h.get("source_kind"):
                            source_kind = h["source_kind"]; break
            if output_type_hint in ["string", "int", "long", "decimal", "double", "float", "bool"]:
                final_cardinality = "SINGLE"
            if final_cardinality == "COLLECTION" and node_type != "LOOP":
                if final_intent not in ["LINQ", "DATABASE_QUERY", "JSON_DESERIALIZE", "FETCH"]:
                    if not self._is_collection_type(output_type_hint):
                        final_cardinality = "SINGLE"
            node = {
                "id": node_id, "type": node_type, "original_text": c_text, "intent": final_intent, "role": analysis["role"],
                "cardinality": final_cardinality, "target_entity": target_entity,
                "output_type": step_entry.get("output_type") or analysis.get("output_type"),
                "source_kind": source_kind, "source_ref": source_ref, "semantic_map": final_semantic_map,
                "input_link": input_link, "children": [], "else_children": []
            }
            if step_entry.get("explicit_method_id"):
                node["explicit_method_id"] = step_entry.get("explicit_method_id")
            if step_entry.get("explicit_method_name"):
                node["explicit_method_name"] = step_entry.get("explicit_method_name")

            if final_intent == "PERSIST" and prefer_scalar_input and last_node_id:
                if node.get("input_link") != last_node_id:
                    node["input_link"] = last_node_id
            
            # 27.440: Phase 7 F-1 Auto-Chaining for JSON Deserialization
            if not simple_list_input:
                ot = node.get("output_type")
                if ot and any(k in ot for k in ["List", "[]", "IEnumerable", "Collection"]):
                    if final_intent in ["FETCH", "HTTP_REQUEST", "FILE_IO"] and source_kind in ["file", "http", "api"]:
                        # 1. 現在のノードの出力を string に変更
                        node["output_type"] = "string"
                        if block_stack: parent = block_stack[-1]; parent["node"][parent["target"]].append(node)
                        else: nodes.append(node)
                        
                        # 2. JSON_DESERIALIZE ノードを新規作成
                        json_node = copy.deepcopy(node)
                        json_node["id"] = f"{node_id}_json"
                        json_node["intent"] = "JSON_DESERIALIZE"
                        json_node["role"] = "TRANSFORM"
                        json_node["output_type"] = ot
                        json_node["source_kind"] = "memory"
                        json_node["semantic_map"]["semantic_roles"] = {} # Binder will resolve content
                        # Derive target entity from collection output type when possible
                        inner = self.type_system.extract_generic_inner(str(ot))
                        if inner:
                            json_node["target_entity"] = inner
                        elif str(ot).endswith("[]"):
                            json_node["target_entity"] = str(ot)[:-2].strip()
                        
                        if block_stack: parent = block_stack[-1]; parent["node"][parent["target"]].append(json_node)
                        else: nodes.append(json_node)
                        
                        context_history.append({
                            "text": c_text,
                            "target_entity": target_entity,
                            "cardinality": "COLLECTION",
                            "output_type": ot,
                            "source_kind": "memory",
                            "node_id": json_node["id"]
                        })
                        last_node_id = json_node["id"]
                        continue

            # 27.450: Phase 7 F-1 Auto-Chaining for JSON Serialization (Reverse of 27.440)
            # If intent is PERSIST and we have a COLLECTION coming in,
            # we need to serialize the collection to string first.
            is_coll_input = False
            if context_history:
                last_ctx = context_history[-1]
                if last_ctx.get("cardinality") == "COLLECTION": is_coll_input = True
            
            try:
                print(f"[DEBUG] IRGen: node_id={node_id}, intent={final_intent}, is_coll_input={is_coll_input}, source_kind={source_kind}")
            except OSError:
                # stdout may be closed in some test runners
                pass
            if not simple_list_input:
                if final_intent in ["PERSIST", "FILE_IO", "WRITE"] and source_kind in ["file", "http", "api"]:
                    is_poco_input = target_entity and target_entity != "Item"
                    input_is_string = False
                    prev_ref = input_link or last_node_id
                    if prev_ref:
                        prev_node = self._find_node_by_id(nodes, prev_ref)
                        if prev_node:
                            if str(prev_node.get("output_type") or "").lower() == "string":
                                input_is_string = True
                            elif prev_node.get("intent") == "DISPLAY":
                                input_is_string = True
                    if not input_is_string and context_history:
                        last_ctx = context_history[-1]
                        if str(last_ctx.get("output_type") or "").lower() == "string":
                            input_is_string = True
                    if is_coll_input or node.get("cardinality") == "COLLECTION" or is_poco_input:
                        if input_is_string:
                            # Skip serialization when upstream output is already string
                            pass
                        else:
                            # 1. データのシリアライズ・ノードを挿入
                            serialize_node = copy.deepcopy(node)
                            serialize_node["id"] = f"{node_id}_ser"
                            serialize_node["intent"] = "TRANSFORM"
                            serialize_node["role"] = "TRANSFORM"
                            serialize_node["output_type"] = "string"
                            serialize_node["source_kind"] = "memory"
                            serialize_node["semantic_map"]["semantic_roles"] = {} # Binder will resolve data from previous collection
                            
                            if block_stack:
                                parent = block_stack[-1]
                                parent["node"][parent["target"]].append(serialize_node)
                            else:
                                nodes.append(serialize_node)
                            
                            # 2. 現在のノード（PERSIST）の入力を serialize_node にリンク
                            node["input_link"] = serialize_node["id"]
                            # PERSIST ノード自体は COLLECTION ではなく SINGLE (stringを1回出す) として扱う
                            node["cardinality"] = "SINGLE"
                        
            if node_type == "ELSE":
                if block_stack:
                    for entry in reversed(block_stack):
                        if entry["node"]["type"] == "CONDITION": entry["target"] = "else_children"; break
                context_history.append({
                    "text": c_text,
                    "target_entity": main_entity,
                    "cardinality": "SINGLE",
                    "output_type": None,
                    "source_kind": source_kind,
                    "node_id": node_id
                })
                continue
            if node_type == "END":
                if block_stack: block_stack.pop()
                continue
            # Skip redundant consecutive DATABASE_QUERY with identical SQL/target
            if final_intent == "DATABASE_QUERY" and last_node_id:
                prev_node = self._find_node_by_id(nodes, last_node_id)
                prev_map = prev_node.get("semantic_map", {}) if isinstance(prev_node, dict) else {}
                prev_sql = prev_map.get("semantic_roles", {}).get("sql")
                curr_sql = final_semantic_map.get("semantic_roles", {}).get("sql")
                if prev_node and prev_node.get("intent") == "DATABASE_QUERY" and prev_node.get("target_entity") == target_entity and prev_sql and curr_sql and prev_sql == curr_sql:
                    last_node_id = prev_node.get("id")
                    context_history.append({
                        "text": c_text,
                        "target_entity": target_entity,
                        "cardinality": prev_node.get("cardinality"),
                        "output_type": prev_node.get("output_type"),
                        "source_kind": prev_node.get("source_kind")
                    })
                    continue
            if block_stack: parent = block_stack[-1]; parent["node"][parent["target"]].append(node)
            else: nodes.append(node)
            if node_type in ["CONDITION", "LOOP"] or c_info.get("has_body"): block_stack.append({"node": node, "target": "children"})
            context_history.append({
                "text": c_text,
                "target_entity": target_entity,
                "cardinality": node.get("cardinality"),
                "output_type": node.get("output_type"),
                "source_kind": node.get("source_kind"),
                "node_id": node["id"]
            })
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
        return self._contains_surface(tokens, ["リトライ"]) or self._contains_base(tokens, ["再試行"])

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

    def _is_collection_type(self, type_hint: Optional[str]) -> bool:
        if not type_hint:
            return False
        t = self.type_system.normalize_type(str(type_hint))
        return any(k in t for k in ["IEnumerable", "List", "ICollection", "IList", "Collection", "[]"])

    def _analyze_step_integrated(self, step_text: str, history: list, intent_hint: str = None, source_kind: str = None, output_type_hint: str = None) -> Dict[str, Any]:
        tokens = []
        if self.morph_analyzer:
            res = self.morph_analyzer.analyze({"original_text": step_text})
            tokens = res.get("analysis", {}).get("tokens", [])
        
        v_intent, sim = self.intent_detector.detect(step_text, tokens=tokens)
        if intent_hint and intent_hint != "GENERAL": v_intent = intent_hint
        
        # 27.155: PRE-SPLIT INTENT ELEVATION.
        if v_intent in ["FETCH", "PERSIST", "GENERAL"] and source_kind == "db":
            v_intent = "DATABASE_QUERY" if v_intent != "PERSIST" else "PERSIST"

        rules = self.ukb.get("resolution_rules", {}) if (self.ukb and hasattr(self.ukb, 'get')) else {}
        intent_meta = rules.get("intent_metadata", {})
        meta = intent_meta.get(v_intent, {})
        role = meta.get("role", "ACTION")
        
        if v_intent == "HTTP_REQUEST":
            role = meta.get("role", "READ")
        elif v_intent in ["FILE_IO", "PERSIST", "FETCH"]:
            if v_intent == "PERSIST":
                role = "WRITE"
            elif v_intent == "FETCH":
                role = "READ"
        
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
        # Ensure target entity is always available to downstream binders
        semantic_roles.setdefault("target_entity", self._identify_target_entity(step_text, history))
        intent = v_intent
        output_type = None
        inferred_intent, inferred_role, inferred_cardinality = self._infer_intent_role_cardinality(step_text, tokens)
        if intent == "GENERAL" and inferred_intent:
            intent = inferred_intent
            role = inferred_role or role
        if inferred_cardinality:
            cardinality = inferred_cardinality

        if any(lg.get("type") == "calculation" for lg in logic_goals):
            intent = "CALC"; role = "CALC"
            valid_goals = []
            for lg in logic_goals:
                if lg.get("type") == "calculation":
                    if not self._starts_with_digit(str(lg.get("value", ""))):
                        num_val = self._extract_first_number(lg.get("original_step", step_text))
                        if num_val:
                            lg["value"] = num_val
                    valid_goals.append(lg)
            logic_goals = valid_goals
        elif intent == "GENERAL" and logic_goals:
            intent = "LINQ"; role = "FILTER"
        # Explicit SQL literal inference
        if "sql" in str(step_text).lower():
            sql_literal = extract_first_quoted_literal(step_text)
            if sql_literal:
                semantic_roles["sql"] = sql_literal
                if intent not in ["PERSIST", "HTTP_REQUEST", "FILE_IO"]:
                    intent = "DATABASE_QUERY"
                    role = "FETCH"
        if intent == "LINQ" and role == "TRANSFORM" and not logic_goals:
            semantic_roles.setdefault("ops", [])
            if "select" not in semantic_roles["ops"]:
                semantic_roles["ops"].append("select")
        # Encourage roles-driven binding for TRANSFORM/PERSIST when explicit content is absent
        if intent in ["TRANSFORM", "PERSIST", "FILE_IO", "WRITE"] and "content" not in semantic_roles:
            semantic_roles["content"] = "{context}"
        if intent in ["LINQ", "DATABASE_QUERY", "JSON_DESERIALIZE", "FETCH"]:
            if self._is_collection_type(output_type_hint):
                cardinality = "COLLECTION"
        if cardinality == "SINGLE" and history:
            last_context = history[-1]
            if intent not in ["PERSIST", "FILE_IO"]:
                if last_context.get("cardinality") == "COLLECTION" or self._is_collection_type(str(last_context.get("output_type") or "")):
                    if self._identify_target_entity(step_text, history) != "Item":
                        cardinality = "COLLECTION"
        if intent == "DISPLAY":
            output_type = "string"
        return {
            "node_type": "ACTION",
            "intent": intent,
            "role": role,
            "cardinality": cardinality,
            "target_entity": self._identify_target_entity(step_text, history),
            "is_chaining": len(history) > 0,
            "semantic_map": {"logic": logic_goals, "semantic_roles": semantic_roles},
            "output_type": output_type,
            "tokens": tokens
        }

    def _infer_intent_role_cardinality(self, text: str, tokens: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        bases = self._token_bases(tokens)
        surfaces = self._token_surfaces(tokens)
        has_suru = "する" in bases

        fetch_nouns = {"取得", "検索", "読み込み", "読込", "読取", "抽出", "取得", "一覧"}
        persist_nouns = {"保存", "書き込み", "書き出し", "登録", "更新", "挿入", "追加"}
        display_nouns = {"表示", "出力", "印刷", "表示", "見せる"}
        exists_nouns = {"存在", "有無", "有り", "有る"}
        transform_nouns = {"変換", "変形", "変化", "選択", "抽出"}

        fetch_verbs = {"取得", "読み込む", "読む", "検索する", "取得する", "取得", "取得する"}
        persist_verbs = {"保存する", "書き込む", "書き出す", "登録する", "更新する", "挿入する", "追加する"}
        display_verbs = {"表示する", "出力する", "印刷する"}
        exists_verbs = {"存在する", "ある", "有る"}
        transform_verbs = {"変換する", "変える", "抽出する", "選択する"}

        def has_noun(noun_set: set) -> bool:
            return any(b in noun_set for b in bases)

        def has_verb(verb_set: set) -> bool:
            return any(b in verb_set for b in bases)

        intent = None
        role = None

        if (has_suru and has_noun(display_nouns)) or has_verb(display_verbs):
            intent = "DISPLAY"
            role = "DISPLAY"
        elif (has_suru and has_noun(persist_nouns)) or has_verb(persist_verbs):
            intent = "PERSIST"
            role = "PERSIST"
        elif (has_suru and has_noun(fetch_nouns)) or has_verb(fetch_verbs):
            intent = "FETCH"
            role = "FETCH"
        elif (has_suru and has_noun(exists_nouns)) or has_verb(exists_verbs):
            intent = "EXISTS"
            role = "CHECK"
        elif (has_suru and has_noun(transform_nouns)) or has_verb(transform_verbs):
            intent = "LINQ"
            role = "TRANSFORM"
        elif "select" in str(text).lower():
            intent = "LINQ"
            role = "TRANSFORM"

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
        if self._extract_first_number(text) is not None:
            return True
        for s in self._token_surfaces(tokens):
            if str(s).lower() in ["true", "false"]:
                return True
        return False

    def _identify_target_entity(self, text: str, history: list) -> str:
        return infer_target_entity(text, history, self.entity_schema, self.morph_analyzer)
