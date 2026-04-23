# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional

from src.config.config_manager import ConfigManager
from src.morph_analyzer.morph_analyzer import MorphAnalyzer
from src.syntactic_analyzer.syntactic_analyzer import SyntacticAnalyzer
from src.semantic_analyzer.semantic_analyzer import SemanticAnalyzer
from src.code_synthesis.method_store import MethodStore
from src.code_synthesis.unified_knowledge_base import UnifiedKnowledgeBase
from src.autonomous_learning.structural_memory import StructuralMemory


class DesignOpsResolver:
    def __init__(self, config: ConfigManager | None = None, vector_engine=None) -> None:
        self.config = config or ConfigManager()
        self.vector_engine = vector_engine
        self._last_stats: Dict[str, int] = {
            "morph": 0,
            "syntactic": 0,
            "semantic": 0,
            "ukb_search": 0,
            "ukb_hits": 0,
        }
        self.morph = MorphAnalyzer(config_manager=self.config)
        self.syntactic = SyntacticAnalyzer(config_manager=self.config)
        self.semantic = SemanticAnalyzer(
            task_manager=None,
            config_manager=self.config,
            morph_analyzer=self.morph,
        )
        self.method_store = MethodStore(self.config, morph_analyzer=self.morph, vector_engine=self.vector_engine)
        self.structural_memory = StructuralMemory(
            self.config.storage_dir,
            config_manager=self.config,
            vector_engine=self.vector_engine,
            morph_analyzer=self.morph,
            index_on_init=False,
        )
        self.ukb = UnifiedKnowledgeBase(self.config, self.method_store, self.structural_memory)
        self._semantic_candidates: List[Dict[str, Any]] = []
        self._semantic_candidate_vectors: List[Any] = []
        self._semantic_candidates_ready = False

        self._template_step_map = {
            "dapper_query": "repo.fetch_all",
            "dapper_query_single": "repo.fetch_by_id",
            "dapper_execute": "repo.update",
            "pattern.dapper_query_list": "repo.fetch_all",
            "pattern.dapper_query_single": "repo.fetch_by_id",
            "http_get_string": "intent.HTTP_REQUEST",
            "http_post": "intent.HTTP_REQUEST",
            "json_deserialize": "intent.JSON_DESERIALIZE",
            "json_serialize": "intent.TRANSFORM",
            "file_readalltext": "intent.FILE_IO",
            "file_writealltext": "intent.FILE_IO",
            "file_exists": "intent.FILE_IO",
            "sys.system.io.file.readalltext": "intent.FILE_IO",
            "sys.system.io.file.readalltextasync": "intent.FILE_IO",
            "sys.system.io.file.writealltext": "intent.FILE_IO",
            "sys.system.io.file.writealltextasync": "intent.FILE_IO",
            "sys.system.io.file.exists": "intent.FILE_IO",
            "console_writeline": "intent.DISPLAY",
            "linq_where": "intent.LINQ",
            "linq_tolist": "intent.LINQ",
        }

    def _ensure_semantic_candidates(self) -> None:
        if self._semantic_candidates_ready:
            return
        self._semantic_candidates = []
        self._semantic_candidate_vectors = []
        candidates = []

        # action_patterns.json
        patterns = self._load_action_patterns()
        for p in patterns:
            cand = {
                "id": p.get("id"),
                "name": p.get("name", ""),
                "description": p.get("description", ""),
                "tags": p.get("tags", []) or [],
                "intent": p.get("intent"),
                "capabilities": p.get("capabilities", []) or [],
                "origin": "pattern",
            }
            candidates.append(cand)

        # canonical_knowledge.json templates
        templates = self._load_canonical_templates()
        for t in templates:
            cand = {
                "id": t.get("id"),
                "name": t.get("name", ""),
                "description": t.get("class", ""),
                "tags": t.get("tags", []) or [],
                "intent": t.get("intent"),
                "capabilities": t.get("capabilities", []) or [],
                "origin": "template",
            }
            candidates.append(cand)

        for cand in candidates:
            vec = self._vectorize_candidate(cand)
            if vec is None:
                continue
            self._semantic_candidates.append(cand)
            self._semantic_candidate_vectors.append(vec)

        self._semantic_candidates_ready = True

    def _load_action_patterns(self) -> List[Dict[str, Any]]:
        path = os.path.join(getattr(self.config, "workspace_root", os.getcwd()), "resources", "action_patterns.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("patterns", []) if isinstance(data, dict) else []
        except Exception:
            return []

    def _load_canonical_templates(self) -> List[Dict[str, Any]]:
        path = os.path.join(getattr(self.config, "workspace_root", os.getcwd()), "resources", "canonical_knowledge.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("templates", []) if isinstance(data, dict) else []
        except Exception:
            return []

    def _vectorize_candidate(self, cand: Dict[str, Any]) -> Any:
        if not self.vector_engine:
            return None
        parts = [
            str(cand.get("name", "")),
            str(cand.get("description", "")),
            " ".join([str(t) for t in cand.get("tags", []) if t]),
            str(cand.get("id", "")),
        ]
        text = " ".join([p for p in parts if p]).strip()
        if not text:
            return None
        raw_tokens = self.morph.tokenize(text) if self.morph else list(text)
        tokens = [t.get("surface") if isinstance(t, dict) else str(t) for t in raw_tokens]
        return self.vector_engine.get_sentence_vector(tokens)

    def _semantic_candidate_search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if not self.vector_engine:
            return []
        self._ensure_semantic_candidates()
        if not self._semantic_candidates:
            return []

        raw_tokens = self.morph.tokenize(query) if self.morph else list(query)
        tokens = [t.get("surface") if isinstance(t, dict) else str(t) for t in raw_tokens]
        query_vec = self.vector_engine.get_sentence_vector(tokens)
        if query_vec is None:
            return []

        scored = []
        for cand, vec in zip(self._semantic_candidates, self._semantic_candidate_vectors):
            if vec is None:
                continue
            score = self.vector_engine.vector_similarity(query_vec, vec)
            scored.append((cand, float(score)))
        scored.sort(key=lambda x: (-x[1], str(x[0].get("id", ""))))
        results = []
        for cand, score in scored[:top_k]:
            c = dict(cand)
            c["score"] = score
            results.append(c)
        return results

    def infer_steps(self, core_logic: List[str], method_name: str) -> List[str]:
        if not core_logic:
            return []
        candidate_steps: List[str] = []
        for line in core_logic:
            step = self._infer_step_from_line(line, method_name)
            if step:
                candidate_steps.append(step)
        return candidate_steps

    def infer_step_with_score(self, line: str, method_name: str) -> tuple[str | None, float]:
        context = self._analyze_line(line)
        query = self._build_query_from_context(context, line)
        if not query:
            return None, 0.0
        candidates = self._sort_candidates(self.ukb.search(query, limit=5))
        step, cand = self._select_with_hints(candidates, method_name, context, require_preferred=True)
        if step and cand:
            return step, self._score_candidate(cand)

        semantic_candidates = self._sort_candidates(self._semantic_candidate_search(query, top_k=5))
        step, cand = self._select_with_hints(semantic_candidates, method_name, context, require_preferred=True)
        if step and cand:
            return step, self._score_candidate(cand)

        if self._needs_expanded_search(context):
            expanded = self._sort_candidates(self.ukb.search(query, limit=20))
            step, cand = self._select_with_hints(expanded, method_name, context, require_preferred=True)
            if step and cand:
                return step, self._score_candidate(cand)

            expanded_semantic = self._sort_candidates(self._semantic_candidate_search(query, top_k=20))
            step, cand = self._select_with_hints(expanded_semantic, method_name, context, require_preferred=True)
            if step and cand:
                return step, self._score_candidate(cand)

            fallback_step, fallback_cand = self._select_with_hints(expanded_semantic, method_name, context, require_preferred=False)
            if fallback_step and fallback_cand:
                return fallback_step, self._score_candidate(fallback_cand)
        return None, 0.0

    def infer_step_with_score_excluding_intents(
        self,
        line: str,
        method_name: str,
        exclude_intents: set[str],
    ) -> tuple[str | None, float]:
        context = self._analyze_line(line)
        query = self._build_query_from_context(context, line)
        if not query:
            return None, 0.0

        candidates = self._sort_candidates(self.ukb.search(query, limit=5))
        step, cand = self._select_with_hints(
            candidates,
            method_name,
            context,
            exclude_intents=exclude_intents,
            require_preferred=True,
        )
        if step and cand:
            step_intent = self._step_to_intent(step)
            if step_intent not in exclude_intents:
                return step, self._score_candidate(cand)

        semantic_candidates = self._sort_candidates(self._semantic_candidate_search(query, top_k=5))
        step, cand = self._select_with_hints(
            semantic_candidates,
            method_name,
            context,
            exclude_intents=exclude_intents,
            require_preferred=True,
        )
        if step and cand:
            step_intent = self._step_to_intent(step)
            if step_intent not in exclude_intents:
                return step, self._score_candidate(cand)

        if self._needs_expanded_search(context):
            expanded = self._sort_candidates(self.ukb.search(query, limit=20))
            step, cand = self._select_with_hints(
                expanded,
                method_name,
                context,
                exclude_intents=exclude_intents,
                require_preferred=True,
            )
            if step and cand:
                step_intent = self._step_to_intent(step)
                if step_intent not in exclude_intents:
                    return step, self._score_candidate(cand)

            expanded_semantic = self._sort_candidates(self._semantic_candidate_search(query, top_k=20))
            step, cand = self._select_with_hints(
                expanded_semantic,
                method_name,
                context,
                exclude_intents=exclude_intents,
                require_preferred=True,
            )
            if step and cand:
                step_intent = self._step_to_intent(step)
                if step_intent not in exclude_intents:
                    return step, self._score_candidate(cand)

            fallback_step, fallback_cand = self._select_with_hints(
                expanded_semantic,
                method_name,
                context,
                exclude_intents=exclude_intents,
                require_preferred=False,
            )
            if fallback_step and fallback_cand:
                step_intent = self._step_to_intent(fallback_step)
                if step_intent not in exclude_intents:
                    return fallback_step, self._score_candidate(fallback_cand)

        return None, 0.0

    def infer_service_steps(self, core_logic: List[str], method_name: str, fallback_op: str | None = None) -> List[str]:
        if not core_logic:
            return []
        candidate_steps: List[str] = []
        for line in core_logic:
            step = self._infer_service_step_from_line(line, method_name, fallback_op)
            if step:
                candidate_steps.append(step)
        return candidate_steps

    def _infer_step_from_line(self, line: str, method_name: str) -> Optional[str]:
        context = self._analyze_line(line)
        query = self._build_query_from_context(context, line)
        if not query:
            return None

        self._last_stats["ukb_search"] += 1
        candidates = self._sort_candidates(self.ukb.search(query, limit=5))
        if not candidates:
            return None
        self._last_stats["ukb_hits"] += 1

        for cand in candidates:
            step = self._map_candidate_to_step(cand, method_name)
            if step:
                return step
        return None

    def _build_query_from_context(self, context: Dict[str, Any], line: str) -> str:
        topics = context.get("analysis", {}).get("topics", [])
        topic_text = " ".join([t.get("text", "") for t in topics if t.get("text")])
        syntax_terms = self._extract_syntax_terms(context)
        syntax_text = " ".join(syntax_terms)
        return " ".join([t for t in [topic_text, syntax_text, line] if t]).strip()

    def _analyze_line(self, line: str) -> Dict[str, Any]:
        context: Dict[str, Any] = {"original_text": line}
        context = self.morph.analyze(context)
        self._last_stats["morph"] += 1
        context = self.syntactic.analyze(context)
        self._last_stats["syntactic"] += 1
        context = self.semantic.analyze(context)
        self._last_stats["semantic"] += 1
        return context

    def _select_with_hints(
        self,
        candidates: List[Dict[str, Any]],
        method_name: str,
        context: Dict[str, Any],
        exclude_intents: Optional[set[str]] = None,
        require_preferred: bool = False,
    ) -> tuple[str | None, Dict[str, Any] | None]:
        if not candidates:
            return None, None
        hints = self._derive_intent_hints(context)
        allowed = hints.get("allowed_intents")
        preferred = hints.get("preferred_intents", [])
        disallowed = hints.get("disallowed_intents", set())
        if exclude_intents:
            disallowed = set(disallowed) | set(exclude_intents)

        def _iter_filtered() -> List[Dict[str, Any]]:
            filtered: List[Dict[str, Any]] = []
            for cand in candidates:
                intent = str(cand.get("intent", "")).upper()
                if allowed and intent not in allowed:
                    continue
                if intent in disallowed:
                    continue
                filtered.append(cand)
            return filtered

        filtered = _iter_filtered()
        if preferred:
            for pref in preferred:
                for cand in filtered:
                    intent = str(cand.get("intent", "")).upper()
                    if intent != pref:
                        caps = {str(c).upper() for c in (cand.get("capabilities", []) or [])}
                        if pref not in caps:
                            continue
                        return f"intent.{pref}", cand
                    step = self._map_candidate_to_step(cand, method_name)
                    if step:
                        return step, cand
            if require_preferred:
                return None, None

        for cand in filtered:
            step = self._map_candidate_to_step(cand, method_name)
            if step:
                return step, cand
        return None, None

    def _derive_intent_hints(self, context: Dict[str, Any]) -> Dict[str, Any]:
        analysis = context.get("analysis", {}) if isinstance(context, dict) else {}
        entities = analysis.get("entities", {}) if isinstance(analysis, dict) else {}
        topics = analysis.get("topics", []) if isinstance(analysis, dict) else []
        topic_texts = {str(t.get("text")) for t in topics if t.get("text")}

        hints: Dict[str, Any] = {
            "allowed_intents": None,
            "preferred_intents": [],
            "disallowed_intents": set(),
        }
        def _prefer(intent: str, front: bool = False) -> None:
            intent = intent.upper()
            if intent in hints["preferred_intents"]:
                hints["preferred_intents"].remove(intent)
            if front:
                hints["preferred_intents"].insert(0, intent)
            else:
                hints["preferred_intents"].append(intent)

        has_url = "url" in entities
        has_filename = any(k in entities for k in ["filename", "source_filename", "destination_filename"])

        if has_url:
            hints["allowed_intents"] = {"HTTP_REQUEST"}
            return hints

        if has_filename:
            hints["disallowed_intents"].add("HTTP_REQUEST")
            _prefer("FILE_IO")
            _prefer("FETCH")

        if "JSON" in topic_texts or "json" in topic_texts:
            _prefer("JSON_DESERIALIZE", front=True)

        if "表示" in topic_texts or "コンソール" in topic_texts:
            _prefer("DISPLAY")

        return hints

    def _needs_expanded_search(self, context: Dict[str, Any]) -> bool:
        hints = self._derive_intent_hints(context)
        return bool(hints.get("preferred_intents"))

    def get_intent_hints(self, line: str) -> Dict[str, Any]:
        context = self._analyze_line(line)
        return self._derive_intent_hints(context)

    def get_entities(self, line: str) -> Dict[str, Any]:
        context = self._analyze_line(line)
        return context.get("analysis", {}).get("entities", {}) or {}

    def _step_to_intent(self, step: str) -> str:
        if not step:
            return ""
        if step.startswith("intent."):
            return step.split(".", 1)[1].upper()
        if step.startswith("repo."):
            if step.endswith("fetch_all") or step.endswith("fetch_by_id"):
                return "DATABASE_QUERY"
            return "PERSIST"
        return ""

    def _map_candidate_to_step(self, candidate: Dict[str, Any], method_name: str) -> Optional[str]:
        cand_id = str(candidate.get("id", ""))
        if cand_id in self._template_step_map:
            step = self._template_step_map[cand_id]
            return step

        intent = str(candidate.get("intent", "")).upper()
        if intent == "DATABASE_QUERY":
            return "repo.fetch_all"
        if intent == "PERSIST":
            return self._map_execute_by_method("repo.update", method_name)
        if intent in ["HTTP_REQUEST", "FETCH", "JSON_DESERIALIZE", "FILE_IO", "DISPLAY", "LINQ", "TRANSFORM", "CALC"]:
            return f"intent.{intent}"
        return None

    def _infer_service_step_from_line(self, line: str, method_name: str, fallback_op: str | None) -> Optional[str]:
        context = self._analyze_line(line)

        topics = context.get("analysis", {}).get("topics", [])
        topic_text = " ".join([t.get("text", "") for t in topics if t.get("text")])
        syntax_terms = self._extract_syntax_terms(context)
        syntax_text = " ".join(syntax_terms)
        query = " ".join([t for t in [topic_text, syntax_text, line] if t]).strip()

        self._last_stats["ukb_search"] += 1
        candidates = self._sort_candidates(self.ukb.search(query, limit=5))
        for cand in candidates:
            step = self._map_candidate_to_service_step(cand, None)
            if step:
                self._last_stats["ukb_hits"] += 1
                return step
        return None

    def get_stats(self) -> Dict[str, int]:
        return dict(self._last_stats)

    def _map_candidate_to_service_step(self, candidate: Dict[str, Any], fallback_op: str | None) -> Optional[str]:
        intent = str(candidate.get("intent", "")).upper()
        return_type = str(candidate.get("return_type", ""))
        capabilities = candidate.get("capabilities", []) or []
        cap_text = " ".join([str(c) for c in capabilities])
        if "DISPLAY" in cap_text or intent == "DISPLAY":
            return "service.list"
        if intent in ["FETCH", "DATABASE_QUERY", "FILE_IO", "HTTP_REQUEST", "JSON_DESERIALIZE", "LINQ", "TRANSFORM"]:
            if "IEnumerable" in return_type or return_type.endswith("[]"):
                return "service.list"
            return "service.get"
        if intent in ["PERSIST", "WRITE"]:
            if fallback_op:
                return f"service.{fallback_op}"
        return None

    def _map_execute_by_method(self, fallback: str, method_name: str) -> str:
        # Keyword-based inference is disallowed; keep explicit fallback only.
        return fallback

    def _extract_syntax_terms(self, context: Dict[str, Any]) -> List[str]:
        terms: List[str] = []
        chunks = context.get("analysis", {}).get("syntax_tree", [])
        for node in chunks:
            surface = node.get("surface", "")
            dep_type = node.get("dep_type", "")
            if not surface:
                continue
            if dep_type in ["SUBJ", "OBJ", "MOD", "COMP"]:
                terms.append(surface)
        return terms

    def _sort_candidates(self, candidates: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
        if not candidates:
            return []
        def _score(cand: Dict[str, Any]) -> float:
            return self._score_candidate(cand)
        return sorted(
            candidates,
            key=lambda c: (-_score(c), str(c.get("id", "")))
        )

    def _score_candidate(self, cand: Dict[str, Any]) -> float:
        raw = cand.get("score")
        if raw is None:
            return 0.0
        try:
            return float(raw)
        except Exception:
            return 0.0
