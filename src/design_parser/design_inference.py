# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.config.config_manager import ConfigManager
from src.utils.design_doc_parser import DesignDocParser
from src.code_generation.design_ops_resolver import DesignOpsResolver
from src.morph_analyzer.morph_analyzer import MorphAnalyzer
from src.design_parser.data_source_utils import parse_data_source_tag
from src.utils.entity_inference import infer_target_entity


@dataclass
class InferenceIssue:
    step_index: int
    reason: str
    detail: str


class DesignInferenceEngine:
    """Infer missing design metadata deterministically and persist into .design.md."""

    _INFERENCE_RULES_VERSION = "v1"

    def __init__(self, config_manager: Optional[ConfigManager] = None, vector_engine=None, morph_analyzer=None):
        self.config_manager = config_manager or ConfigManager()
        self.vector_engine = vector_engine
        self.morph_analyzer = morph_analyzer or MorphAnalyzer(config_manager=self.config_manager)
        self.parser = DesignDocParser()
        self.resolver = DesignOpsResolver(config=self.config_manager, vector_engine=self.vector_engine)
        self.entity_schema = self._load_entity_schema()

        cfg = self.config_manager.get_section("design_inference") if self.config_manager else {}
        self.thresholds = {
            "intent_threshold": float(cfg.get("intent_threshold", 0.80)),
            "entity_threshold": float(cfg.get("entity_threshold", 0.80)),
            "data_source_threshold": float(cfg.get("data_source_threshold", 0.85)),
            "refs_threshold": float(cfg.get("refs_threshold", 0.75)),
        }

    def infer_then_freeze(self, design_path: str) -> Dict[str, Any]:
        if not os.path.exists(design_path):
            return {"status": "error", "message": f"Design document not found: {design_path}"}

        with open(design_path, "r", encoding="utf-8") as f:
            original = f.read()

        parsed = self.parser.parse_content(original)
        spec = parsed.get("specification", {}) if isinstance(parsed, dict) else {}
        core_logic = spec.get("core_logic", []) if isinstance(spec, dict) else []
        output_spec = spec.get("output", {}) if isinstance(spec, dict) else {}
        output_format = str(output_spec.get("format") or "").strip().lower()
        module_name = str(parsed.get("module_name") or "").strip()

        if not core_logic:
            return {"status": "no_change", "message": "Core Logic is empty."}

        data_sources = self._collect_data_sources(core_logic)
        self._current_data_sources = [ds for ds in (parse_data_source_tag(s, {"db","http","file","memory","env","stdin"}) for s in data_sources) if ds]
        updated_lines: List[str] = []
        issues: List[InferenceIssue] = []
        inferred_any = False

        step_idx = 0
        last_persist_path: Optional[str] = None
        non_data_lines = [line for line in core_logic if not self._is_data_source_line(line)]
        last_step_idx = len(non_data_lines)
        last_output_type: Optional[str] = None
        for raw in core_logic:
            line = str(raw)
            if self._is_data_source_line(line):
                updated_lines.append(line)
                continue

            step_idx += 1
            is_last_step = step_idx == last_step_idx
            if self._has_explicit_step_meta(line):
                explicit_roles = self._extract_semantic_roles(line)
                if not explicit_roles:
                    explicit_intent = self._extract_intent_from_line(line)
                    if explicit_intent == "LINQ":
                        pass
                updated_lines.append(line)
                last_output_type = self._extract_output_type_from_line(line) or last_output_type
                intent = self._extract_intent_from_line(line)
                roles = self._extract_semantic_roles(line)
                if intent == "PERSIST":
                    path_val = roles.get("path")
                    if isinstance(path_val, str) and path_val:
                        last_persist_path = path_val
                continue

            inferred, issue, new_line, ds_updates = self._infer_line(
                line,
                step_idx,
                module_name,
                last_output_type,
                is_last_step=is_last_step,
                output_format=output_format,
                last_persist_path=last_persist_path,
            )
            if issue:
                issues.append(issue)
                updated_lines.append(line)
                continue
            if inferred:
                inferred_any = True
                updated_lines.append(new_line)
                for ds in ds_updates:
                    if ds not in data_sources:
                        data_sources.append(ds)
            else:
                updated_lines.append(line)
            last_output_type = self._extract_output_type_from_line(updated_lines[-1]) or last_output_type
            if inferred:
                intent = self._extract_intent_from_line(updated_lines[-1])
                roles = self._extract_semantic_roles(updated_lines[-1])
                if intent == "PERSIST":
                    path_val = roles.get("path")
                    if isinstance(path_val, str) and path_val:
                        last_persist_path = path_val

        if issues:
            return {
                "status": "blocked",
                "message": "Inference blocked due to low confidence or missing signals.",
                "issues": [issue.__dict__ for issue in issues],
            }

        inferred_path = self._get_inferred_path(design_path)

        if not inferred_any and not data_sources:
            self._write_inferred_file(inferred_path, original)
            return {"status": "no_change", "message": "No inference required.", "output_path": inferred_path}

        updated_content = self._write_back_inference(
            original,
            updated_lines,
            data_sources=data_sources,
        )
        if updated_content == original:
            self._write_inferred_file(inferred_path, original)
            return {"status": "no_change", "message": "No changes applied.", "output_path": inferred_path}

        updated_content = self._upsert_inference_metadata(updated_content)

        self._write_inferred_file(inferred_path, updated_content)

        return {"status": "updated", "message": "Inference applied and design frozen.", "output_path": inferred_path}

    def _get_inferred_path(self, design_path: str) -> str:
        base = os.path.basename(design_path)
        if base.endswith(".design.md"):
            inferred = base[:-10] + ".inferred.design.md"
        else:
            inferred = base + ".inferred"
        return os.path.join(os.path.dirname(design_path), inferred)

    def _write_inferred_file(self, path: str, content: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _infer_line(
        self,
        line: str,
        step_idx: int,
        module_name: str,
        last_output_type: Optional[str],
        is_last_step: bool = False,
        output_format: str = "",
        last_persist_path: Optional[str] = None,
    ) -> Tuple[bool, Optional[InferenceIssue], str, List[str]]:
        step_token, score = self.resolver.infer_step_with_score(line, module_name)
        if not step_token:
            if is_last_step and output_format and output_format not in ["void", "none"] and last_persist_path:
                meta = {
                    "kind": "ACTION",
                    "intent": "TRANSFORM",
                    "target_entity": "Item",
                    "output_type": self._normalize_output_type(output_format) or "void",
                    "side_effect": "NONE",
                }
                semantic_roles_tag = f'[semantic_roles:{{"return_value":{json.dumps(str(last_persist_path))}}}]'
                tag = self._build_step_meta_tag(meta)
                refs = self._build_refs_tag(step_idx)
                new_line = self._prefix_inferred_tags(line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            return False, InferenceIssue(step_idx, "NO_CANDIDATE", "No deterministic candidate found."), line, []
        if score < self.thresholds["intent_threshold"]:
            preferred_ok = False
            if step_token and step_token.startswith("intent."):
                intent = step_token.split(".", 1)[1].upper()
                hints = self.resolver.get_intent_hints(line)
                preferred = [str(p).upper() for p in (hints.get("preferred_intents") or [])]
                if intent in preferred:
                    preferred_ok = True
            if not preferred_ok:
                return False, InferenceIssue(step_idx, "LOW_CONFIDENCE", f"score={score:.3f}"), line, []

        meta = self._map_step_token_to_meta(step_token)
        if not meta:
            return False, InferenceIssue(step_idx, "UNMAPPED_TOKEN", step_token), line, []

        semantic_roles_tag = ""
        sql_literal = ""
        entities = self.resolver.get_entities(line)
        has_url = "url" in entities
        has_filename = any(k in entities for k in ["filename", "source_filename", "destination_filename"])
        if has_filename:
            filename_val = None
            if "filename" in entities:
                filename_val = entities.get("filename", {}).get("value")
            if not filename_val and "source_filename" in entities:
                filename_val = entities.get("source_filename", {}).get("value")
            if not filename_val and "destination_filename" in entities:
                filename_val = entities.get("destination_filename", {}).get("value")
            if filename_val and not self._is_likely_filename(str(filename_val)):
                has_filename = False
        env_sources, stdin_sources, http_sources, file_sources = self._collect_source_kinds()

        if meta.get("intent") == "JSON_DESERIALIZE":
            inferred_entity = infer_target_entity(line, [], self.entity_schema, self.morph_analyzer)
            if inferred_entity and inferred_entity != "Item":
                meta = dict(meta)
                meta["target_entity"] = inferred_entity
                if meta.get("output_type") in ["List<Item>", "Item"]:
                    meta["output_type"] = meta["output_type"].replace("Item", inferred_entity)
            if has_filename:
                filename_val = None
                if "filename" in entities:
                    filename_val = entities.get("filename", {}).get("value")
                if not filename_val and "source_filename" in entities:
                    filename_val = entities.get("source_filename", {}).get("value")
                if not filename_val and "destination_filename" in entities:
                    filename_val = entities.get("destination_filename", {}).get("value")
                if filename_val and self._is_likely_filename(str(filename_val)):
                    semantic_roles_tag = f'[semantic_roles:{{"path":{json.dumps(str(filename_val))}}}]'
        if meta.get("intent") == "DISPLAY" and not semantic_roles_tag:
            display_prop = self._infer_display_property(line)
            if display_prop:
                semantic_roles_tag = f'[semantic_roles:{{"property":{json.dumps(display_prop)}}}]'
        source_override_applied = False
        if meta.get("intent") in ["HTTP_REQUEST", "FILE_IO", "FETCH"]:
            source_override = self._select_source_override(
                line,
                step_idx,
                env_sources,
                stdin_sources,
                http_sources,
                file_sources,
            )
            if source_override:
                source_ref, source_kind, forced_intent = source_override
                meta = dict(meta)
                meta["source_ref"] = source_ref
                meta["source_kind"] = source_kind
                if forced_intent:
                    meta["intent"] = forced_intent
                meta["side_effect"] = "IO" if meta["intent"] in ["FETCH", "FILE_IO"] else meta.get("side_effect", "NONE")
                if meta.get("intent") == "FETCH":
                    meta["output_type"] = meta.get("output_type") or "string"
                source_override_applied = True
        if meta.get("intent") in ["DATABASE_QUERY", "PERSIST"]:
            sql_literal = self._extract_sql_literal(line)
            if not sql_literal:
                alt_token, alt_score = self.resolver.infer_step_with_score_excluding_intents(
                    line,
                    module_name,
                    exclude_intents={"DATABASE_QUERY", "PERSIST"},
                )
                if alt_token and alt_score >= self.thresholds["intent_threshold"]:
                    step_token = alt_token
                    meta = self._map_step_token_to_meta(step_token)
                    if not meta:
                        return False, InferenceIssue(step_idx, "UNMAPPED_TOKEN", step_token), line, []
                else:
                    return False, InferenceIssue(step_idx, "MISSING_SQL", "SQL literal required for DATABASE_QUERY/PERSIST."), line, []
            sql_intent = self._classify_sql_intent(sql_literal)
            if sql_intent:
                meta = dict(meta)
                meta["intent"] = sql_intent
                meta["side_effect"] = "DB"
                meta["output_type"] = "List<Item>" if sql_intent == "DATABASE_QUERY" else "void"
            semantic_roles_tag = f'[semantic_roles:{{"sql":"{sql_literal}"}}]'

        if meta.get("intent") in ["HTTP_REQUEST", "FILE_IO", "FETCH"] and not has_url and not has_filename:
            if not http_sources and meta.get("intent") == "HTTP_REQUEST":
                alt_token, alt_score = self.resolver.infer_step_with_score_excluding_intents(
                    line,
                    module_name,
                    exclude_intents={"HTTP_REQUEST", "DATABASE_QUERY", "PERSIST"},
                )
                if alt_token and alt_score >= self.thresholds["intent_threshold"]:
                    step_token = alt_token
                    meta = self._map_step_token_to_meta(step_token)
            if meta.get("intent") == "FILE_IO":
                alt_token, alt_score = self.resolver.infer_step_with_score_excluding_intents(
                    line,
                    module_name,
                    exclude_intents={"FILE_IO", "HTTP_REQUEST", "DATABASE_QUERY", "PERSIST"},
                )
                if alt_token and alt_score >= self.thresholds["intent_threshold"]:
                    step_token = alt_token
                    meta = self._map_step_token_to_meta(step_token)
                elif not source_override_applied:
                    meta = dict(meta)
                    meta["intent"] = "TRANSFORM"
                    meta["side_effect"] = "NONE"
                    meta["output_type"] = last_output_type or "string"
            if meta.get("intent") == "FETCH":
                alt_token, alt_score = self.resolver.infer_step_with_score_excluding_intents(
                    line,
                    module_name,
                    exclude_intents={"FETCH", "FILE_IO", "HTTP_REQUEST", "DATABASE_QUERY", "PERSIST"},
                )
                if alt_token and alt_score >= self.thresholds["intent_threshold"]:
                    step_token = alt_token
                    meta = self._map_step_token_to_meta(step_token)
                elif not source_override_applied:
                    meta = dict(meta)
                    meta["intent"] = "TRANSFORM"
                    meta["side_effect"] = "NONE"
                    meta["output_type"] = last_output_type or "string"

        if not semantic_roles_tag and is_last_step and output_format and output_format not in ["void", "none"] and last_persist_path:
            if meta.get("intent") in ["TRANSFORM", "GENERAL", "DISPLAY"]:
                semantic_roles_tag = f'[semantic_roles:{{"return_value":{json.dumps(str(last_persist_path))}}}]'
        tag = self._build_step_meta_tag(meta)
        refs = self._build_refs_tag(step_idx)
        new_line = self._prefix_inferred_tags(line, tag, refs, semantic_roles_tag)
        data_sources = []
        if meta.get("source_ref") == "db_main":
            data_sources.append("[data_source|db_main|db]")
        return True, None, new_line, data_sources

    def _collect_source_kinds(self) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
        sources = []
        if hasattr(self, "_current_data_sources"):
            sources = self._current_data_sources or []
        env_sources = [s for s in sources if s.get("kind") == "env"]
        stdin_sources = [s for s in sources if s.get("kind") == "stdin"]
        http_sources = [s for s in sources if s.get("kind") == "http"]
        file_sources = [s for s in sources if s.get("kind") == "file"]
        return env_sources, stdin_sources, http_sources, file_sources

    def _select_source_override(
        self,
        line: str,
        step_idx: int,
        env_sources: List[Dict[str, str]],
        stdin_sources: List[Dict[str, str]],
        http_sources: List[Dict[str, str]],
        file_sources: List[Dict[str, str]],
    ) -> Optional[Tuple[str, str, Optional[str]]]:
        text = str(line)
        for src in env_sources:
            src_id = src.get("id")
            if src_id and src_id in text:
                return src_id, "env", "FETCH"
        if len(env_sources) == 1 and not http_sources and not file_sources and not stdin_sources:
            src = env_sources[0]
            return src.get("id", "env"), "env", "FETCH"
        if step_idx == 1 and len(stdin_sources) == 1 and not http_sources and not file_sources:
            src = stdin_sources[0]
            return src.get("id", "STDIN"), "stdin", "FETCH"
        return None

    def _load_entity_schema(self) -> Dict[str, Any]:
        path = os.path.join(self.config_manager.workspace_root, "resources", "entity_schema.json")
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


    def _map_step_token_to_meta(self, token: str) -> Optional[Dict[str, str]]:
        if not token or "." not in token:
            return None
        domain, op = token.split(".", 1)

        meta = {
            "kind": "ACTION",
            "intent": "GENERAL",
            "target_entity": "Item",
            "output_type": "void",
            "side_effect": "NONE",
        }
        if domain == "repo":
            meta["side_effect"] = "DB"
            meta["source_ref"] = "db_main"
            meta["source_kind"] = "db"
            if op in ["fetch_all"]:
                meta["intent"] = "DATABASE_QUERY"
                meta["output_type"] = "List<Item>"
            elif op in ["fetch_by_id"]:
                meta["intent"] = "DATABASE_QUERY"
                meta["output_type"] = "Item"
            else:
                meta["intent"] = "PERSIST"
        elif domain == "service":
            if op == "list":
                meta["intent"] = "DISPLAY"
                meta["output_type"] = "void"
            elif op == "get":
                meta["intent"] = "FETCH"
                meta["output_type"] = "Item"
            elif op in ["create", "update", "delete"]:
                meta["intent"] = "TRANSFORM"
        elif domain == "calc":
            meta["intent"] = "CALC"
            meta["output_type"] = "decimal"
        elif domain == "intent":
            intent = op.upper()
            meta["intent"] = intent
            if intent == "HTTP_REQUEST":
                meta["output_type"] = "string"
                meta["side_effect"] = "NETWORK"
            elif intent == "FETCH":
                meta["output_type"] = "string"
                meta["side_effect"] = "IO"
            elif intent == "JSON_DESERIALIZE":
                meta["output_type"] = "List<Item>"
            elif intent == "FILE_IO":
                meta["output_type"] = "string"
                meta["side_effect"] = "IO"
            elif intent == "DISPLAY":
                meta["output_type"] = "void"
            elif intent == "LINQ":
                meta["output_type"] = "List<Item>"
            elif intent == "TRANSFORM":
                meta["output_type"] = "void"
            elif intent == "CALC":
                meta["output_type"] = "decimal"
        else:
            return None
        return meta

    def _build_step_meta_tag(self, meta: Dict[str, str]) -> str:
        parts = [
            meta.get("kind", "ACTION"),
            meta.get("intent", "GENERAL"),
            meta.get("target_entity", "Item"),
            meta.get("output_type", "void"),
            meta.get("side_effect", "NONE"),
        ]
        if meta.get("source_ref"):
            parts.append(meta["source_ref"])
        if meta.get("source_kind"):
            parts.append(meta["source_kind"])
        return "[" + "|".join(parts) + "]"

    def _build_refs_tag(self, step_idx: int) -> str:
        if step_idx <= 1:
            return ""
        return f"[refs:step_{step_idx-1}]"

    def _prefix_inferred_tags(self, line: str, meta_tag: str, refs_tag: str, semantic_roles_tag: str) -> str:
        prefix, remainder = self._split_line_prefix(line)
        tags = meta_tag
        if refs_tag:
            tags = f"{tags} {refs_tag}"
        if semantic_roles_tag:
            tags = f"{tags} {semantic_roles_tag}"
        if remainder.startswith("["):
            return f"{prefix}{tags} {remainder}"
        return f"{prefix}{tags} {remainder}".rstrip()

    def _split_line_prefix(self, line: str) -> Tuple[str, str]:
        s = line.rstrip("\n")
        stripped = s.lstrip()
        prefix_len = len(s) - len(stripped)
        prefix = s[:prefix_len]
        if stripped.startswith("- "):
            return prefix + "- ", stripped[2:].strip()
        i = 0
        while i < len(stripped) and stripped[i].isdigit():
            i += 1
        if i > 0 and i < len(stripped) and stripped[i] == ".":
            if i + 1 < len(stripped) and stripped[i + 1] == " ":
                return prefix + stripped[: i + 2], stripped[i + 2 :].strip()
        return prefix, stripped.strip()

    def _collect_data_sources(self, core_logic: List[str]) -> List[str]:
        data_sources = []
        for line in core_logic:
            if self._is_data_source_line(line):
                data_sources.append(self._strip_leading_numbering(str(line).strip()))
        return data_sources

    def _extract_output_type_from_line(self, line: str) -> Optional[str]:
        s = self._strip_leading_numbering(str(line).strip())
        if not s.startswith("["):
            return None
        end = s.find("]")
        if end == -1:
            return None
        meta = s[1:end]
        lower = meta.lower()
        if lower.startswith("data_source|") or lower.startswith("refs:") or lower.startswith("ops:") or lower.startswith("semantic_roles:"):
            return None
        parts = [p.strip() for p in meta.split("|")]
        if not parts:
            return None
        kind = parts[0].upper()
        if kind in ["END", "ELSE"]:
            return None
        if kind in ["LOOP", "CONDITION"] and len(parts) >= 3:
            return parts[2]
        if len(parts) >= 4:
            return parts[3]
        return None

    def _extract_intent_from_line(self, line: str) -> Optional[str]:
        s = self._strip_leading_numbering(str(line).strip())
        if not s.startswith("["):
            return None
        end = s.find("]")
        if end == -1:
            return None
        meta = s[1:end]
        lower = meta.lower()
        if lower.startswith("data_source|") or lower.startswith("refs:") or lower.startswith("ops:") or lower.startswith("semantic_roles:"):
            return None
        parts = [p.strip() for p in meta.split("|")]
        if len(parts) >= 2:
            return parts[1].upper()
        return None

    def _extract_semantic_roles(self, line: str) -> Dict[str, Any]:
        text = str(line)
        marker = "[semantic_roles:"
        idx = text.find(marker)
        if idx == -1:
            return {}
        start = idx + len(marker)
        end = text.find("]", start)
        if end == -1:
            return {}
        raw = text[start:end].strip()
        if not raw.startswith("{") or not raw.endswith("}"):
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _append_semantic_roles(self, line: str, semantic_roles_tag: str) -> str:
        if not semantic_roles_tag:
            return line
        prefix, remainder = self._split_line_prefix(line)
        if remainder.startswith("["):
            return f"{prefix}{remainder} {semantic_roles_tag}".rstrip()
        return f"{prefix}{semantic_roles_tag} {remainder}".rstrip()

    def _infer_display_property(self, line: str) -> Optional[str]:
        entity = infer_target_entity(line, [], self.entity_schema, self.morph_analyzer)
        if not entity or not isinstance(self.entity_schema, dict):
            return None
        props = {}
        for ent in self.entity_schema.get("entities", []):
            if ent.get("name") == entity and isinstance(ent.get("properties"), dict):
                props = ent.get("properties") or {}
                break
        if not props:
            return None
        tokens = []
        if self.morph_analyzer:
            try:
                res = self.morph_analyzer.analyze({"original_text": line})
                tokens = res.get("analysis", {}).get("tokens", []) if isinstance(res, dict) else []
            except Exception:
                tokens = []
        token_vals = []
        for t in tokens:
            if isinstance(t, dict):
                if t.get("surface"):
                    token_vals.append(str(t.get("surface")).lower())
                if t.get("base"):
                    token_vals.append(str(t.get("base")).lower())
        if not token_vals:
            return None
        string_props = [p for p, pt in props.items() if "string" in str(pt).lower()]
        ordered_props = string_props + [p for p in props.keys() if p not in string_props]
        for prop in ordered_props:
            if str(prop).lower() in token_vals:
                return prop
        return None

    def _normalize_output_type(self, output_format: str) -> str:
        if not output_format:
            return ""
        fmt = str(output_format).strip()
        if fmt.endswith("?"):
            fmt = fmt[:-1].strip()
        if fmt in ["string", "int", "long", "decimal", "double", "float", "bool", "void"]:
            return fmt
        return fmt

    def _is_likely_filename(self, value: str) -> bool:
        if not value:
            return False
        s = str(value).strip()
        if not s:
            return False
        if any(ch in s for ch in [" ", ",", "="]):
            return False
        return "." in s or "/" in s or "\\" in s


    def _is_data_source_line(self, line: str) -> bool:
        s = self._strip_leading_numbering(str(line).strip())
        if s.startswith("- "):
            s = s[2:].strip()
        return s.startswith("[data_source|")

    def _has_explicit_step_meta(self, line: str) -> bool:
        s = self._strip_leading_numbering(str(line).strip())
        if not s.startswith("["):
            return False
        end = s.find("]")
        if end == -1:
            return False
        meta = s[1:end]
        if meta.lower().startswith("data_source|"):
            return False
        if meta.lower().startswith("ops:") or meta.lower().startswith("refs:") or meta.lower().startswith("semantic_roles:"):
            return False
        return "|" in meta

    def _strip_leading_numbering(self, text: str) -> str:
        s = text.strip()
        i = 0
        while i < len(s) and s[i].isdigit():
            i += 1
        if i > 0 and i < len(s) and s[i] == ".":
            if i + 1 < len(s) and s[i + 1].isspace():
                return s[i + 2:].strip()
        if s.startswith("- "):
            return s[2:].strip()
        return s

    def _extract_sql_literal(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        start = text.find("`")
        end = text.rfind("`")
        if start == -1 or end == -1 or end <= start:
            return ""
        return text[start + 1 : end].strip()

    def _classify_sql_intent(self, sql: str) -> str:
        if not sql:
            return ""
        cleaned = sql.strip().lower()
        for prefix in ["select", "with"]:
            if cleaned.startswith(prefix):
                return "DATABASE_QUERY"
        for prefix in ["insert", "update", "delete"]:
            if cleaned.startswith(prefix):
                return "PERSIST"
        return ""

    def _write_back_inference(self, content: str, updated_core_logic: List[str], data_sources: List[str]) -> str:
        filtered_core = []
        for line in updated_core_logic:
            if self._is_data_source_line(line):
                continue
            filtered_core.append(line)
        deduped_sources: List[str] = []
        for ds in data_sources or []:
            if ds and ds not in deduped_sources:
                deduped_sources.append(ds)
        lines = content.splitlines()
        out_lines: List[str] = []
        in_core = False
        logic_lines_consumed = 0
        inserted_data_sources = False

        for line in lines:
            lower = line.strip().lower()
            if lower.startswith("##") or lower.startswith("###"):
                if in_core:
                    in_core = False
                if "core logic" in lower:
                    in_core = True
                    out_lines.append(line)
                    continue

            if in_core:
                if not inserted_data_sources and deduped_sources:
                    for ds in deduped_sources:
                        out_lines.append(f"- {ds}")
                    inserted_data_sources = True
                if logic_lines_consumed < len(filtered_core):
                    out_lines.append(filtered_core[logic_lines_consumed])
                    logic_lines_consumed += 1
                continue

            out_lines.append(line)

        return "\n".join(out_lines) + ("\n" if content.endswith("\n") else "")

    def _upsert_inference_metadata(self, content: str) -> str:
        metadata_block = self._build_inference_metadata_block(content)
        if "### Inference Metadata" in content:
            return self._replace_inference_block(content, metadata_block)
        return self._insert_inference_block(content, metadata_block)

    def _replace_inference_block(self, content: str, block: str) -> str:
        lines = content.splitlines()
        out = []
        in_block = False
        for line in lines:
            if line.strip() == "### Inference Metadata":
                in_block = True
                out.append(block.strip())
                continue
            if in_block:
                if line.strip().startswith("## ") or line.strip().startswith("### "):
                    in_block = False
                    out.append(line)
                else:
                    continue
            else:
                out.append(line)
        return "\n".join(out) + ("\n" if content.endswith("\n") else "")

    def _insert_inference_block(self, content: str, block: str) -> str:
        lines = content.splitlines()
        out = []
        inserted = False
        in_purpose = False
        for i, line in enumerate(lines):
            lower = line.strip().lower()
            if lower.startswith("## purpose"):
                in_purpose = True
                out.append(line)
                continue
            if in_purpose and (line.strip().startswith("## ") or line.strip().startswith("### ")):
                out.append(block.strip())
                inserted = True
                in_purpose = False
            out.append(line)
        if not inserted:
            out.append(block.strip())
        return "\n".join(out) + ("\n" if content.endswith("\n") else "")

    def _build_inference_metadata_block(self, content: str) -> str:
        assets = self._collect_assets()
        fingerprint = self._compute_fingerprint(content, assets)
        lines = ["### Inference Metadata", "- inference_mode: infer_then_freeze", f"- inference_fingerprint: {fingerprint}", "- assets:"]
        for asset in assets:
            lines.append(f"  - {asset['path']}")
        return "\n".join(lines)

    def _collect_assets(self) -> List[Dict[str, Any]]:
        cfg = self.config_manager
        paths = [
            cfg.vector_model_path,
            cfg.dictionary_db_path,
            os.path.join(cfg.workspace_root, "config", "scoring_rules.json"),
            cfg.method_store_path,
            os.path.join(cfg.workspace_root, "config", "config.json"),
            os.path.join(cfg.workspace_root, "config", "safety_policy.json"),
            os.path.join(cfg.workspace_root, "config", "project_rules.json"),
            os.path.join(cfg.workspace_root, "config", "retry_rules.json"),
        ]
        assets = []
        for p in sorted(set(paths)):
            assets.append(self._hash_asset(p))
        return assets

    def _hash_asset(self, path: str) -> Dict[str, Any]:
        info = {"path": path, "size_bytes": 0, "sha256": ""}
        if not path or not os.path.exists(path):
            return info
        try:
            size = os.path.getsize(path)
            sha = self._sha256_file(path)
            info["size_bytes"] = size
            info["sha256"] = sha
        except Exception:
            pass
        return info

    def _compute_fingerprint(self, content: str, assets: List[Dict[str, Any]]) -> str:
        normalized = self._normalize_design_text(content)
        payload = {
            "design_text_normalized": normalized,
            "asset_versions": assets,
            "inference_rules_version": self._INFERENCE_RULES_VERSION,
        }
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _normalize_design_text(self, content: str) -> str:
        text = content.replace("\r\n", "\n").replace("\r", "\n")
        lines = [ln.rstrip() for ln in text.split("\n")]
        normalized = "\n".join(lines)
        return self._remove_inference_metadata_block(normalized)

    def _remove_inference_metadata_block(self, content: str) -> str:
        if "### Inference Metadata" not in content:
            return content
        lines = content.splitlines()
        out = []
        in_block = False
        for line in lines:
            if line.strip() == "### Inference Metadata":
                in_block = True
                continue
            if in_block:
                if line.strip().startswith("## ") or line.strip().startswith("### "):
                    in_block = False
                    out.append(line)
                else:
                    continue
            else:
                out.append(line)
        return "\n".join(out)

    def _sha256_file(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()


def infer_then_freeze_if_needed(
    design_path: str,
    config_manager: Optional[ConfigManager] = None,
    vector_engine=None,
    morph_analyzer=None,
) -> Dict[str, Any]:
    engine = DesignInferenceEngine(
        config_manager=config_manager,
        vector_engine=vector_engine,
        morph_analyzer=morph_analyzer,
    )
    return engine.infer_then_freeze(design_path)
