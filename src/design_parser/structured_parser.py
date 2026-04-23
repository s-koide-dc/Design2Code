# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, List, Tuple

from src.design_parser.validator import validate_structured_spec_or_raise
from src.design_parser.data_source_utils import parse_data_source_tag
from src.utils.design_doc_parser import DesignDocParser


class StructuredDesignParser:
    """Convert .design.md content into StructuredSpec."""

    _ALLOWED_SOURCE_KINDS = {"db", "http", "file", "memory", "env", "stdin"}

    def __init__(self, knowledge_base=None) -> None:
        self._logger = logging.getLogger(__name__)
        self._legacy_parser = DesignDocParser(knowledge_base=knowledge_base)

    def parse_design_file(self, file_path: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Design document not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.parse_markdown(content)

    def parse_markdown(self, content: str) -> Dict[str, Any]:
        legacy = self._legacy_parser.parse_content(content)

        module_name = str(legacy.get("module_name") or "UnknownModule").strip() or "UnknownModule"
        purpose = str(legacy.get("purpose") or "").strip()
        spec = legacy.get("specification") or {}

        inputs = self._io_block_to_structured(spec.get("input"), "input")
        outputs = self._io_block_to_structured(spec.get("output"), "output")

        core_logic = spec.get("core_logic") or []
        data_sources: List[Dict[str, str]] = []
        steps: List[Dict[str, Any]] = []
        
        # First pass: Extract all data sources
        for raw in core_logic:
            normalized_raw = str(raw).strip()
            normalized_raw = self._strip_leading_numbering(normalized_raw)
                
            ds = self._extract_data_source_declaration(normalized_raw)
            if ds:
                if not any(existing.get("id") == ds["id"] for existing in data_sources):
                    data_sources.append(ds)

        # Second pass: Extract logic steps
        step_idx = 1
        for raw in core_logic:
            normalized_raw = str(raw).strip()
            normalized_raw = self._strip_leading_numbering(normalized_raw)

            if self._extract_data_source_declaration(normalized_raw):
                continue
            steps.append(self._logic_step_to_structured(step_idx, str(raw)))
            step_idx += 1

        # Resolve source_kind
        self._resolve_source_info(steps, data_sources)

        test_cases = legacy.get("test_cases") or []
        structured_cases = [self._test_case_to_structured(i + 1, tc) for i, tc in enumerate(test_cases)]

        result = {
            "module_name": module_name,
            "purpose": purpose,
            "inputs": inputs,
            "outputs": outputs,
            "steps": steps,
            "constraints": [],
            "test_cases": structured_cases,
            "data_sources": data_sources,
        }

        # DEBUG LOG
        self._logger.debug("Data Sources: %s", json.dumps(data_sources))
        for i, s in enumerate(steps):
            self._logger.debug("Step %s ID=%s SourceRef=%s", i + 1, s.get("id"), s.get("source_ref"))

        # Validate
        validate_structured_spec_or_raise(result)

        return result

    def _resolve_source_info(self, steps: List[Dict[str, Any]], data_sources: List[Dict[str, str]]) -> None:
        source_map = {ds["id"]: ds["kind"] for ds in data_sources}
        for step in steps:
            source_ref = step.get("source_ref")
            source_kind = step.get("source_kind")
            
            if source_ref and not source_kind:
                if source_ref in source_map:
                    step["source_kind"] = source_map[source_ref]
            
            # Default for FETCH if still missing
            if step["intent"] == "FETCH" and not step.get("source_kind"):
                step["source_kind"] = "file"

    def _io_to_structured(self, name: str, io_data: Dict[str, Any]) -> Dict[str, str]:
        def _strip_backticks(value: Any) -> str:
            if value is None:
                return ""
            text = str(value)
            return text.replace("`", "").strip()
        def _normalize_none(value: str) -> str:
            low = (value or "").strip().lower()
            if low in ["none", "void", "なし", "無し"]:
                return ""
            return value
        return {
            "name": str(io_data.get("name") or name),
            "description": _normalize_none(_strip_backticks(io_data.get("description") or "")),
            "type_format": _normalize_none(_strip_backticks(io_data.get("format") or "")),
            "example": _strip_backticks(io_data.get("example") or ""),
        }

    def _logic_step_to_structured(self, idx: int, text: str) -> Dict[str, Any]:
        kind = "ACTION"
        intent = "GENERAL"
        target_entity = "Item"
        output_type = "void"
        side_effect = "NONE"
        source_ref = None
        source_kind = None
        semantic_roles: Dict[str, str] = {}
        explicit_intent = False

        normalized_text = str(text).strip()
        # Strip numeric marker if present (e.g. "1. [ACTION]...")
        normalized_text = self._strip_leading_numbering(normalized_text)

        meta, normalized_text = self._extract_meta(normalized_text)
        if meta:
            explicit_intent = True
            kind = meta[0].upper()
            if kind in ["ELSE", "END"]:
                intent = "GENERAL"
                if len(meta) > 1: intent = meta[1]
            else:
                if len(meta) == 4 and kind in ["LOOP", "CONDITION"]:
                    kind = meta[0]
                    intent = "GENERAL"
                    target_entity = meta[1]
                    output_type = meta[2]
                    side_effect = meta[3]
                else:
                    kind = meta[0]
                    intent = meta[1]
                    target_entity = meta[2]
                    output_type = meta[3]
                    side_effect = meta[4]
                    if len(meta) >= 6 and meta[5]:
                        source_ref = meta[5].strip()
                    if len(meta) >= 7 and meta[6]:
                        source_kind = meta[6].strip()

        refs: List[str] = []
        ops: List[str] = []
        extracted_roles: Dict[str, Any] = {}
        scan_text = normalized_text
        while True:
            meta_raw, remainder = self._extract_bracket_prefix(scan_text)
            if not meta_raw:
                break
            lower = meta_raw.lower()
            if lower.startswith("refs:") or lower.startswith("depends:"):
                refs_raw = meta_raw.split(":", 1)[1]
                refs = [r.strip() for r in refs_raw.split(",") if r.strip()]
                scan_text = remainder
                continue
            if lower.startswith("ops:"):
                ops_raw = meta_raw.split(":", 1)[1]
                ops = [o.strip() for o in ops_raw.split(",") if o.strip()]
                scan_text = remainder
                continue
            if lower.startswith("semantic_roles:"):
                raw = meta_raw.split(":", 1)[1].strip()
                if raw:
                    try:
                        data = json.loads(raw)
                        if isinstance(data, dict):
                            extracted_roles.update(data)
                    except Exception:
                        pass
                scan_text = remainder
                continue
            break
        normalized_text = scan_text
        input_refs = refs if refs else ([f"step_{idx-1}"] if idx > 1 else [])

        # Parse semantic roles from text (heuristics for SQL, etc.)
        semantic_roles = {}
        if ops:
            semantic_roles["ops"] = ops
        if extracted_roles:
            semantic_roles.update(extracted_roles)
        # SQL parsing via keywords/regex is intentionally avoided.

        return {
            "id": f"step_{idx}",
            "kind": kind,
            "intent": intent,
            "target_entity": target_entity,
            "input_refs": input_refs,
            "output_type": output_type,
            "side_effect": side_effect,
            "text": normalized_text,
            "semantic_roles": semantic_roles,
            "explicit_intent": explicit_intent,
            "explicit_semantic_roles": bool(ops or extracted_roles),
            "depends_on": list(input_refs),
            **({"source_ref": source_ref} if source_ref else {}),
            **({"source_kind": source_kind} if source_kind else {}),
        }

    def _extract_meta(self, text: str) -> Tuple[List[str], str]:
        """
        Parse explicit metadata prefix:
        [KIND|INTENT|TARGET_ENTITY|OUTPUT_TYPE|SIDE_EFFECT|SOURCE_REF(optional)|SOURCE_KIND(optional)] remaining text
        """
        meta_raw, remainder = self._extract_bracket_prefix(text)
        if not meta_raw:
            return [], text
        parts = [p.strip() for p in meta_raw.split("|")]
        kind = parts[0].upper()
        if kind in ["ELSE", "END"]:
            # Special handling for simple blocks
            return parts, remainder
            
        if len(parts) not in [4, 5, 6, 7]:
            return [], text

        return parts, remainder

    def _extract_refs(self, text: str) -> Tuple[List[str], str]:
        """Parse optional refs prefix: [refs:step_1,step_2] ..."""
        meta_raw, remainder = self._extract_bracket_prefix(text)
        if not meta_raw:
            return [], text
        if not (meta_raw.lower().startswith("refs:") or meta_raw.lower().startswith("depends:")):
            return [], text
        refs_raw = meta_raw.split(":", 1)[1]
        refs = [r.strip() for r in refs_raw.split(",") if r.strip()]
        return refs, remainder

    def _extract_data_source_declaration(self, text: str) -> Dict[str, str]:
        """
        Parse data source declaration line:
        [data_source|source_xxx|db|http|file|memory] optional description
        """
        stripped = text.strip()
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        meta_raw, remainder = self._extract_bracket_prefix(stripped)
        if not meta_raw:
            return {}
        data = parse_data_source_tag(f"[{meta_raw}]", self._ALLOWED_SOURCE_KINDS)
        if not data:
            return {}
        desc = remainder.strip()
        if desc:
            data["description"] = desc
        return data

    def _io_block_to_structured(self, raw: Any, prefix: str) -> List[Dict[str, str]]:
        def _is_none_io(entry: Dict[str, Any]) -> bool:
            desc = str(entry.get("description") or "").strip().lower()
            fmt = str(entry.get("format") or "").strip().lower()
            return desc in ["none", "void", "なし", "無し", ""] and fmt in ["none", "void", "なし", "無し", ""]

        if isinstance(raw, list):
            entries = []
            for i, item in enumerate(raw, start=1):
                if not isinstance(item, dict):
                    continue
                if prefix == "input" and _is_none_io(item):
                    continue
                name = str(item.get("name") or f"{prefix}_{i}")
                entries.append(self._io_to_structured(name, item))
            return entries
        if isinstance(raw, dict) and prefix == "input" and _is_none_io(raw):
            return []
        return [self._io_to_structured(f"{prefix}_1", raw or {})]

    def _extract_ops(self, text: str) -> Tuple[List[str], str]:
        meta_raw, remainder = self._extract_bracket_prefix(text)
        if not meta_raw:
            return [], text
        if not meta_raw.lower().startswith("ops:"):
            return [], text
        ops_raw = meta_raw.split(":", 1)[1]
        ops = [o.strip() for o in ops_raw.split(",") if o.strip()]
        return ops, remainder

    def _extract_semantic_roles(self, text: str) -> Tuple[Dict[str, Any], str]:
        meta_raw, remainder = self._extract_bracket_prefix(text)
        if not meta_raw:
            return {}, text
        if not meta_raw.lower().startswith("semantic_roles:"):
            return {}, text
        raw = meta_raw.split(":", 1)[1].strip()
        if not raw:
            return {}, remainder
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data, remainder
        except Exception:
            return {}, text
        return {}, text

    def _test_case_to_structured(self, idx: int, tc: Dict[str, Any]) -> Dict[str, str]:
        return {
            "id": f"tc_{idx}",
            "type": str(tc.get("type") or "general"),
            "scenario": str(tc.get("scenario") or f"Scenario {idx}"),
            "input": str(tc.get("input") or ""),
            "expected": str(tc.get("expected") or ""),
        }

    def _extract_bracket_prefix(self, text: str) -> Tuple[str, str]:
        s = str(text).lstrip()
        if not s.startswith("["):
            return "", text
        end = s.find("]")
        if end == -1:
            return "", text
        meta = s[1:end].strip()
        remainder = s[end + 1:].strip()
        return meta, remainder

    def _strip_leading_numbering(self, text: str) -> str:
        s = str(text).strip()
        i = 0
        while i < len(s) and s[i].isdigit():
            i += 1
        if i > 0 and i < len(s) and s[i] == ".":
            if i + 1 < len(s) and s[i+1].isspace():
                return s[i+2:].strip()
        return s
