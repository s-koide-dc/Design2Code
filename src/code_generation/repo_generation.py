# -*- coding: utf-8 -*-
"""Repository code generation helpers."""
from __future__ import annotations

from src.design_parser import StructuredDesignParser
from src.code_synthesis.synthesis_pipeline import synthesize_structured_spec


class RepoGenerationHelper:
    def __init__(self, owner) -> None:
        self.owner = owner

    def extract_sql_from_core(self, core_logic: list) -> str:
        parser = StructuredDesignParser()
        for line in core_logic or []:
            text = str(line)
            if not text:
                continue
            try:
                step = parser._logic_step_to_structured(1, text)
            except Exception:
                step = {}
            semantic_roles = step.get("semantic_roles") if isinstance(step, dict) else {}
            sql_text = semantic_roles.get("sql") if isinstance(semantic_roles, dict) else None
            if isinstance(sql_text, str) and sql_text.strip():
                return sql_text.strip()
            if "`" in text:
                start = text.find("`")
                end = text.rfind("`")
                if start != -1 and end != -1 and end > start:
                    return text[start + 1: end].strip()
        return ""

    def rewrite_repo_freeform_lines(
        self,
        body_lines: list,
        method_kind: str,
        param_name: str,
        id_name: str,
        sql_text: str,
        param_object_with_id: str,
    ) -> list:
        if not body_lines:
            return []
        if sql_text and method_kind == "update":
            return [
                f"var rows = _db.Execute(\"{sql_text}\", {param_object_with_id});",
                "if (rows == 0) return null;",
                f"{param_name}.Id = {id_name};",
                f"return {param_name};",
            ]
        if sql_text and method_kind == "delete":
            return [
                f"var rows = _db.Execute(\"{sql_text}\", new {{ Id = {id_name} }});",
                "if (rows >= 1) return true;",
                "if (rows == 0) return false;",
                "return false;",
            ]
        rewritten = []
        for line in body_lines:
            text = str(line)
            if "await" in text:
                if text.startswith("await "):
                    text = text[len("await "):]
                text = text.replace("= await ", "= ").replace(" await ", " ").replace("await ", "")
            text = text.replace(".QueryAsync", ".Query").replace(".ExecuteAsync", ".Execute")
            if method_kind in ["create", "update"]:
                if "input_1" in text:
                    text = text.replace("input_1", param_name)
                if "input_2" in text:
                    text = text.replace("input_2", id_name)
            elif method_kind in ["get", "delete"]:
                if "input_1" in text:
                    text = text.replace("input_1", id_name)
            rewritten.append(text)
        return rewritten

    def build_structured_spec_for_repo(
        self,
        method_name: str,
        method_spec: dict,
        entity_name: str,
        param_name: str,
        id_type: str,
        method_kind: str,
        param_object: str,
        param_object_with_id: str,
        init_object: str,
    ) -> dict:
        output_text = str(method_spec.get("output", "")).replace("`", "").strip()
        output_type = output_text.split()[0] if output_text else "void"
        core_logic = method_spec.get("core_logic", []) or []
        steps_hint = method_spec.get("steps", []) or []
        inferred_kind = self.infer_repo_kind_from_spec(steps_hint, core_logic, method_name, method_kind)
        method_kind = inferred_kind or method_kind
        sql = self.extract_sql_from_core(core_logic)
        inputs = []
        if method_kind in ["get", "delete", "update"]:
            inputs.append({"name": "id", "description": id_type, "type_format": id_type, "example": ""})
        if method_kind in ["create", "update"]:
            inputs.append({"name": param_name, "description": entity_name, "type_format": entity_name, "example": ""})
        steps = []

        def add_step(step_id: int, op: str, roles: dict) -> None:
            step = {
                "id": f"step_{step_id}",
                "kind": "ACTION",
                "intent": "ACTION",
                "target_entity": entity_name,
                "input_refs": [f"step_{step_id - 1}"] if step_id > 1 else [],
                "output_type": output_type,
                "side_effect": "DB",
                "text": f"ops:{op}",
                "semantic_roles": {
                    "ops": [op],
                    "scope": "repository",
                    "entity": entity_name,
                    "sql": sql,
                    "param_object": param_object,
                    "param_object_with_id": param_object_with_id,
                    "init_object": init_object,
                },
            }
            step["semantic_roles"].update(roles or {})
            steps.append(step)

        if method_kind == "list":
            add_step(1, "repo_fetch_all", {})
        elif method_kind == "get":
            add_step(1, "repo_fetch_by_id", {})
        elif method_kind == "create":
            add_step(1, "repo_insert", {"source_var": param_name})
        elif method_kind == "update":
            add_step(1, "repo_update", {"source_var": param_name})
        elif method_kind == "delete":
            add_step(1, "repo_delete", {})
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

    def infer_repo_kind_from_spec(
        self,
        steps_hint: list,
        core_logic: list,
        method_name: str,
        fallback_kind: str,
    ) -> str:
        for step in steps_hint:
            text = str(step).strip().lower()
            if text.endswith("repo.fetch_all") or text == "repo.fetch_all":
                return "list"
            if text.endswith("repo.fetch_by_id") or text == "repo.fetch_by_id":
                return "get"
            if text.endswith("repo.insert") or text == "repo.insert":
                return "create"
            if text.endswith("repo.update") or text == "repo.update":
                return "update"
            if text.endswith("repo.delete") or text == "repo.delete":
                return "delete"
        resolver = self.owner._get_ops_resolver()
        inferred_steps = resolver.infer_steps(core_logic, method_name)
        for step in inferred_steps:
            step_low = str(step).strip().lower()
            if step_low.endswith("repo.fetch_all") or step_low == "repo.fetch_all":
                return "list"
            if step_low.endswith("repo.fetch_by_id") or step_low == "repo.fetch_by_id":
                return "get"
            if step_low.endswith("repo.insert") or step_low == "repo.insert":
                return "create"
            if step_low.endswith("repo.update") or step_low == "repo.update":
                return "update"
            if step_low.endswith("repo.delete") or step_low == "repo.delete":
                return "delete"
        return fallback_kind

    def synthesize_repo_method_body(
        self,
        method_name: str,
        method_spec: dict,
        entity_name: str,
        param_name: str,
        id_type: str,
        method_kind: str,
        param_object: str,
        param_object_with_id: str,
        init_object: str,
    ) -> list:
        try:
            synthesizer = self.owner._get_synthesizer()
            sql_text = self.extract_sql_from_core(method_spec.get("core_logic", []) or [])
            if sql_text:
                if method_kind == "list":
                    return [
                        f"return _db.Query<{entity_name}>(\"{sql_text}\", null).AsList();",
                    ]
                if method_kind == "get":
                    return [
                        f"return _db.QuerySingleOrDefault<{entity_name}>(\"{sql_text}\", new {{ Id = id }});",
                    ]
                if method_kind == "create":
                    return [
                        f"_db.Execute(\"{sql_text}\", {param_object});",
                        f"return {param_name};",
                    ]
                if method_kind == "update":
                    return [
                        f"var rows = _db.Execute(\"{sql_text}\", {param_object_with_id});",
                        "if (rows == 0) return null;",
                        f"{param_name}.Id = id;",
                        f"return {param_name};",
                    ]
                if method_kind == "delete":
                    return [
                        f"var rows = _db.Execute(\"{sql_text}\", new {{ Id = id }});",
                        "if (rows >= 1) return true;",
                        "if (rows == 0) return false;",
                        "return false;",
                    ]
            output_text = str(method_spec.get("output", "")).replace("`", "").strip()
            output_type = output_text.split()[0] if output_text else "void"
            freeform = self.owner._spec_helpers.build_freeform_structured_spec(method_name, method_spec, output_type)
            if freeform:
                result = synthesize_structured_spec(
                    synthesizer,
                    freeform,
                    method_name,
                    return_trace=False,
                    allow_retry=False,
                )
                code = result.get("code") if isinstance(result, dict) else ""
                if code and "NotImplementedException" not in code:
                    body_lines = self.owner._extract_method_body_lines(code, method_name)
                    if body_lines:
                        cleaned = [line.replace("_dbConnection", "_db") for line in body_lines]
                        rewritten = self.rewrite_repo_freeform_lines(
                            cleaned,
                            method_kind=method_kind,
                            param_name=param_name,
                            id_name="id",
                            sql_text=sql_text,
                            param_object_with_id=param_object_with_id,
                        )
                        return self.owner._filter_synth_body_lines(rewritten)
            structured = self.build_structured_spec_for_repo(
                method_name,
                method_spec,
                entity_name,
                param_name,
                id_type,
                method_kind,
                param_object,
                param_object_with_id,
                init_object,
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
            code = result.get("code") if isinstance(result, dict) else ""
            if not code or "NotImplementedException" in code:
                return []
            body_lines = self.owner._extract_method_body_lines(code, method_name)
            if not body_lines:
                return []
            cleaned = [line.replace("_dbConnection", "_db") for line in body_lines]
            return self.owner._filter_synth_body_lines(cleaned)
        except Exception:
            return []

    def build_repo_method_bodies(
        self,
        method_specs: dict,
        repo_name: str,
        entity_name: str,
        entity_props: list,
        insert_fields: list,
        update_fields: list,
        param_name: str,
        id_type: str,
        step_templates: dict,
        repo_method_map: dict,
    ) -> dict:
        bodies = {}
        method_keys = {
            repo_method_map.get("list", "FetchAll"): "list",
            repo_method_map.get("get", "FetchById"): "get",
            repo_method_map.get("create", "Insert"): "create",
            repo_method_map.get("update", "Update"): "update",
            repo_method_map.get("delete", "Delete"): "delete",
        }
        entity_fields = {name for name, _ in self.owner._parse_props(entity_props)}
        insert_list = [f for f in insert_fields if f]
        update_list = [f for f in update_fields if f]
        if "CreatedAt" in entity_fields and "CreatedAt" not in insert_list:
            insert_list.append("CreatedAt")
        param_list_insert = ", ".join([f"{param_name}.{f}" for f in insert_list]) if insert_list else ""
        param_list_update = ", ".join([f"{param_name}.{f}" for f in update_list]) if update_list else ""
        init_list = ", ".join([f"{f} = {param_name}.{f}" for f in insert_list]) if insert_list else ""
        for name, spec in (method_specs or {}).items():
            if not name.startswith(repo_name + "."):
                continue
            method = name.split(".", 1)[1]
            core = spec.get("core_logic", [])
            sql = self.extract_sql_from_core(core)
            method_kind = method_keys.get(method, "")
            if not sql:
                raise RuntimeError(f"Repository synth requires SQL in core_logic: {repo_name}.{method}")
            sql_for_synth = sql
            if method_kind == "update" and "UpdatedAt" in update_list:
                if "updatedat" not in sql.lower() and spec.get("_auto_completed"):
                    lower_sql = sql.lower()
                    where_idx = lower_sql.rfind(" where ")
                    if where_idx != -1:
                        sql_for_synth = sql[:where_idx] + ", UpdatedAt=@UpdatedAt" + sql[where_idx:]
            spec_for_synth = spec
            if sql_for_synth != sql:
                spec_for_synth = dict(spec)
                spec_for_synth["core_logic"] = [
                    line.replace(sql, sql_for_synth) if isinstance(line, str) and sql in line else line
                    for line in core
                ]
            synth_body = self.synthesize_repo_method_body(
                method,
                spec_for_synth,
                entity_name,
                param_name,
                id_type,
                method_kind,
                "new { " + param_list_insert + " }" if param_list_insert else "new { }",
                "new { Id = id, " + param_list_update + " }" if param_list_update else "new { Id = id }",
                (", " + init_list) if init_list else "",
            )
            if not synth_body:
                raise RuntimeError(f"Repository synth failed: {repo_name}.{method}")
            bodies[method] = synth_body
        return bodies
