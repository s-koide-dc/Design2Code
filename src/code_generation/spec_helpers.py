# -*- coding: utf-8 -*-
"""Spec parsing helpers."""
from __future__ import annotations

from src.design_parser import StructuredDesignParser


class SpecHelpers:
    def __init__(self, owner) -> None:
        self.owner = owner

    def parse_input_defs_from_text(self, input_text: str) -> list:
        inputs = []
        if not input_text:
            return inputs
        parts = [p.strip() for p in str(input_text).split(",") if p.strip()]
        for idx, part in enumerate(parts, start=1):
            name = f"input_{idx}"
            typ = "object"
            if ":" in part:
                left, right = [x.strip() for x in part.split(":", 1)]
                if left and right:
                    name = left
                    typ = right
            else:
                tokens = [t for t in part.split(" ") if t]
                if len(tokens) >= 2:
                    typ = tokens[0]
                    name = tokens[-1]
            inputs.append({"name": name, "description": typ, "type_format": typ, "example": ""})
        return inputs

    def build_freeform_structured_spec(self, method_name: str, method_spec: dict, output_type: str) -> dict:
        core_logic = method_spec.get("core_logic", []) or []
        if not core_logic:
            return {}
        parser = StructuredDesignParser()
        data_sources = []
        steps = []
        for raw in core_logic:
            normalized = parser._strip_leading_numbering(str(raw).strip())
            if not normalized:
                continue
            ds = parser._extract_data_source_declaration(normalized)
            if ds:
                if not any(existing.get("id") == ds.get("id") for existing in data_sources):
                    data_sources.append(ds)
                continue
            steps.append(parser._logic_step_to_structured(len(steps) + 1, str(raw)))
        if not steps:
            return {}
        # Require explicit intent or semantic roles for each step to avoid heuristic synthesis.
        for step in steps:
            if not (step.get("explicit_intent") or step.get("explicit_semantic_roles")):
                return {}
        parser._resolve_source_info(steps, data_sources)
        input_text = str(method_spec.get("input", "") or "")
        inputs = self.parse_input_defs_from_text(input_text)
        structured = {
            "module_name": method_name,
            "purpose": "Auto-generated for synthesis.",
            "inputs": inputs,
            "outputs": [{"name": "output_1", "description": output_type, "type_format": output_type, "example": ""}],
            "steps": steps,
            "constraints": [],
            "test_cases": [],
            "data_sources": data_sources,
        }
        return structured
