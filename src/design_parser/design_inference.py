# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import shlex
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.config.config_manager import ConfigManager
from src.utils.action_intents import INTENT_CMD_RUN
from src.utils.design_doc_parser import DesignDocParser
from src.code_generation.design_ops_resolver import DesignOpsResolver
from src.morph_analyzer.morph_analyzer import MorphAnalyzer
from src.design_parser.data_source_utils import parse_data_source_tag
from src.utils.entity_inference import infer_target_entity
from src.utils.text_parser import extract_first_quoted_literal, extract_urls
from src.utils.semantic_intents import (
    INTENT_CALC,
    INTENT_DATABASE_QUERY,
    INTENT_DISPLAY,
    INTENT_FETCH,
    INTENT_FILE_IO,
    INTENT_GENERAL,
    INTENT_HTTP_REQUEST,
    INTENT_JSON_DESERIALIZE,
    INTENT_LINQ,
    INTENT_PERSIST,
    INTENT_RETURN,
    INTENT_TRANSFORM,
    NODE_CONDITION,
    NODE_ELSE,
    NODE_END,
    NODE_LOOP,
    NODE_ACTION,
)


@dataclass
class InferenceIssue:
    step_index: int
    reason: str
    detail: str


class DesignInferenceEngine:
    """Infer missing design metadata deterministically and persist into .design.md."""

    _INFERENCE_RULES_VERSION = "v1"
    _PLAIN_SOURCE_DESCRIPTION_PROFILES = [
        {"text": "標準入力", "source_ref": "STDIN", "source_kind": "stdin"},
        {"text": "Product API Endpoint", "source_ref": "product_api", "source_kind": "http"},
        {"text": "Local SQL Database", "source_ref": "local_db", "source_kind": "db"},
    ]
    _EXPLICIT_OP_HINTS = {
        "trim_upper": {
            "intents": {INTENT_TRANSFORM},
            "requires_all": ["トリム", "大文字"],
            "meta": {"target_entity": "string", "output_type": "string"},
        },
        "split_lines": {
            "intents": {INTENT_TRANSFORM},
            "requires_all": ["行", "分割"],
            "meta": {"target_entity": "string", "output_type": "List<string>"},
        },
        "csv_serialize": {
            "intents": {INTENT_TRANSFORM},
            "requires_all": ["csv"],
            "requires_any": ["文字列", "形式", "変換"],
            "meta": {"target_entity": "string", "output_type": "string"},
        },
        "aggregate_by_product": {
            "intents": {INTENT_CALC},
            "requires_all": ["商品別"],
            "requires_any": ["合計", "集計"],
            "meta": {"target_entity": "decimal", "output_type": "Dictionary<string, decimal>"},
        },
        "display_names": {
            "intents": {INTENT_DISPLAY},
            "requires_all": ["名前"],
            "requires_any": ["一覧", "リスト", "改行", "まとめ"],
            "meta": {},
        },
    }

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

    def infer_then_freeze(self, design_path: str, suggestion_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not os.path.exists(design_path):
            return {"status": "error", "message": f"Design document not found: {design_path}"}

        with open(design_path, "r", encoding="utf-8") as f:
            original = f.read()
        self._assist_metadata = None
        if suggestion_payload:
            original, applied_steps = self._apply_literal_suggestions_to_content(original, suggestion_payload)
            if applied_steps:
                self._assist_metadata = {
                    "provider": suggestion_payload.get("provider"),
                    "model_id": suggestion_payload.get("model_id"),
                    "mode": suggestion_payload.get("mode"),
                    "applied_steps": applied_steps,
                }

        parsed = self.parser.parse_content(original)
        spec = parsed.get("specification", {}) if isinstance(parsed, dict) else {}
        core_logic = spec.get("core_logic", []) if isinstance(spec, dict) else []
        io_inputs = spec.get("input", []) if isinstance(spec, dict) else []
        output_spec = spec.get("output", {}) if isinstance(spec, dict) else {}
        output_format = str(output_spec.get("format") or "").strip().lower()
        module_name = str(parsed.get("module_name") or "").strip()

        if not core_logic:
            return {"status": "no_change", "message": "Core Logic is empty."}

        self._current_io_inputs = io_inputs if isinstance(io_inputs, list) else []
        data_sources = self._collect_data_sources(core_logic)
        self._current_data_sources = [ds for ds in (parse_data_source_tag(s, {"db","http","file","memory","env","stdin"}) for s in data_sources) if ds]
        updated_lines: List[str] = []
        issues: List[InferenceIssue] = []
        inferred_any = False

        step_idx = 0
        last_persist_path: Optional[str] = None
        non_data_lines = [line for line in core_logic if not self._resolve_data_source_tag(line)]
        last_step_idx = len(non_data_lines)
        last_output_type: Optional[str] = None
        for raw in core_logic:
            line = str(raw)
            data_source_tag = self._resolve_data_source_tag(line)
            if data_source_tag:
                updated_lines.append(line)
                continue

            step_idx += 1
            is_last_step = step_idx == last_step_idx
            if self._has_explicit_step_meta(line):
                explicit_roles = self._extract_semantic_roles(line)
                if not explicit_roles:
                    explicit_intent = self._extract_intent_from_line(line)
                    if explicit_intent == INTENT_LINQ:
                        pass
                updated_lines.append(line)
                last_output_type = self._extract_output_type_from_line(line) or last_output_type
                intent = self._extract_intent_from_line(line)
                roles = self._extract_semantic_roles(line)
                if intent == INTENT_PERSIST:
                    path_val = roles.get("path")
                    if isinstance(path_val, str) and path_val:
                        last_persist_path = path_val
                    else:
                        source_ref = self._extract_source_ref_from_line(line)
                        if source_ref:
                            last_persist_path = source_ref
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
                if intent == INTENT_PERSIST:
                    path_val = roles.get("path")
                    if isinstance(path_val, str) and path_val:
                        last_persist_path = path_val
                    else:
                        source_ref = self._extract_source_ref_from_line(updated_lines[-1])
                        if source_ref:
                            last_persist_path = source_ref

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

    def _apply_literal_suggestions_to_content(self, content: str, suggestion_payload: Dict[str, Any]) -> Tuple[str, List[int]]:
        result = suggestion_payload.get("result", {}) if isinstance(suggestion_payload, dict) else {}
        suggestions = result.get("accepted_suggestions", []) if isinstance(result, dict) else []
        if not isinstance(suggestions, list) or not suggestions:
            return content, []
        suggestion_map: Dict[int, Dict[str, Any]] = {}
        for item in suggestions:
            if not isinstance(item, dict):
                continue
            step_number = item.get("step_number")
            semantic_roles = item.get("semantic_roles", {}) or {}
            if not isinstance(step_number, int) or not isinstance(semantic_roles, dict):
                continue
            filtered = {
                key: value
                for key, value in semantic_roles.items()
                if key in {"path", "url", "sql"} and isinstance(value, str) and value.strip()
            }
            if filtered:
                suggestion_map[step_number] = filtered
        if not suggestion_map:
            return content, []

        lines = content.splitlines()
        updated_lines: List[str] = []
        in_core = False
        step_idx = 0
        applied_steps: List[int] = []
        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()
            if lower.startswith("### core logic"):
                in_core = True
                updated_lines.append(line)
                continue
            if in_core and (lower.startswith("### ") or lower.startswith("## ")):
                in_core = False
                updated_lines.append(line)
                continue
            if not in_core:
                updated_lines.append(line)
                continue
            if self._resolve_data_source_tag(line):
                updated_lines.append(line)
                continue
            if not stripped:
                updated_lines.append(line)
                continue
            step_idx += 1
            suggested_roles = suggestion_map.get(step_idx)
            if not suggested_roles:
                updated_lines.append(line)
                continue
            merged_line, changed = self._merge_literal_roles_into_line(line, suggested_roles)
            updated_lines.append(merged_line)
            if changed:
                applied_steps.append(step_idx)
        if not applied_steps:
            return content, []
        updated_content = "\n".join(updated_lines)
        if content.endswith("\n"):
            updated_content += "\n"
        return updated_content, applied_steps

    def _merge_literal_roles_into_line(self, line: str, suggested_roles: Dict[str, Any]) -> Tuple[str, bool]:
        existing_roles = self._extract_semantic_roles(line)
        merged_roles = dict(existing_roles or {})
        changed = False
        for key, value in suggested_roles.items():
            if key not in merged_roles:
                merged_roles[key] = value
                changed = True
        if not changed:
            return line, False
        semantic_roles_tag = self._build_semantic_roles_tag(merged_roles)
        if existing_roles:
            return self._replace_semantic_roles_tag(line, semantic_roles_tag), True
        return self._append_semantic_roles(line, semantic_roles_tag), True

    def _replace_semantic_roles_tag(self, line: str, semantic_roles_tag: str) -> str:
        marker = "[semantic_roles:"
        idx = line.find(marker)
        if idx == -1:
            return self._append_semantic_roles(line, semantic_roles_tag)
        end = self._find_bracket_end(line[idx:])
        if end == -1:
            return self._append_semantic_roles(line, semantic_roles_tag)
        suffix_start = idx + end + 1
        return f"{line[:idx]}{semantic_roles_tag}{line[suffix_start:]}"

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
        command_literal = self._extract_command_literal(line, self.resolver.get_entities(line))
        env_sources, stdin_sources, http_sources, file_sources = self._collect_source_kinds()
        db_sources = [s for s in getattr(self, "_current_data_sources", []) if s.get("kind") == "db"]
        fallback_line = self._strip_non_step_metadata_prefixes(line)
        existing_semantic_roles = self._extract_semantic_roles(line)

        def _merged_semantic_roles(extra_roles: Dict[str, Any]) -> Dict[str, Any]:
            merged = dict(existing_semantic_roles)
            merged.update(extra_roles or {})
            return merged

        def _try_structural_fallback() -> Optional[Tuple[bool, Optional[InferenceIssue], str, List[str]]]:
            stdin_meta = self._infer_plain_stdin_fetch_meta(fallback_line, step_idx, stdin_sources)
            if stdin_meta:
                tag = self._build_step_meta_tag(stdin_meta)
                refs = self._build_refs_tag(step_idx)
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles({}))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            env_meta = self._infer_plain_env_fetch_meta(fallback_line, env_sources)
            if env_meta:
                tag = self._build_step_meta_tag(env_meta)
                refs = self._build_refs_tag(step_idx)
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles({}))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            http_meta, http_roles = self._infer_plain_http_request_meta(fallback_line, http_sources)
            if http_meta:
                tag = self._build_step_meta_tag(http_meta)
                refs = self._build_refs_tag(step_idx)
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles(http_roles))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            file_source_fetch_meta, file_source_fetch_roles = self._infer_plain_file_source_fetch_meta(fallback_line, file_sources)
            if file_source_fetch_meta:
                tag = self._build_step_meta_tag(file_source_fetch_meta)
                refs = self._build_refs_tag(step_idx)
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles(file_source_fetch_roles))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            file_fetch_meta, file_fetch_roles = self._infer_plain_file_fetch_meta(fallback_line)
            if file_fetch_meta:
                tag = self._build_step_meta_tag(file_fetch_meta)
                refs = self._build_refs_tag(step_idx)
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles(file_fetch_roles))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            deserialize_meta = self._infer_plain_json_deserialize_meta(fallback_line)
            if deserialize_meta:
                tag = self._build_step_meta_tag(deserialize_meta)
                refs = self._build_refs_tag(step_idx)
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles({}))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            linq_meta = self._infer_plain_linq_meta(fallback_line)
            if linq_meta:
                linq_roles: Dict[str, Any] = {}
                filter_prop = self._infer_filter_property(fallback_line)
                if filter_prop:
                    linq_roles["property"] = filter_prop
                tag = self._build_step_meta_tag(linq_meta)
                refs = self._build_refs_tag(step_idx)
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles(linq_roles))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            db_query_meta, db_query_roles = self._infer_plain_db_query_meta(
                fallback_line,
                db_sources,
                _merged_semantic_roles({}),
            )
            if db_query_meta:
                tag = self._build_step_meta_tag(db_query_meta)
                refs = self._build_refs_tag(step_idx)
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles(db_query_roles))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                data_sources = []
                if db_query_meta.get("source_ref") == "db_main":
                    data_sources.append("[data_source|db_main|db]")
                return True, None, new_line, data_sources
            db_persist_meta, db_persist_roles = self._infer_plain_db_persist_meta(fallback_line, db_sources)
            if db_persist_meta:
                tag = self._build_step_meta_tag(db_persist_meta)
                refs = self._build_refs_tag(step_idx)
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles(db_persist_roles))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            ops_meta, ops_roles = self._infer_ops_only_fallback(fallback_line, last_output_type)
            if ops_meta:
                tag = self._build_step_meta_tag(ops_meta)
                refs = self._build_refs_tag(step_idx)
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles(ops_roles))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            loop_meta = self._infer_plain_loop_meta(fallback_line, last_output_type)
            if loop_meta:
                tag = self._build_step_meta_tag(loop_meta)
                refs = self._build_refs_tag(step_idx)
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles({}))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            display_meta = self._infer_plain_display_meta(fallback_line, last_output_type)
            if display_meta:
                tag = self._build_step_meta_tag(display_meta)
                refs = self._build_refs_tag(step_idx)
                display_roles: Dict[str, Any] = {}
                display_prop = self._infer_display_property(fallback_line)
                if display_prop:
                    display_roles["property"] = display_prop
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles(display_roles))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            persist_meta = self._infer_plain_persist_meta(fallback_line, file_sources)
            if persist_meta:
                persist_roles: Dict[str, Any] = {}
                if persist_meta.get("source_kind") == "file" and persist_meta.get("source_ref"):
                    persist_roles["path"] = persist_meta["source_ref"]
                tag = self._build_step_meta_tag(persist_meta)
                refs = self._build_refs_tag(step_idx)
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles(persist_roles))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            return_true_meta, return_true_roles = self._infer_plain_return_true_meta(fallback_line, output_format, is_last_step)
            if return_true_meta:
                tag = self._build_step_meta_tag(return_true_meta)
                refs = self._build_refs_tag(step_idx)
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles(return_true_roles))
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            if command_literal and self._is_command_execution_line(fallback_line):
                if not self._is_allowed_command_literal(command_literal):
                    return False, InferenceIssue(step_idx, "UNSAFE_COMMAND", command_literal), line, []
                meta = {
                    "kind": NODE_ACTION,
                    "intent": INTENT_CMD_RUN,
                    "target_entity": "string",
                    "output_type": "void",
                    "side_effect": "NONE",
                }
                semantic_roles_tag = self._build_semantic_roles_tag(_merged_semantic_roles({"command": command_literal}))
                tag = self._build_step_meta_tag(meta)
                refs = self._build_refs_tag(step_idx)
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            if is_last_step and output_format and output_format not in ["void", "none"] and last_persist_path:
                meta = {
                    "kind": NODE_ACTION,
                    "intent": INTENT_TRANSFORM,
                    "target_entity": "Item",
                    "output_type": self._normalize_output_type(output_format) or "void",
                    "side_effect": "NONE",
                }
                semantic_roles_tag = self._build_semantic_roles_tag(
                    _merged_semantic_roles({"return_value": str(last_persist_path)})
                )
                tag = self._build_step_meta_tag(meta)
                refs = self._build_refs_tag(step_idx)
                new_line = self._prefix_inferred_tags(fallback_line, tag, refs, semantic_roles_tag)
                return True, None, new_line, []
            return None

        if not step_token:
            fallback = _try_structural_fallback()
            if fallback:
                return fallback
            return False, InferenceIssue(step_idx, "NO_CANDIDATE", "No deterministic candidate found."), line, []
        if score < self.thresholds["intent_threshold"]:
            fallback = _try_structural_fallback()
            if fallback:
                return fallback
            preferred_ok = False
            if step_token and step_token.startswith("intent."):
                intent = step_token.split(".", 1)[1].upper()
                hints = self.resolver.get_intent_hints(line)
                preferred = [str(p).upper() for p in (hints.get("preferred_intents") or [])]
                if intent in preferred:
                    preferred_ok = True
            if not preferred_ok:
                env_fetch_meta = self._infer_plain_env_fetch_meta(line, env_sources)
                if env_fetch_meta:
                    step_token = "intent.FETCH"
                    score = self.thresholds["intent_threshold"]
                    preferred_ok = True
            if not preferred_ok and self._infer_plain_stdin_fetch_meta(line, step_idx, stdin_sources):
                step_token = "intent.FETCH"
                score = self.thresholds["intent_threshold"]
                preferred_ok = True
            if not preferred_ok:
                return False, InferenceIssue(step_idx, "NO_CANDIDATE", f"No deterministic candidate above threshold. score={score:.3f}"), line, []

        meta = self._map_step_token_to_meta(step_token)
        if not meta:
            return False, InferenceIssue(step_idx, "UNMAPPED_TOKEN", step_token), line, []

        semantic_roles: Dict[str, Any] = dict(existing_semantic_roles)
        sql_literal = ""
        entities = self.resolver.get_entities(line)
        command_literal = command_literal or self._extract_command_literal(line, entities)
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
        env_fetch_meta = self._infer_plain_env_fetch_meta(line, env_sources)
        if env_fetch_meta:
            meta = env_fetch_meta
        elif self._looks_like_plain_file_read(line) and not self._looks_like_plain_json_deserialize(line):
            file_fetch_meta, file_fetch_roles = self._infer_plain_file_fetch_meta(line)
            if file_fetch_meta:
                meta = file_fetch_meta
                semantic_roles.update(file_fetch_roles)
        elif meta.get("intent") == INTENT_JSON_DESERIALIZE:
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
                    semantic_roles["path"] = str(filename_val)
        elif self._looks_like_plain_file_read(line):
            file_fetch_meta, file_fetch_roles = self._infer_plain_file_fetch_meta(line)
            if file_fetch_meta:
                meta = file_fetch_meta
                semantic_roles.update(file_fetch_roles)
        elif self._looks_like_plain_json_deserialize(line):
            deserialize_meta = self._infer_plain_json_deserialize_meta(line)
            if deserialize_meta:
                meta = deserialize_meta
        elif self._looks_like_plain_linq(line):
            linq_meta = self._infer_plain_linq_meta(line)
            if linq_meta:
                meta = linq_meta
        if meta.get("intent") == INTENT_DISPLAY:
            display_entity = self._infer_entity_from_output_type(last_output_type)
            if not display_entity:
                inferred_entity = infer_target_entity(line, [], self.entity_schema, self.morph_analyzer)
                if inferred_entity and inferred_entity != "Item":
                    display_entity = inferred_entity
            if display_entity and str(meta.get("target_entity") or "") in ["", "Item", "string"]:
                meta = dict(meta)
                meta["target_entity"] = display_entity
        if meta.get("intent") == INTENT_DISPLAY and "property" not in semantic_roles:
            display_prop = self._infer_display_property(line)
            if display_prop:
                semantic_roles["property"] = display_prop
        if meta.get("intent") == INTENT_LINQ and "property" not in semantic_roles:
            filter_prop = self._infer_filter_property(line)
            if filter_prop:
                semantic_roles["property"] = filter_prop
        if meta.get("intent") == INTENT_HTTP_REQUEST and "url" not in semantic_roles:
            url_literal = self._extract_url_literal(line, entities)
            if url_literal:
                semantic_roles["url"] = url_literal
        if meta.get("intent") == INTENT_CMD_RUN:
            if not command_literal:
                return False, InferenceIssue(step_idx, "MISSING_COMMAND", "Command literal required for CMD_RUN."), line, []
            if not self._is_allowed_command_literal(command_literal):
                return False, InferenceIssue(step_idx, "UNSAFE_COMMAND", command_literal), line, []
            semantic_roles["command"] = command_literal
        inferred_ops = self._infer_explicit_ops(line, str(meta.get("intent") or ""))
        if inferred_ops:
            semantic_roles["ops"] = inferred_ops
            meta = self._apply_ops_meta_overrides(meta, inferred_ops)
        source_override_applied = False
        if meta.get("intent") in [INTENT_HTTP_REQUEST, INTENT_FILE_IO, INTENT_FETCH]:
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
                meta["side_effect"] = "IO" if meta["intent"] in [INTENT_FETCH, INTENT_FILE_IO] else meta.get("side_effect", "NONE")
                if meta.get("intent") == INTENT_FETCH:
                    meta["output_type"] = meta.get("output_type") or "string"
                source_override_applied = True
        if meta.get("intent") in [INTENT_DATABASE_QUERY, INTENT_PERSIST]:
            sql_literal = self._extract_sql_literal(line)
            if not sql_literal:
                alt_token, alt_score = self.resolver.infer_step_with_score_excluding_intents(
                    line,
                    module_name,
                    exclude_intents={INTENT_DATABASE_QUERY, INTENT_PERSIST},
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
                meta["output_type"] = "List<Item>" if sql_intent == INTENT_DATABASE_QUERY else "void"
            semantic_roles["sql"] = sql_literal

        if meta.get("intent") in [INTENT_HTTP_REQUEST, INTENT_FILE_IO, INTENT_FETCH] and not has_url and not has_filename:
            if not http_sources and meta.get("intent") == INTENT_HTTP_REQUEST:
                alt_token, alt_score = self.resolver.infer_step_with_score_excluding_intents(
                    line,
                    module_name,
                    exclude_intents={INTENT_HTTP_REQUEST, INTENT_DATABASE_QUERY, INTENT_PERSIST},
                )
                if alt_token and alt_score >= self.thresholds["intent_threshold"]:
                    step_token = alt_token
                    meta = self._map_step_token_to_meta(step_token)
            if meta.get("intent") == INTENT_FILE_IO:
                alt_token, alt_score = self.resolver.infer_step_with_score_excluding_intents(
                    line,
                    module_name,
                    exclude_intents={INTENT_FILE_IO, INTENT_HTTP_REQUEST, INTENT_DATABASE_QUERY, INTENT_PERSIST},
                )
                if alt_token and alt_score >= self.thresholds["intent_threshold"]:
                    step_token = alt_token
                    meta = self._map_step_token_to_meta(step_token)
                elif not source_override_applied:
                    meta = dict(meta)
                    meta["intent"] = INTENT_TRANSFORM
                    meta["side_effect"] = "NONE"
                    meta["output_type"] = last_output_type or "string"
            if meta.get("intent") == INTENT_FETCH:
                alt_token, alt_score = self.resolver.infer_step_with_score_excluding_intents(
                    line,
                    module_name,
                    exclude_intents={INTENT_FETCH, INTENT_FILE_IO, INTENT_HTTP_REQUEST, INTENT_DATABASE_QUERY, INTENT_PERSIST},
                )
                if alt_token and alt_score >= self.thresholds["intent_threshold"]:
                    step_token = alt_token
                    meta = self._map_step_token_to_meta(step_token)
                elif not source_override_applied:
                    meta = dict(meta)
                    meta["intent"] = INTENT_TRANSFORM
                    meta["side_effect"] = "NONE"
                    meta["output_type"] = last_output_type or "string"

        loop_meta = self._infer_plain_loop_meta(line, last_output_type)
        if loop_meta:
            meta = loop_meta

        persist_meta = self._infer_plain_persist_meta(line, file_sources)
        if persist_meta:
            meta = persist_meta
            if meta.get("source_kind") == "file" and meta.get("source_ref"):
                semantic_roles.setdefault("path", meta["source_ref"])
        db_persist_meta, db_persist_roles = self._infer_plain_db_persist_meta(line, db_sources)
        if db_persist_meta:
            meta = db_persist_meta
            semantic_roles.update(db_persist_roles)

        if "ops" not in semantic_roles:
            inferred_ops = self._infer_explicit_ops(line, str(meta.get("intent") or ""))
            if inferred_ops:
                semantic_roles["ops"] = inferred_ops
                meta = self._apply_ops_meta_overrides(meta, inferred_ops)
            else:
                ops_meta, ops_roles = self._infer_ops_only_fallback(line, last_output_type)
                if ops_meta and ops_roles.get("ops"):
                    meta = ops_meta
                    semantic_roles.update(ops_roles)

        return_meta, return_roles = self._infer_plain_return_meta(
            line,
            output_format,
            last_persist_path,
            is_last_step,
        )
        if return_meta:
            meta = return_meta
            semantic_roles.update(return_roles)
        return_true_meta, return_true_roles = self._infer_plain_return_true_meta(line, output_format, is_last_step)
        if return_true_meta:
            meta = return_true_meta
            semantic_roles.update(return_true_roles)

        if meta.get("intent") == INTENT_RETURN and "sql" in semantic_roles:
            semantic_roles.pop("sql", None)

        if "return_value" not in semantic_roles and is_last_step and output_format and output_format not in ["void", "none"] and last_persist_path:
            if meta.get("intent") in [INTENT_TRANSFORM, INTENT_GENERAL, INTENT_DISPLAY]:
                semantic_roles["return_value"] = str(last_persist_path)
        semantic_roles_tag = self._build_semantic_roles_tag(semantic_roles)
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
                return src_id, "env", INTENT_FETCH
        if len(env_sources) == 1 and not http_sources and not file_sources and not stdin_sources:
            src = env_sources[0]
            return src.get("id", "env"), "env", INTENT_FETCH
        if step_idx == 1 and len(stdin_sources) == 1 and not http_sources and not file_sources:
            src = stdin_sources[0]
            return src.get("id", "STDIN"), "stdin", INTENT_FETCH
        for src in file_sources:
            src_id = str(src.get("id") or "")
            if src_id == "input_path" and "入力ファイルパス" in text:
                return src_id, "file", INTENT_FETCH
            if src_id == "output_path" and "出力ファイルパス" in text:
                return src_id, "file", INTENT_FILE_IO
        if len(http_sources) == 1 and self._extract_url_literal(text, {}):
            src = http_sources[0]
            return src.get("id", "http_main"), "http", INTENT_HTTP_REQUEST
        return None

    def _infer_plain_stdin_fetch_meta(
        self,
        line: str,
        step_idx: int,
        stdin_sources: List[Dict[str, str]],
    ) -> Optional[Dict[str, str]]:
        if step_idx != 1 or len(stdin_sources) != 1:
            return None
        normalized = str(line).strip()
        if "標準入力" not in normalized:
            return None
        if "取得" not in normalized and "読み" not in normalized:
            return None
        src = stdin_sources[0]
        return {
            "kind": NODE_ACTION,
            "intent": INTENT_FETCH,
            "target_entity": "string",
            "output_type": "string",
            "side_effect": "IO",
            "source_ref": src.get("id", "STDIN"),
            "source_kind": "stdin",
        }

    def _infer_plain_env_fetch_meta(
        self,
        line: str,
        env_sources: List[Dict[str, str]],
    ) -> Optional[Dict[str, str]]:
        normalized = str(line).strip()
        if "環境変数" not in normalized:
            return None
        if "取得" not in normalized and "読み" not in normalized:
            return None
        source_ref = None
        for src in env_sources:
            src_id = str(src.get("id") or "").strip()
            if src_id and src_id in normalized:
                source_ref = src_id
                break
        if not source_ref:
            if len(env_sources) != 1:
                return None
            source_ref = str(env_sources[0].get("id") or "env").strip() or "env"
        return {
            "kind": NODE_ACTION,
            "intent": INTENT_FETCH,
            "target_entity": "string",
            "output_type": "string",
            "side_effect": "IO",
            "source_ref": source_ref,
            "source_kind": "env",
        }

    def _infer_plain_http_request_meta(
        self,
        line: str,
        http_sources: List[Dict[str, str]],
    ) -> Tuple[Optional[Dict[str, str]], Dict[str, Any]]:
        url_literal = self._extract_url_literal(line, {})
        if not url_literal:
            return None, {}
        normalized = str(line).strip()
        if "取得" not in normalized and "読み" not in normalized and "呼び出" not in normalized:
            return None, {}
        source_ref = "http_main"
        if len(http_sources) == 1:
            source_ref = str(http_sources[0].get("id") or source_ref)
        return (
            {
                "kind": NODE_ACTION,
                "intent": INTENT_HTTP_REQUEST,
                "target_entity": "Item",
                "output_type": "string",
                "side_effect": "NETWORK",
                "source_ref": source_ref,
                "source_kind": "http",
            },
            {"url": url_literal},
        )

    def _looks_like_plain_file_read(self, line: str) -> bool:
        normalized = str(line).strip()
        return ("読み込" in normalized or "ロード" in normalized) and extract_first_quoted_literal(normalized) is not None

    def _infer_plain_file_fetch_meta(self, line: str) -> Tuple[Optional[Dict[str, str]], Dict[str, Any]]:
        quoted = extract_first_quoted_literal(str(line))
        if not quoted or not self._is_likely_filename(quoted):
            return None, {}
        if not self._looks_like_plain_file_read(line):
            return None, {}
        return (
            {
                "kind": NODE_ACTION,
                "intent": INTENT_FETCH,
                "target_entity": "string",
                "output_type": "string",
                "side_effect": "IO",
            },
            {"path": quoted},
        )

    def _infer_plain_file_source_fetch_meta(
        self,
        line: str,
        file_sources: List[Dict[str, str]],
    ) -> Tuple[Optional[Dict[str, str]], Dict[str, Any]]:
        normalized = str(line).strip()
        if "読み込" not in normalized and "ロード" not in normalized:
            return None, {}
        for src in file_sources:
            src_id = str(src.get("id") or "").strip()
            if src_id == "input_path" and "入力ファイルパス" in normalized:
                return (
                    {
                        "kind": NODE_ACTION,
                        "intent": INTENT_FETCH,
                        "target_entity": "string",
                        "output_type": "string",
                        "side_effect": "IO",
                        "source_ref": src_id,
                        "source_kind": "file",
                    },
                    {"path": src_id},
                )
        return None, {}

    def _looks_like_plain_json_deserialize(self, line: str) -> bool:
        normalized = str(line).strip()
        return "変換" in normalized and any(token in normalized for token in ["リスト", "一覧", "配列"])

    def _infer_plain_json_deserialize_meta(self, line: str) -> Optional[Dict[str, str]]:
        if not self._looks_like_plain_json_deserialize(line):
            return None
        inferred_entity = infer_target_entity(line, [], self.entity_schema, self.morph_analyzer) or "Item"
        output_type = f"List<{inferred_entity}>"
        return {
            "kind": NODE_ACTION,
            "intent": INTENT_JSON_DESERIALIZE,
            "target_entity": inferred_entity,
            "output_type": output_type,
            "side_effect": "NONE",
        }

    def _looks_like_plain_linq(self, line: str) -> bool:
        normalized = str(line).strip()
        return "抽出" in normalized

    def _infer_plain_linq_meta(self, line: str) -> Optional[Dict[str, str]]:
        if not self._looks_like_plain_linq(line):
            return None
        inferred_entity = infer_target_entity(line, [], self.entity_schema, self.morph_analyzer) or "Item"
        return {
            "kind": NODE_ACTION,
            "intent": INTENT_LINQ,
            "target_entity": inferred_entity,
            "output_type": f"List<{inferred_entity}>",
            "side_effect": "NONE",
        }

    def _infer_ops_only_fallback(
        self,
        line: str,
        last_output_type: Optional[str],
    ) -> Tuple[Optional[Dict[str, str]], Dict[str, Any]]:
        matched_ops: List[str] = []
        inferred_intent = ""
        for op_name, hint in self._EXPLICIT_OP_HINTS.items():
            intents = [str(v).upper() for v in (hint.get("intents") or []) if v]
            if len(intents) != 1:
                continue
            candidate_intent = intents[0]
            op_matches = self._infer_explicit_ops(line, candidate_intent)
            if op_name not in op_matches:
                continue
            if inferred_intent and inferred_intent != candidate_intent:
                continue
            inferred_intent = candidate_intent
            matched_ops.append(op_name)
        if not matched_ops or not inferred_intent:
            return None, {}

        meta = {
            "kind": NODE_ACTION,
            "intent": inferred_intent,
            "target_entity": last_output_type or "string",
            "output_type": "void",
            "side_effect": "NONE",
        }
        if inferred_intent == INTENT_TRANSFORM:
            meta["output_type"] = last_output_type or "string"
        elif inferred_intent == INTENT_DISPLAY:
            meta["target_entity"] = last_output_type or "Item"
            meta["output_type"] = "void"
        elif inferred_intent == INTENT_CALC:
            meta["target_entity"] = "decimal"
            meta["output_type"] = "decimal"
        meta = self._apply_ops_meta_overrides(meta, matched_ops)
        return meta, {"ops": matched_ops}

    def _infer_plain_loop_meta(
        self,
        line: str,
        last_output_type: Optional[str],
    ) -> Optional[Dict[str, str]]:
        normalized = str(line).strip()
        if "順に処理" not in normalized and "各行" not in normalized:
            return None
        return {
            "kind": NODE_LOOP,
            "intent": INTENT_GENERAL,
            "target_entity": last_output_type or "Item",
            "output_type": "void",
            "side_effect": "NONE",
        }

    def _infer_plain_display_meta(
        self,
        line: str,
        last_output_type: Optional[str],
    ) -> Optional[Dict[str, str]]:
        normalized = str(line).strip()
        if "表示" not in normalized:
            return None
        display_entity = self._infer_entity_from_output_type(last_output_type) or last_output_type or "Item"
        return {
            "kind": NODE_ACTION,
            "intent": INTENT_DISPLAY,
            "target_entity": display_entity,
            "output_type": "void",
            "side_effect": "NONE",
        }

    def _infer_plain_persist_meta(
        self,
        line: str,
        file_sources: List[Dict[str, str]],
    ) -> Optional[Dict[str, str]]:
        normalized = str(line).strip()
        if "書き出" not in normalized and "保存" not in normalized:
            return None
        for src in file_sources:
            src_id = str(src.get("id") or "")
            if src_id == "output_path" and "出力ファイルパス" in normalized:
                return {
                    "kind": NODE_ACTION,
                    "intent": INTENT_PERSIST,
                    "target_entity": "string",
                    "output_type": "void",
                    "side_effect": "IO",
                    "source_ref": src_id,
                    "source_kind": "file",
                }
        return None

    def _infer_plain_db_persist_meta(
        self,
        line: str,
        db_sources: List[Dict[str, str]],
    ) -> Tuple[Optional[Dict[str, str]], Dict[str, Any]]:
        normalized = str(line).strip()
        if "sql" not in normalized.lower():
            return None, {}
        if "保存" not in normalized and "更新" not in normalized and "登録" not in normalized:
            return None, {}
        sql_literal = self._extract_sql_literal(normalized)
        if not sql_literal:
            return None, {}
        source_ref = "db_main"
        for src in db_sources:
            src_id = str(src.get("id") or "")
            if src_id:
                source_ref = src_id
                break
        return (
            {
                "kind": NODE_ACTION,
                "intent": INTENT_PERSIST,
                "target_entity": "Item",
                "output_type": "void",
                "side_effect": "DB",
                "source_ref": source_ref,
                "source_kind": "db",
            },
            {"sql": sql_literal},
        )

    def _infer_plain_db_query_meta(
        self,
        line: str,
        db_sources: List[Dict[str, str]],
        semantic_roles: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, str]], Dict[str, Any]]:
        sql_literal = ""
        role_sql = semantic_roles.get("sql") if isinstance(semantic_roles, dict) else None
        if isinstance(role_sql, str) and role_sql.strip():
            sql_literal = role_sql.strip()
        if not sql_literal:
            sql_literal = self._extract_sql_literal(str(line))
        if not sql_literal or self._classify_sql_intent(sql_literal) != INTENT_DATABASE_QUERY:
            return None, {}
        if not db_sources:
            return None, {}
        source_ref = ""
        for src in db_sources:
            src_id = str(src.get("id") or "").strip()
            if src_id:
                source_ref = src_id
                break
        if not source_ref:
            return None, {}
        inferred_entity = infer_target_entity(line, [], self.entity_schema, self.morph_analyzer) or "Item"
        return (
            {
                "kind": NODE_ACTION,
                "intent": INTENT_DATABASE_QUERY,
                "target_entity": inferred_entity,
                "output_type": f"IEnumerable<{inferred_entity}>",
                "side_effect": "DB",
                "source_ref": source_ref,
                "source_kind": "db",
            },
            {"sql": sql_literal},
        )

    def _infer_plain_return_meta(
        self,
        line: str,
        output_format: str,
        last_persist_path: Optional[str],
        is_last_step: bool,
    ) -> Tuple[Optional[Dict[str, str]], Dict[str, Any]]:
        if not is_last_step or not last_persist_path:
            return None, {}
        normalized = str(line).strip()
        if "返す" not in normalized and "戻す" not in normalized:
            return None, {}
        return (
            {
                "kind": NODE_ACTION,
                "intent": INTENT_TRANSFORM,
                "target_entity": "string",
                "output_type": self._normalize_output_type(output_format) or "string",
                "side_effect": "NONE",
            },
            {"return_value": str(last_persist_path)},
        )

    def _infer_plain_return_true_meta(
        self,
        line: str,
        output_format: str,
        is_last_step: bool,
    ) -> Tuple[Optional[Dict[str, str]], Dict[str, Any]]:
        if not is_last_step:
            return None, {}
        normalized = str(line).strip().lower()
        if "返す" not in normalized and "戻す" not in normalized:
            return None, {}
        if "true" not in normalized:
            return None, {}
        return (
            {
                "kind": NODE_ACTION,
                "intent": INTENT_RETURN,
                "target_entity": "bool",
                "output_type": self._normalize_output_type(output_format) or "bool",
                "side_effect": "NONE",
            },
            {"return_value": "true"},
        )

    def _load_entity_schema(self) -> Dict[str, Any]:
        path = os.path.join(self.config_manager.workspace_root, "resources", "entity_schema.json")
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _extract_url_literal(self, line: str, entities: Dict[str, Any]) -> str:
        url_entity = entities.get("url") if isinstance(entities, dict) else None
        if isinstance(url_entity, dict):
            value = str(url_entity.get("value") or "").strip()
            if value:
                return value
        urls = extract_urls(line)
        return urls[0] if urls else ""

    def _extract_command_literal(self, line: str, entities: Dict[str, Any]) -> str:
        command_entity = entities.get("command") if isinstance(entities, dict) else None
        if isinstance(command_entity, dict):
            value = str(command_entity.get("value") or "").strip()
            if value:
                return value
        return ""

    def _is_command_execution_line(self, line: str) -> bool:
        text = str(line)
        return any(
            marker in text
            for marker in ["を実行", "を動かして", "を走らせて", "を起動"]
        )

    def _is_allowed_command_literal(self, command_literal: str) -> bool:
        if not command_literal:
            return False
        policy = self.config_manager.get_safety_policy() if self.config_manager else {}
        safe_commands = {
            str(cmd).lower()
            for cmd in (policy.get("safe_commands", []) if isinstance(policy, dict) else [])
            if str(cmd).strip()
        }
        if not safe_commands:
            return False
        try:
            parts = shlex.split(command_literal, posix=False)
        except ValueError:
            return False
        if not parts:
            return False
        return str(parts[0]).lower() in safe_commands


    def _map_step_token_to_meta(self, token: str) -> Optional[Dict[str, str]]:
        if not token or "." not in token:
            return None
        domain, op = token.split(".", 1)

        meta = {
            "kind": NODE_ACTION,
            "intent": INTENT_GENERAL,
            "target_entity": "Item",
            "output_type": "void",
            "side_effect": "NONE",
        }
        if domain == "repo":
            meta["side_effect"] = "DB"
            meta["source_ref"] = "db_main"
            meta["source_kind"] = "db"
            if op in ["fetch_all"]:
                meta["intent"] = INTENT_DATABASE_QUERY
                meta["output_type"] = "List<Item>"
            elif op in ["fetch_by_id"]:
                meta["intent"] = INTENT_DATABASE_QUERY
                meta["output_type"] = "Item"
            else:
                meta["intent"] = INTENT_PERSIST
        elif domain == "service":
            if op == "list":
                meta["intent"] = INTENT_DISPLAY
                meta["output_type"] = "void"
            elif op == "get":
                meta["intent"] = INTENT_FETCH
                meta["output_type"] = "Item"
            elif op in ["create", "update", "delete"]:
                meta["intent"] = INTENT_TRANSFORM
        elif domain == "calc":
            meta["intent"] = INTENT_CALC
            meta["output_type"] = "decimal"
        elif domain == "intent":
            intent = op.upper()
            meta["intent"] = intent
            if intent == INTENT_HTTP_REQUEST:
                meta["output_type"] = "string"
                meta["side_effect"] = "NETWORK"
            elif intent == INTENT_FETCH:
                meta["output_type"] = "string"
                meta["side_effect"] = "IO"
            elif intent == INTENT_JSON_DESERIALIZE:
                meta["output_type"] = "List<Item>"
            elif intent == INTENT_FILE_IO:
                meta["output_type"] = "string"
                meta["side_effect"] = "IO"
            elif intent == INTENT_DISPLAY:
                meta["output_type"] = "void"
            elif intent == INTENT_LINQ:
                meta["output_type"] = "List<Item>"
            elif intent == INTENT_TRANSFORM:
                meta["output_type"] = "void"
            elif intent == INTENT_CALC:
                meta["output_type"] = "decimal"
            elif intent == INTENT_CMD_RUN:
                meta["target_entity"] = "string"
                meta["output_type"] = "void"
                meta["side_effect"] = "NONE"
        else:
            return None
        return meta

    def _build_step_meta_tag(self, meta: Dict[str, str]) -> str:
        parts = [
            meta.get("kind", NODE_ACTION),
            meta.get("intent", INTENT_GENERAL),
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

    def _strip_non_step_metadata_prefixes(self, line: str) -> str:
        prefix, remainder = self._split_line_prefix(line)
        text = remainder.strip()
        while text.startswith("["):
            end = self._find_bracket_end(text)
            if end == -1:
                break
            meta = text[1:end].strip()
            lowered = meta.lower()
            if not (
                lowered.startswith("refs:")
                or lowered.startswith("ops:")
                or lowered.startswith("semantic_roles:")
            ):
                break
            text = text[end + 1 :].strip()
        return f"{prefix}{text}".rstrip()

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
            inferred = self._resolve_data_source_tag(line)
            if inferred:
                data_sources.append(inferred)
        return data_sources

    def _resolve_data_source_tag(self, line: str) -> str:
        if self._is_data_source_line(line):
            return self._strip_leading_numbering(str(line).strip())
        return self._infer_plain_data_source_tag(line)

    def _infer_plain_data_source_tag(self, line: str) -> str:
        normalized = self._strip_leading_numbering(str(line).strip())
        for profile in self._PLAIN_SOURCE_DESCRIPTION_PROFILES:
            if normalized == profile["text"]:
                return f'[data_source|{profile["source_ref"]}|{profile["source_kind"]}]'
        if self._is_likely_filename(normalized):
            source_ref = self._build_file_source_ref(normalized)
            if source_ref:
                return f"[data_source|{source_ref}|file]"
        io_inputs = getattr(self, "_current_io_inputs", []) or []
        io_file_aliases = {
            "入力CSV": "input_path",
            "出力CSV": "output_path",
        }
        expected_name = io_file_aliases.get(normalized)
        if expected_name:
            for item in io_inputs:
                name = str(item.get("name") or "").strip()
                if name == expected_name:
                    return f"[data_source|{expected_name}|file]"
        return ""

    def _build_file_source_ref(self, value: str) -> str:
        leaf = str(value).strip().replace("\\", "/").rsplit("/", 1)[-1]
        if not leaf:
            return ""
        chars = []
        previous_was_separator = False
        for ch in leaf:
            if ch.isalnum():
                chars.append(ch.lower())
                previous_was_separator = False
            elif not previous_was_separator:
                chars.append("_")
                previous_was_separator = True
        source_ref = "".join(chars).strip("_")
        return source_ref or "file_source"

    def _extract_output_type_from_line(self, line: str) -> Optional[str]:
        s = self._strip_leading_numbering(str(line).strip())
        if not s.startswith("["):
            return None
        end = self._find_bracket_end(s)
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
        if kind in [NODE_END, NODE_ELSE]:
            return None
        if kind in [NODE_LOOP, NODE_CONDITION] and len(parts) >= 3:
            return parts[2]
        if len(parts) >= 4:
            return parts[3]
        return None

    def _extract_intent_from_line(self, line: str) -> Optional[str]:
        s = self._strip_leading_numbering(str(line).strip())
        if not s.startswith("["):
            return None
        end = self._find_bracket_end(s)
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

    def _extract_source_ref_from_line(self, line: str) -> Optional[str]:
        s = self._strip_leading_numbering(str(line).strip())
        if not s.startswith("["):
            return None
        end = self._find_bracket_end(s)
        if end == -1:
            return None
        meta = s[1:end]
        lower = meta.lower()
        if lower.startswith("data_source|") or lower.startswith("refs:") or lower.startswith("ops:") or lower.startswith("semantic_roles:"):
            return None
        parts = [p.strip() for p in meta.split("|")]
        if len(parts) >= 6 and parts[5]:
            return parts[5]
        return None

    def _extract_semantic_roles(self, line: str) -> Dict[str, Any]:
        text = str(line)
        marker = "[semantic_roles:"
        idx = text.find(marker)
        if idx == -1:
            return {}
        start = idx + len(marker)
        end = self._find_bracket_end(text[idx:])
        if end == -1:
            return {}
        raw = text[start: idx + end].strip()
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

    def _build_semantic_roles_tag(self, semantic_roles: Dict[str, Any]) -> str:
        if not semantic_roles:
            return ""
        return f"[semantic_roles:{json.dumps(semantic_roles, ensure_ascii=False, separators=(',', ':'))}]"

    def _infer_explicit_ops(self, line: str, intent: str) -> List[str]:
        normalized = str(line).strip().lower()
        if not normalized or not intent:
            return []
        inferred: List[str] = []
        for op_name, hint in self._EXPLICIT_OP_HINTS.items():
            allowed_intents = hint.get("intents") or set()
            if allowed_intents and intent not in allowed_intents:
                continue
            requires_all = [str(v).lower() for v in (hint.get("requires_all") or []) if v]
            if requires_all and not all(token in normalized for token in requires_all):
                continue
            requires_any = [str(v).lower() for v in (hint.get("requires_any") or []) if v]
            if requires_any and not any(token in normalized for token in requires_any):
                continue
            inferred.append(op_name)
        return inferred

    def _apply_ops_meta_overrides(self, meta: Dict[str, str], ops: List[str]) -> Dict[str, str]:
        updated = dict(meta)
        for op_name in ops:
            hint = self._EXPLICIT_OP_HINTS.get(op_name) or {}
            for key, value in (hint.get("meta") or {}).items():
                if value:
                    updated[key] = value
        return updated

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

    def _infer_filter_property(self, line: str) -> Optional[str]:
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
        normalized = str(line).lower()
        for prop in props.keys():
            prop_name = str(prop)
            if prop_name.lower() in normalized:
                return prop_name
        localized_map = {
            "名前": "Name",
            "価格": "Price",
            "金額": "Price",
            "ポイント": "Points",
            "年齢": "Age",
            "id": "Id",
        }
        for token, prop_name in localized_map.items():
            if token.lower() in normalized and prop_name in props:
                return prop_name
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

    def _infer_entity_from_output_type(self, output_type: Optional[str]) -> str:
        if not output_type:
            return ""
        text = str(output_type).strip()
        if text.startswith("List<") and text.endswith(">"):
            inner = text[len("List<"):-1].strip()
            return inner if inner else ""
        if text.startswith("IEnumerable<") and text.endswith(">"):
            inner = text[len("IEnumerable<"):-1].strip()
            return inner if inner else ""
        if text.endswith("[]"):
            inner = text[:-2].strip()
            return inner if inner else ""
        return ""

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
        end = self._find_bracket_end(s)
        if end == -1:
            return False
        meta = s[1:end]
        if meta.lower().startswith("data_source|"):
            return False
        if meta.lower().startswith("ops:") or meta.lower().startswith("refs:") or meta.lower().startswith("semantic_roles:"):
            return False
        return "|" in meta

    def _find_bracket_end(self, text: str) -> int:
        in_string = False
        escape = False
        nested_square = 0
        for idx in range(1, len(text)):
            ch = text[idx]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "[":
                nested_square += 1
                continue
            if ch == "]":
                if nested_square == 0:
                    return idx
                nested_square -= 1
        return -1

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
        for literal in [extract_first_quoted_literal(text)]:
            if literal and self._classify_sql_intent(str(literal)):
                return str(literal).strip()
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
                return INTENT_DATABASE_QUERY
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
        assist = getattr(self, "_assist_metadata", None) or {}
        applied_steps = assist.get("applied_steps") or []
        if applied_steps:
            lines.append("- llm_literal_assist: true")
            lines.append(f"- llm_literal_assist_mode: {assist.get('mode') or 'literal_roles_only'}")
            if assist.get("provider"):
                lines.append(f"- llm_literal_assist_provider: {assist.get('provider')}")
            if assist.get("model_id"):
                lines.append(f"- llm_literal_assist_model_id: {assist.get('model_id')}")
            lines.append("- llm_literal_assist_applied_steps: " + ", ".join(str(step) for step in applied_steps))
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
    suggestion_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    engine = DesignInferenceEngine(
        config_manager=config_manager,
        vector_engine=vector_engine,
        morph_analyzer=morph_analyzer,
    )
    return engine.infer_then_freeze(design_path, suggestion_payload=suggestion_payload)
