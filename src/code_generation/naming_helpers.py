# -*- coding: utf-8 -*-
"""Naming, typing, and mapping helpers."""
from __future__ import annotations

import copy

class NamingHelpers:
    def __init__(self, owner) -> None:
        self.owner = owner

    def map_type(self, t: str) -> str:
        t_low = str(t).strip().lower()
        if t_low in ["int", "int32"]:
            return "int"
        if t_low in ["long", "int64"]:
            return "long"
        if t_low in ["bool", "boolean"]:
            return "bool"
        if t_low in ["decimal", "money"]:
            return "decimal"
        if t_low in ["datetime", "date"]:
            return "DateTime"
        return "string"

    def parse_props(self, lines: list) -> list:
        props = []
        for line in lines or []:
            parts = [p.strip() for p in line.split(",") if p.strip()]
            for p in parts:
                if ":" in p:
                    name, p_type = [x.strip() for x in p.split(":", 1)]
                    props.append((name, self.map_type(p_type)))
        return props

    def build_default_mapping(self, source_props: list, target_props: list) -> list:
        mapping = []
        source_names = {name for name, _ in source_props or []}
        for name, _ in target_props or []:
            if name in source_names:
                mapping.append({"from": name, "to": name})
        return mapping

    def resolve_dto_mapping(
        self,
        create_mapping: list,
        response_mapping: list,
        create_dto_props: list,
        response_dto_props: list,
        entity_props: list,
    ) -> dict:
        create_dto_fields = self.parse_props(create_dto_props)
        response_dto_fields = self.parse_props(response_dto_props)
        entity_fields = self.parse_props(entity_props)
        if not create_mapping:
            create_mapping = self.build_default_mapping(create_dto_fields, entity_fields)
        if not response_mapping:
            response_mapping = self.build_default_mapping(entity_fields, response_dto_fields)
        return {
            "create_to_entity": create_mapping,
            "entity_to_response": response_mapping,
        }

    def extract_type_token(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        raw = text.strip()
        if raw.startswith("`") and raw.endswith("`") and len(raw) >= 2:
            raw = raw[1:-1].strip()
        token_chars = []
        for ch in raw:
            if ch.isalnum() or ch in "<>_.,?[]":
                token_chars.append(ch)
                continue
            break
        return "".join(token_chars)

    def infer_return_type_from_output(self, output_text: str, default_type: str) -> str:
        output_raw = str(output_text or "")
        type_token = self.extract_type_token(output_raw)
        ret_type = type_token if type_token else default_type
        output_low = output_raw.lower()
        if "?" not in ret_type and ("?" in output_raw or "null" in output_low):
            ret_type = ret_type + "?"
        return ret_type

    def apply_nullable_hint(self, signature: str, default_type: str) -> str:
        text = str(signature or "")
        if ":" not in text:
            return default_type
        ret = text.rsplit(":", 1)[1].strip()
        if not ret:
            return default_type
        token = self.extract_type_token(ret)
        return token if token else default_type

    def infer_nullable_return(self, method_specs: dict, key: str, default_type: str) -> str:
        if not method_specs or key not in method_specs:
            return default_type
        output_text = method_specs.get(key, {}).get("output", "")
        return self.infer_return_type_from_output(output_text, default_type)

    def build_module_method_return_map(self, modules: list) -> dict:
        result = {}
        for mod in modules or []:
            name = mod.get("name")
            if not name:
                continue
            for method in mod.get("methods", []) or []:
                if not isinstance(method, str) or "(" not in method or ":" not in method:
                    continue
                method_name = method.split("(", 1)[0].strip()
                if not method_name:
                    continue
                full = f"{name}.{method_name}"
                result[full] = method
        return result

    def infer_id_type(self, entity_name: str, entities: list, hints_entities: dict) -> str:
        for e in entities or []:
            if e.get("name") != entity_name:
                continue
            for prop, p_type in self.parse_props(e.get("properties")):
                if prop.lower() == "id":
                    return p_type
        primary = hints_entities.get("Primary Key", "")
        if ":" in primary:
            _, p_type = [p.strip() for p in primary.split(":", 1)]
            return self.map_type(p_type)
        return "int"

    def map_target_framework(self, target: str) -> str:
        text = str(target or "").strip().lower()
        if text.startswith("net"):
            text = text[3:]
        if "net" in text:
            text = text.replace(".net", "").replace("net", "")
        digits = "".join([c for c in text if c.isdigit() or c == "."])
        if not digits:
            return "net8.0"
        major = digits.split(".")[0]
        if not major:
            return "net8.0"
        return f"net{major}.0"

    def format_name(self, template: str, entity: str, entity_plural: str) -> str:
        return template.replace("{Entity}", entity).replace("{EntityPlural}", entity_plural)

    def to_camel(self, name: str) -> str:
        if not name:
            return "entity"
        return name[0].lower() + name[1:]

    def build_service_method_name_map(self, service_name: str, method_specs: dict) -> dict:
        name_map = {}
        if not service_name or not method_specs:
            return name_map
        prefix = service_name + "."
        for full_name, spec in method_specs.items():
            if not full_name.startswith(prefix):
                continue
            method_name = full_name.split(".", 1)[1]
            steps = spec.get("steps", []) or []
            for step in steps:
                step_low = str(step).strip().lower()
                if step_low == "service.list":
                    name_map["list"] = method_name
                elif step_low == "service.get":
                    name_map["get"] = method_name
                elif step_low == "service.create":
                    name_map["create"] = method_name
                elif step_low == "service.update":
                    name_map["update"] = method_name
                elif step_low == "service.delete":
                    name_map["delete"] = method_name
        return name_map

    def build_repo_method_name_map(self, repo_name: str, method_specs: dict) -> dict:
        name_map = {}
        if not repo_name or not method_specs:
            return name_map
        prefix = repo_name + "."
        for full_name, spec in method_specs.items():
            if not full_name.startswith(prefix):
                continue
            method_name = full_name.split(".", 1)[1]
            steps = spec.get("steps", []) or []
            for step in steps:
                step_low = str(step).strip().lower()
                if step_low == "repo.fetch_all":
                    name_map["list"] = method_name
                elif step_low == "repo.fetch_by_id":
                    name_map["get"] = method_name
                elif step_low == "repo.insert":
                    name_map["create"] = method_name
                elif step_low == "repo.update":
                    name_map["update"] = method_name
                elif step_low == "repo.delete":
                    name_map["delete"] = method_name
        return name_map

    def build_crud_template_override(self, crud_template: dict, service_name_map: dict, repo_name_map: dict) -> dict:
        template = copy.deepcopy(crud_template) if crud_template else {}

        def _set(section: str, key: str, value: str | None) -> None:
            if not value:
                return
            template.setdefault(section, {})[key] = value

        _set("List", "Service", service_name_map.get("list"))
        _set("GetById", "Service", service_name_map.get("get"))
        _set("Create", "Service", service_name_map.get("create"))
        _set("Update", "Service", service_name_map.get("update"))
        _set("Delete", "Service", service_name_map.get("delete"))
        _set("List", "Repository", repo_name_map.get("list"))
        _set("GetById", "Repository", repo_name_map.get("get"))
        _set("Create", "Repository", repo_name_map.get("create"))
        _set("Update", "Repository", repo_name_map.get("update"))
        _set("Delete", "Repository", repo_name_map.get("delete"))
        return template

    def infer_route_base(self, routes: list, default_base: str) -> str:
        candidates = []
        for route in routes or []:
            if not isinstance(route, str):
                continue
            parts = route.split(" ", 1)
            path = parts[1] if len(parts) > 1 else parts[0]
            path = path.strip()
            if path.startswith("/"):
                path = path[1:]
            if not path:
                continue
            first = path.split("/", 1)[0]
            if not first or first == "{id}":
                continue
            candidates.append(first)
        if candidates and all(c == candidates[0] for c in candidates):
            return candidates[0]
        return default_base
