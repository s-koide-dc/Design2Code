# -*- coding: utf-8 -*-
"""Controller code generation helpers."""
from __future__ import annotations

from src.code_synthesis.synthesis_pipeline import synthesize_structured_spec


class ControllerGenerationHelper:
    def __init__(self, owner) -> None:
        self.owner = owner

    def build_structured_spec_for_controller(
        self,
        action_name: str,
        action_kind: str,
        service_call: str,
        create_dto: str,
        id_type: str,
    ) -> dict:
        inputs = []
        if action_kind in ["get", "update", "delete"]:
            inputs.append({"name": "id", "description": id_type, "type_format": id_type, "example": ""})
        if action_kind in ["create", "update"]:
            inputs.append({"name": "req", "description": create_dto, "type_format": create_dto, "example": ""})
        op_map = {
            "list": "controller_list",
            "get": "controller_get",
            "create": "controller_create",
            "update": "controller_update",
            "delete": "controller_delete",
        }
        op = op_map.get(action_kind)
        if not op:
            return {}
        steps = [{
            "id": "step_1",
            "kind": "ACTION",
            "intent": "ACTION",
            "target_entity": "Controller",
            "input_refs": [],
            "output_type": "IActionResult",
            "side_effect": "IO",
            "text": f"ops:{op}",
            "semantic_roles": {
                "ops": [op],
                "service_call": service_call,
                "create_dto": create_dto,
            },
        }]
        return {
            "module_name": action_name,
            "purpose": "Auto-generated for synthesis.",
            "inputs": inputs,
            "outputs": [{"name": "output_1", "description": "IActionResult", "type_format": "IActionResult", "example": ""}],
            "steps": steps,
            "constraints": [],
            "test_cases": [],
            "data_sources": [],
        }

    def synthesize_controller_action_body(
        self,
        action_name: str,
        action_kind: str,
        service_call: str,
        create_dto: str,
        id_type: str,
    ) -> list:
        try:
            synthesizer = self.owner._get_synthesizer()
            structured = self.build_structured_spec_for_controller(action_name, action_kind, service_call, create_dto, id_type)
            if not structured:
                return []
            result = synthesize_structured_spec(
                synthesizer,
                structured,
                action_name,
                return_trace=False,
                allow_retry=False,
            )
            code = result.get("code") if isinstance(result, dict) else ""
            if not code or "NotImplementedException" in code:
                return []
            body_lines = self.owner._extract_method_body_lines(code, action_name)
            if not body_lines:
                return []
            return self.owner._filter_synth_body_lines(body_lines)
        except Exception:
            return []
