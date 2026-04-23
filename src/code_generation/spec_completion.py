# -*- coding: utf-8 -*-
"""Spec completion helpers."""
from __future__ import annotations


class SpecCompletionHelper:
    def __init__(self, owner) -> None:
        self.owner = owner

    def ensure_method_spec(self, specs: dict, full_name: str) -> dict:
        spec = specs.get(full_name)
        if not isinstance(spec, dict):
            spec = {}
        spec.setdefault("input", "")
        spec.setdefault("output", "")
        spec.setdefault("core_logic", [])
        spec.setdefault("steps", [])
        spec.setdefault("test_cases", [])
        spec.setdefault("_auto_completed", False)
        specs[full_name] = spec
        return spec

    def default_service_steps(self, method_kind: str) -> list:
        mapping = {
            "list": ["service.list"],
            "get": ["service.get"],
            "create": ["service.create"],
            "update": ["service.update"],
            "delete": ["service.delete"],
        }
        return mapping.get(method_kind, [])

    def default_repo_steps(self, method_kind: str) -> list:
        mapping = {
            "list": ["repo.fetch_all"],
            "get": ["repo.fetch_by_id"],
            "create": ["repo.insert"],
            "update": ["repo.update"],
            "delete": ["repo.delete"],
        }
        return mapping.get(method_kind, [])

    def build_default_service_core_logic(self, method_kind: str, entity_name: str, response_dto: str) -> list:
        if method_kind == "list":
            return [
                "Repository から全件取得する。",
                f"取得結果を `{response_dto}` に変換する。",
                "変換結果を返す（空なら空配列）。",
            ]
        if method_kind == "get":
            return [
                "Repository から id で取得する。",
                f"取得結果を `{response_dto}` に変換する。",
                "取得できない場合は null を返す。",
            ]
        if method_kind == "create":
            return [
                "入力が null の場合は null を返す。",
                f"入力DTOを {entity_name} に変換する。",
                "Repository に保存して結果を受け取る。",
                f"保存結果を `{response_dto}` に変換して返す。",
            ]
        if method_kind == "update":
            return [
                "入力が null の場合は null を返す。",
                f"Repository から対象{entity_name}を取得する。存在しない場合は null を返す。",
                f"取得した {entity_name} に更新内容を反映する。",
                "Repository で更新し、結果を変換して返す。",
            ]
        if method_kind == "delete":
            return [
                "Repository で削除を実行する。",
                "成功なら true、失敗なら false を返す。",
            ]
        return []

    def build_default_repo_core_logic(
        self,
        method_kind: str,
        entity_name: str,
        table_name: str,
        select_columns: list,
        insert_columns: list,
        update_columns: list,
    ) -> list:
        column_list = ", ".join(select_columns) if select_columns else "*"
        if method_kind == "list":
            return [
                f"`SELECT {column_list} FROM {table_name}` を実行する。",
                f"結果を `{entity_name}` のリストで返す。",
            ]
        if method_kind == "get":
            return [
                f"`SELECT {column_list} FROM {table_name} WHERE Id = @Id` を実行する。",
                "取得できない場合は null。",
            ]
        if method_kind == "create":
            insert_list = ", ".join(insert_columns)
            values_list = ", ".join([f"@{col}" for col in insert_columns])
            return [
                f"`INSERT INTO {table_name} ({insert_list}) VALUES ({values_list})` を実行する。",
                f"実行結果の Id を反映した {entity_name} を返す。",
            ]
        if method_kind == "update":
            assigns = ", ".join([f"{col}=@{col}" for col in update_columns])
            return [
                f"`UPDATE {table_name} SET {assigns} WHERE Id = @Id` を実行する。",
                "更新件数が0なら null。",
                f"更新成功なら Id を反映した {entity_name} を返す。",
            ]
        if method_kind == "delete":
            return [
                f"`DELETE FROM {table_name} WHERE Id = @Id` を実行する。",
                "削除件数が0なら false、成功なら true。",
            ]
        return []

    def complete_method_specs_for_generation(
        self,
        method_specs: dict,
        entity_specs: list,
        entities: list,
        crud_template: dict,
    ) -> dict:
        completed = dict(method_specs or {})

        def _existing_service_kinds(service_name: str) -> set:
            kinds = set()
            if not service_name:
                return kinds
            prefix = service_name + "."
            for name, spec in (completed or {}).items():
                if not name.startswith(prefix):
                    continue
                steps = spec.get("steps", []) or []
                for step in steps:
                    step_low = str(step).strip().lower()
                    if step_low.endswith("service.list") or step_low == "service.list":
                        kinds.add("list")
                    elif step_low.endswith("service.get") or step_low == "service.get":
                        kinds.add("get")
                    elif step_low.endswith("service.create") or step_low == "service.create":
                        kinds.add("create")
                    elif step_low.endswith("service.update") or step_low == "service.update":
                        kinds.add("update")
                    elif step_low.endswith("service.delete") or step_low == "service.delete":
                        kinds.add("delete")
            return kinds

        def _existing_repo_kinds(repo_name: str) -> set:
            kinds = set()
            if not repo_name:
                return kinds
            prefix = repo_name + "."
            for name, spec in (completed or {}).items():
                if not name.startswith(prefix):
                    continue
                steps = spec.get("steps", []) or []
                for step in steps:
                    step_low = str(step).strip().lower()
                    if step_low.endswith("repo.fetch_all") or step_low == "repo.fetch_all":
                        kinds.add("list")
                    elif step_low.endswith("repo.fetch_by_id") or step_low == "repo.fetch_by_id":
                        kinds.add("get")
                    elif step_low.endswith("repo.insert") or step_low == "repo.insert":
                        kinds.add("create")
                    elif step_low.endswith("repo.update") or step_low == "repo.update":
                        kinds.add("update")
                    elif step_low.endswith("repo.delete") or step_low == "repo.delete":
                        kinds.add("delete")
            return kinds

        entity_props_map = {e.get("name"): e.get("properties", []) for e in entities or []}
        for spec_item in entity_specs or []:
            entity_name = spec_item.get("name")
            entity_plural = spec_item.get("plural", f"{entity_name}s")
            create_dto = spec_item.get("create_dto")
            response_dto = spec_item.get("response_dto")
            service_name = spec_item.get("service")
            repo_name = spec_item.get("repository")
            crud_template_local = crud_template or {}
            list_service = crud_template_local.get("List", {}).get("Service", "Get{EntityPlural}")
            get_service = crud_template_local.get("GetById", {}).get("Service", "Get{Entity}ById")
            create_service = crud_template_local.get("Create", {}).get("Service", "Create{Entity}")
            update_service = crud_template_local.get("Update", {}).get("Service", "Update{Entity}")
            delete_service = crud_template_local.get("Delete", {}).get("Service", "Delete{Entity}")
            repo_list = crud_template_local.get("List", {}).get("Repository", "FetchAll")
            repo_get = crud_template_local.get("GetById", {}).get("Repository", "FetchById")
            repo_create = crud_template_local.get("Create", {}).get("Repository", "Insert")
            repo_update = crud_template_local.get("Update", {}).get("Repository", "Update")
            repo_delete = crud_template_local.get("Delete", {}).get("Repository", "Delete")
            list_service = self.owner._format_name(list_service, entity_name, entity_plural)
            get_service = self.owner._format_name(get_service, entity_name, entity_plural)
            create_service = self.owner._format_name(create_service, entity_name, entity_plural)
            update_service = self.owner._format_name(update_service, entity_name, entity_plural)
            delete_service = self.owner._format_name(delete_service, entity_name, entity_plural)

            if service_name:
                existing_kinds = _existing_service_kinds(service_name)
                service_methods = {
                    list_service: "list",
                    get_service: "get",
                    create_service: "create",
                    update_service: "update",
                    delete_service: "delete",
                }
                for method_name, kind in service_methods.items():
                    if kind in existing_kinds:
                        continue
                    full_name = f"{service_name}.{method_name}"
                    spec = self.ensure_method_spec(completed, full_name)
                    if not spec.get("steps"):
                        spec["steps"] = self.default_service_steps(kind)
                        spec["_auto_completed"] = True
                    if not spec.get("core_logic"):
                        spec["core_logic"] = self.build_default_service_core_logic(kind, entity_name, response_dto)
                        spec["_auto_completed"] = True
                    if not spec.get("test_cases"):
                        spec["test_cases"] = []

            if repo_name:
                existing_kinds = _existing_repo_kinds(repo_name)
                entity_props = entity_props_map.get(entity_name, [])
                entity_fields = [name for name, _ in self.owner._parse_props(entity_props)]
                select_columns = entity_fields if entity_fields else ["Id"]
                insert_fields = [name for name in entity_fields if name not in ["Id"]]
                update_fields = [name for name in insert_fields if name != "CreatedAt"]
                table_name = entity_plural
                repo_methods = {
                    repo_list: "list",
                    repo_get: "get",
                    repo_create: "create",
                    repo_update: "update",
                    repo_delete: "delete",
                }
                for method_name, kind in repo_methods.items():
                    if kind in existing_kinds:
                        continue
                    full_name = f"{repo_name}.{method_name}"
                    spec = self.ensure_method_spec(completed, full_name)
                    if not spec.get("steps"):
                        spec["steps"] = self.default_repo_steps(kind)
                        spec["_auto_completed"] = True
                    if not spec.get("core_logic"):
                        spec["core_logic"] = self.build_default_repo_core_logic(
                            kind,
                            entity_name,
                            table_name,
                            select_columns,
                            insert_fields,
                            update_fields,
                        )
                        spec["_auto_completed"] = True
                    if not spec.get("test_cases"):
                        spec["test_cases"] = []
        return completed
