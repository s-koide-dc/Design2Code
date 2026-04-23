# -*- coding: utf-8 -*-
"""Service code generation helpers."""
from __future__ import annotations

from src.code_synthesis.synthesis_pipeline import synthesize_structured_spec
from src.design_parser import StructuredDesignParser


class ServiceGenerationHelper:
    def __init__(self, owner) -> None:
        self.owner = owner

    def infer_service_kind_from_spec(
        self,
        steps_hint: list,
        core_logic: list,
        method_name: str,
        fallback_kind: str,
        input_text: str,
        create_dto: str,
    ) -> str:
        input_low = str(input_text).lower()
        create_low = str(create_dto).lower()
        has_id = "id" in input_low
        has_req = "req" in input_low or (create_low and create_low in input_low)

        def _compatible(kind: str) -> bool:
            if kind in ["get", "update", "delete"] and not has_id:
                return False
            if kind in ["create", "update"] and not has_req:
                return False
            if kind == "list" and has_id:
                return False
            return True

        for step in steps_hint:
            text = str(step).strip().lower()
            if text.endswith("service.list") or text == "service.list":
                return "list" if _compatible("list") else fallback_kind
            if text.endswith("service.get") or text == "service.get":
                return "get" if _compatible("get") else fallback_kind
            if text.endswith("service.create") or text == "service.create":
                return "create" if _compatible("create") else fallback_kind
            if text.endswith("service.update") or text == "service.update":
                return "update" if _compatible("update") else fallback_kind
            if text.endswith("service.delete") or text == "service.delete":
                return "delete" if _compatible("delete") else fallback_kind
        resolver = self.owner._get_ops_resolver()
        inferred_steps = resolver.infer_service_steps(core_logic, method_name, fallback_kind)
        for step in inferred_steps:
            step_low = str(step).strip().lower()
            if step_low.endswith("service.list") or step_low == "service.list":
                return "list" if _compatible("list") else fallback_kind
            if step_low.endswith("service.get") or step_low == "service.get":
                return "get" if _compatible("get") else fallback_kind
            if step_low.endswith("service.create") or step_low == "service.create":
                return "create" if _compatible("create") else fallback_kind
            if step_low.endswith("service.update") or step_low == "service.update":
                return "update" if _compatible("update") else fallback_kind
            if step_low.endswith("service.delete") or step_low == "service.delete":
                return "delete" if _compatible("delete") else fallback_kind
        return fallback_kind

    def build_structured_spec_for_service(
        self,
        method_name: str,
        method_kind: str,
        method_spec: dict,
        entity_name: str,
        response_dto: str,
        create_dto: str,
        id_type: str,
        repo_methods: dict,
        validation_guards: list,
        update_assignments: list,
        timestamp_assignment: str,
    ) -> dict:
        core_logic = method_spec.get("core_logic", []) or []
        steps_hint = method_spec.get("steps", []) or []
        input_text = str(method_spec.get("input", "") or "")
        inferred_kind = self.infer_service_kind_from_spec(
            steps_hint,
            core_logic,
            method_name,
            method_kind,
            input_text,
            create_dto,
        )
        method_kind = inferred_kind or method_kind
        output_type = response_dto
        if method_kind == "list":
            output_type = f"List<{response_dto}>"
        elif method_kind == "delete":
            output_type = "bool"
        output_type = self.owner._infer_return_type_from_output(method_spec.get("output", ""), output_type)
        inputs = []
        if method_kind in ["get", "update", "delete"]:
            inputs.append({"name": "id", "description": id_type, "type_format": id_type, "example": ""})
        if method_kind in ["create", "update"]:
            inputs.append({"name": "req", "description": create_dto, "type_format": create_dto, "example": ""})
        steps = []

        def add_step(step_id: int, op: str, roles: dict) -> None:
            step = {
                "id": f"step_{step_id}",
                "kind": "ACTION",
                "intent": "ACTION",
                "target_entity": entity_name,
                "input_refs": [f"step_{step_id - 1}"] if step_id > 1 else [],
                "output_type": "void",
                "side_effect": "NONE",
                "text": f"ops:{op}",
                "semantic_roles": {
                    "ops": [op],
                    "entity": entity_name,
                    "response_dto": response_dto,
                },
            }
            step["semantic_roles"].update(roles or {})
            steps.append(step)

        repo_list = repo_methods.get("list", "FetchAll")
        repo_get = repo_methods.get("get", "FetchById")
        repo_create = repo_methods.get("create", "Insert")
        repo_update = repo_methods.get("update", "Update")
        repo_delete = repo_methods.get("delete", "Delete")
        step_id = 1
        if method_kind == "list":
            add_step(step_id, "repo_fetch_all", {"repo_method": repo_list, "result_var": "items"})
            step_id += 1
            add_step(step_id, "to_response", {"collection": True, "source_var": "items"})
        elif method_kind == "get":
            add_step(step_id, "repo_fetch_by_id", {"repo_method": repo_get, "result_var": "item"})
            step_id += 1
            add_step(step_id, "to_response", {"collection": False, "source_var": "item"})
        elif method_kind == "create":
            add_step(step_id, "null_guard", {"guard_var": "req", "return_value": "null"})
            step_id += 1
            add_step(step_id, "validation_guards", {"guards": validation_guards})
            step_id += 1
            add_step(step_id, "to_entity", {"result_var": "entity"})
            step_id += 1
            add_step(step_id, "repo_insert", {"repo_method": repo_create, "source_var": "entity", "result_var": "created"})
            step_id += 1
            add_step(step_id, "to_response", {"collection": False, "source_var": "created"})
        elif method_kind == "update":
            add_step(step_id, "null_guard", {"guard_var": "req", "return_value": "null"})
            step_id += 1
            add_step(step_id, "validation_guards", {"guards": validation_guards})
            step_id += 1
            add_step(step_id, "repo_fetch_by_id", {"repo_method": repo_get, "result_var": "existing"})
            step_id += 1
            add_step(step_id, "null_guard", {"guard_var": "existing", "return_value": "null"})
            step_id += 1
            add_step(step_id, "update_fields", {"target_var": "existing", "update_assignments": update_assignments})
            step_id += 1
            add_step(step_id, "repo_update", {"repo_method": repo_update, "source_var": "existing", "result_var": "updated"})
            step_id += 1
            add_step(step_id, "null_guard", {"guard_var": "updated", "return_value": "null"})
            step_id += 1
            if timestamp_assignment:
                add_step(step_id, "timestamp_assignment", {"timestamp_assignment": timestamp_assignment})
                step_id += 1
            add_step(step_id, "to_response", {"collection": False, "source_var": "updated"})
        elif method_kind == "delete":
            add_step(step_id, "repo_delete", {"repo_method": repo_delete})
        else:
            return {}
        structured = {
            "module_name": method_name,
            "purpose": "Auto-generated for synthesis.",
            "inputs": inputs,
            "outputs": [{"name": "output_1", "description": output_type, "type_format": output_type, "example": ""}],
            "steps": steps,
            "constraints": [],
            "test_cases": [],
            "data_sources": [],
        }
        return structured

    def build_structured_spec_from_explicit_service_steps(
        self,
        method_name: str,
        method_kind: str,
        method_spec: dict,
        entity_name: str,
        response_dto: str,
        create_dto: str,
        id_type: str,
        repo_methods: dict,
        validation_guards: list,
        update_assignments: list,
        timestamp_assignment: str,
    ) -> dict:
        core_logic = method_spec.get("core_logic", []) or []
        if not core_logic:
            return {}
        parser = StructuredDesignParser()
        steps = []
        for raw in core_logic:
            normalized = parser._strip_leading_numbering(str(raw).strip())
            if not normalized:
                continue
            if parser._extract_data_source_declaration(normalized):
                continue
            steps.append(parser._logic_step_to_structured(len(steps) + 1, str(raw)))
        if not steps:
            return {}
        if any(not (s.get("explicit_intent") or s.get("explicit_semantic_roles")) for s in steps):
            return {}
        intents = [str(s.get("intent") or "").upper() for s in steps]
        targets = [str(s.get("target_entity") or "") for s in steps]
        has_validate = "VALIDATE" in intents
        has_fetch = "FETCH" in intents
        has_persist = "PERSIST" in intents
        has_transform_entity = any(i == "TRANSFORM" and t == entity_name for i, t in zip(intents, targets))
        has_transform_response = any(
            (i in ["TRANSFORM", "RETURN"]) and t == response_dto for i, t in zip(intents, targets)
        )
        output_type = response_dto
        if method_kind == "list":
            output_type = f"List<{response_dto}>"
        elif method_kind == "delete":
            output_type = "bool"
        output_type = self.owner._infer_return_type_from_output(method_spec.get("output", ""), output_type)
        inputs = []
        if method_kind in ["get", "update", "delete"]:
            inputs.append({"name": "id", "description": id_type, "type_format": id_type, "example": ""})
        if method_kind in ["create", "update"]:
            inputs.append({"name": "req", "description": create_dto, "type_format": create_dto, "example": ""})
        steps_out = []

        def add_step(step_id: int, op: str, roles: dict) -> None:
            step = {
                "id": f"step_{step_id}",
                "kind": "ACTION",
                "intent": "ACTION",
                "target_entity": entity_name,
                "input_refs": [f"step_{step_id - 1}"] if step_id > 1 else [],
                "output_type": "void",
                "side_effect": "NONE",
                "text": f"ops:{op}",
                "semantic_roles": {
                    "ops": [op],
                    "entity": entity_name,
                    "response_dto": response_dto,
                },
            }
            step["semantic_roles"].update(roles or {})
            steps_out.append(step)

        repo_list = repo_methods.get("list", "FetchAll")
        repo_get = repo_methods.get("get", "FetchById")
        repo_create = repo_methods.get("create", "Insert")
        repo_update = repo_methods.get("update", "Update")
        repo_delete = repo_methods.get("delete", "Delete")
        step_id = 1
        if method_kind == "list":
            if not (has_fetch and has_transform_response):
                return {}
            add_step(step_id, "repo_fetch_all", {"repo_method": repo_list, "result_var": "items"})
            step_id += 1
            add_step(step_id, "to_response", {"collection": True, "source_var": "items"})
        elif method_kind == "get":
            if not (has_fetch and has_transform_response):
                return {}
            add_step(step_id, "repo_fetch_by_id", {"repo_method": repo_get, "result_var": "item"})
            step_id += 1
            add_step(step_id, "to_response", {"collection": False, "source_var": "item"})
        elif method_kind == "create":
            if not (has_transform_entity and has_persist and has_transform_response):
                return {}
            if has_validate:
                add_step(step_id, "null_guard", {"guard_var": "req", "return_value": "null"})
                step_id += 1
                add_step(step_id, "validation_guards", {"guards": validation_guards})
                step_id += 1
            add_step(step_id, "to_entity", {"result_var": "entity"})
            step_id += 1
            add_step(step_id, "repo_insert", {"repo_method": repo_create, "source_var": "entity", "result_var": "created"})
            step_id += 1
            add_step(step_id, "to_response", {"collection": False, "source_var": "created"})
        elif method_kind == "update":
            if not (has_fetch and has_transform_entity and has_persist and has_transform_response):
                return {}
            if has_validate:
                add_step(step_id, "null_guard", {"guard_var": "req", "return_value": "null"})
                step_id += 1
                add_step(step_id, "validation_guards", {"guards": validation_guards})
                step_id += 1
            add_step(step_id, "repo_fetch_by_id", {"repo_method": repo_get, "result_var": "existing"})
            step_id += 1
            add_step(step_id, "null_guard", {"guard_var": "existing", "return_value": "null"})
            step_id += 1
            add_step(step_id, "update_fields", {"target_var": "existing", "update_assignments": update_assignments})
            step_id += 1
            add_step(step_id, "repo_update", {"repo_method": repo_update, "source_var": "existing", "result_var": "updated"})
            step_id += 1
            add_step(step_id, "null_guard", {"guard_var": "updated", "return_value": "null"})
            step_id += 1
            if timestamp_assignment:
                add_step(step_id, "timestamp_assignment", {"timestamp_assignment": timestamp_assignment})
                step_id += 1
            add_step(step_id, "to_response", {"collection": False, "source_var": "updated"})
        elif method_kind == "delete":
            if not has_persist:
                return {}
            add_step(step_id, "repo_delete", {"repo_method": repo_delete})
        else:
            return {}
        return {
            "module_name": method_name,
            "purpose": "Auto-generated for synthesis.",
            "inputs": inputs,
            "outputs": [{"name": "output_1", "description": output_type, "type_format": output_type, "example": ""}],
            "steps": steps_out,
            "constraints": [],
            "test_cases": [],
            "data_sources": [],
        }

    def synthesize_service_method_body(
        self,
        method_name: str,
        method_kind: str,
        method_spec: dict,
        entity_name: str,
        response_dto: str,
        create_dto: str,
        id_type: str,
        repo_methods: dict,
        validation_guards: list,
        update_assignments: list,
        timestamp_assignment: str,
    ) -> list:
        try:
            synthesizer = self.owner._get_synthesizer()
            output_type = response_dto
            if method_kind == "list":
                output_type = f"List<{response_dto}>"
            elif method_kind == "delete":
                output_type = "bool"
            output_type = self.owner._infer_return_type_from_output(method_spec.get("output", ""), output_type)
            if self.owner._allow_service_freeform:
                structured_explicit = self.build_structured_spec_from_explicit_service_steps(
                    method_name,
                    method_kind,
                    method_spec,
                    entity_name,
                    response_dto,
                    create_dto,
                    id_type,
                    repo_methods,
                    validation_guards,
                    update_assignments,
                    timestamp_assignment,
                )
                if structured_explicit:
                    result = synthesize_structured_spec(
                        synthesizer,
                        structured_explicit,
                        method_name,
                        return_trace=False,
                        allow_retry=False,
                    )
                    code = result.get("code") if isinstance(result, dict) else ""
                    if code and "NotImplementedException" not in code:
                        body_lines = self.owner._extract_method_body_lines(code, method_name)
                        if body_lines:
                            return self.owner._filter_synth_body_lines(body_lines)
            structured = self.build_structured_spec_for_service(
                method_name,
                method_kind,
                method_spec,
                entity_name,
                response_dto,
                create_dto,
                id_type,
                repo_methods,
                validation_guards,
                update_assignments,
                timestamp_assignment,
            )
            if not structured:
                return []
            result = synthesize_structured_spec(
                synthesizer,
                structured,
                method_name,
                return_trace=False,
                allow_retry=False,
            )
            if isinstance(result, dict) and result.get("status") == "FAILED":
                print(f"[!] Service synth failed: {method_name}")
                errs = result.get("errors") or []
                if errs:
                    for err in errs:
                        print(f"    - {err}")
            code = result.get("code") if isinstance(result, dict) else ""
            if not code or "NotImplementedException" in code:
                return []
            body_lines = self.owner._extract_method_body_lines(code, method_name)
            if not body_lines:
                return []
            return self.owner._filter_synth_body_lines(body_lines)
        except Exception as e:
            print(f"[!] Service synth exception: {method_name}: {e}")
            return []

    def build_service_method_bodies(
        self,
        method_specs: dict,
        service_name: str,
        method_name_map: dict,
        repo_method_map: dict,
        response_dto: str,
        create_dto: str,
        dto_mapping: dict,
        validation_rules: dict,
        field_types: dict,
        validation_templates: dict,
        step_templates: dict,
        entity_name: str,
        id_type: str,
        entity_props: list,
    ) -> dict:
        bodies = {}
        create_mappings = dto_mapping.get("create_to_entity", [])
        update_assignments = []
        for mapping in create_mappings:
            src = mapping.get("from")
            dest = mapping.get("to")
            if not src or not dest:
                continue
            if src.lower() == "utcnow":
                continue
            src_type = field_types.get(src, "string")
            suffix = "!" if src_type == "string" else ""
            update_assignments.append(f"existing.{dest} = req.{src}{suffix};")
        entity_fields = {name for name, _ in self.owner._parse_props(entity_props)}
        if "UpdatedAt" in entity_fields:
            update_assignments.append("existing.UpdatedAt = DateTime.UtcNow;")
        validation_guards = self.owner._build_validation_guards(create_dto, "req", validation_rules, field_types, validation_templates)
        list_name = method_name_map.get("list", "GetItems")
        get_name = method_name_map.get("get", "GetItemById")
        create_name = method_name_map.get("create", "CreateItem")
        update_name = method_name_map.get("update", "UpdateItem")
        delete_name = method_name_map.get("delete", "DeleteItem")
        repo_list = repo_method_map.get("list", "FetchAll")
        repo_get = repo_method_map.get("get", "FetchById")
        repo_create = repo_method_map.get("create", "Insert")
        repo_update = repo_method_map.get("update", "Update")
        repo_delete = repo_method_map.get("delete", "Delete")
        method_keys = {
            list_name: "list",
            get_name: "get",
            create_name: "create",
            update_name: "update",
            delete_name: "delete",
        }
        for method_name, op_key in method_keys.items():
            spec_key = f"{service_name}.{method_name}"
            spec = method_specs.get(spec_key, {}) or {}
            timestamp_assignment = ""
            if "CreatedAt" in entity_fields:
                timestamp_assignment = "updated.CreatedAt = existing.CreatedAt;"
            elif "UpdatedAt" in entity_fields:
                timestamp_assignment = "updated.UpdatedAt = existing.UpdatedAt;"
            synth_body = self.synthesize_service_method_body(
                method_name=method_name,
                method_kind=op_key,
                method_spec=spec,
                entity_name=entity_name,
                response_dto=response_dto,
                create_dto=create_dto,
                id_type=id_type,
                repo_methods=repo_method_map,
                validation_guards=validation_guards,
                update_assignments=update_assignments,
                timestamp_assignment=timestamp_assignment,
            )
            if not synth_body:
                raise RuntimeError(f"Service synth failed: {service_name}.{method_name}")
            bodies[method_name] = synth_body
        return bodies
