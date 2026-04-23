# -*- coding: utf-8 -*-
"""Project generator for multi-file C# projects from Project Specs."""
from __future__ import annotations

import os

from src.code_generation.template_engine import TemplateEngine
from src.code_generation.renderers import (
    render_controller,
    render_controller_from_actions,
    render_dto_class,
    render_entity_class,
    render_interface,
    render_appsettings,
    build_controller_validation_guards,
    build_service_validation_guards,
    render_csproj,
    render_program,
    render_repository_class,
    render_service_class,
    render_test_csproj,
)
from src.code_generation.repo_generation import RepoGenerationHelper
from src.code_generation.service_generation import ServiceGenerationHelper
from src.code_generation.spec_helpers import SpecHelpers
from src.code_generation.spec_completion import SpecCompletionHelper
from src.code_generation.naming_helpers import NamingHelpers
from src.code_generation.controller_generation import ControllerGenerationHelper
from src.code_generation.audit_helpers import AuditHelpers
from src.test_generator import TestGenerator
from src.code_generation.design_ops_resolver import DesignOpsResolver
from src.utils.logic_auditor import LogicAuditor
from src.utils.design_doc_refiner import DesignDocRefiner
from src.config.config_manager import ConfigManager
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.code_synthesis.method_store import MethodStore
from src.vector_engine.vector_engine import VectorEngine


class ProjectGenerator:
    def __init__(self, template_dir: str | None = None) -> None:
        if template_dir is None:
            template_dir = os.path.join(os.getcwd(), "templates", "project")
        self.workspace_root = os.getcwd()
        self._engine = TemplateEngine(template_dir)
        self._ops_resolver: DesignOpsResolver | None = None
        self._logic_auditor: LogicAuditor | None = None
        self._doc_refiner: DesignDocRefiner | None = None
        self._config: ConfigManager | None = None
        self._method_store: MethodStore | None = None
        self._synthesizer: CodeSynthesizer | None = None
        self._vector_engine: VectorEngine | None = None
        self._repo_gen = RepoGenerationHelper(self)
        self._service_gen = ServiceGenerationHelper(self)
        self._spec_helpers = SpecHelpers(self)
        self._spec_completion = SpecCompletionHelper(self)
        self._naming = NamingHelpers(self)
        self._controller_gen = ControllerGenerationHelper(self)
        self._audit_helpers = AuditHelpers(self)
        self._use_synth_repo = os.environ.get("USE_CODE_SYNTH_REPO", "1") != "0"
        self._use_synth_service = os.environ.get("USE_CODE_SYNTH_SERVICE", "1") != "0"
        self._force_synth_project = os.environ.get("USE_CODE_SYNTH_PROJECT_ALL", "1") != "0"
        self._allow_service_freeform = os.environ.get("USE_SERVICE_FREEFORM", "0") == "1"

    def _get_ops_resolver(self) -> DesignOpsResolver:
        if self._ops_resolver is None:
            self._ops_resolver = DesignOpsResolver(self._config or ConfigManager(), vector_engine=self._get_vector_engine())
        return self._ops_resolver

    def _get_vector_engine(self) -> VectorEngine:
        if self._vector_engine is None:
            self._config = self._config or ConfigManager()
            self._vector_engine = VectorEngine(model_path=self._config.vector_model_path)
        return self._vector_engine

    def _get_logic_auditor_factory(self, resolver: DesignOpsResolver) -> LogicAuditor:
        return LogicAuditor(
            config_manager=resolver.config,
            morph_analyzer=resolver.morph,
            vector_engine=self._get_vector_engine(),
            knowledge_base=resolver.ukb,
        )

    def _get_doc_refiner_factory(self, resolver: DesignOpsResolver) -> DesignDocRefiner:
        return DesignDocRefiner(
            config_manager=resolver.config,
            morph_analyzer=resolver.morph,
            vector_engine=self._get_vector_engine(),
            knowledge_base=resolver.ukb,
        )

    def _get_synthesizer(self) -> CodeSynthesizer:
        if self._synthesizer is None:
            resolver = self._get_ops_resolver()
            self._config = resolver.config
            self._method_store = self._method_store or MethodStore(
                self._config,
                morph_analyzer=resolver.morph,
                vector_engine=self._get_vector_engine(),
            )
            self._synthesizer = CodeSynthesizer(
                self._config,
                method_store=self._method_store,
                morph_analyzer=resolver.morph,
            )
        return self._synthesizer

    def _normalize_core_logic(self, core_logic: list) -> list:
        normalized = []
        for line in core_logic:
            text = str(line).strip()
            if not text:
                continue
            parts = text.split(None, 1)
            if parts:
                head = parts[0]
                if head.endswith(".") or head.endswith(")"):
                    num = head[:-1]
                    if num.isdigit():
                        text = parts[1] if len(parts) > 1 else ""
            if text:
                normalized.append(text)
        return normalized

    def _build_method_design_doc(self, method_name: str, method_spec: dict) -> str:
        if not method_spec:
            return ""
        input_text = method_spec.get("input", "").strip()
        output_text = method_spec.get("output", "").strip()
        core_logic = method_spec.get("core_logic", []) or []
        lines = [f"# {method_name} Design Document", "", "## Purpose", "Auto-generated for audit.", "", "### Input"]
        lines.append(f"- **Description**: {input_text or 'none'}")
        lines.append("")
        lines.append("### Output")
        lines.append(f"- **Description**: {output_text or 'none'}")
        lines.append("")
        lines.append("### Core Logic")
        if core_logic:
            for item in core_logic:
                text = str(item).strip()
                if not text:
                    continue
                if text[0].isdigit() and "." in text:
                    lines.append(text)
                else:
                    lines.append(f"- {text}")
        else:
            lines.append("- (no core logic specified)")
        return "\n".join(lines) + "\n"

    def _ensure_dir(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)

    def _render_template(self, name: str, values: dict) -> str:
        return self._engine.render(name, values)

    def _load_step_templates(self) -> dict:
        return self._engine.load_json("steps.json")

    def _load_validation_templates(self) -> dict:
        return self._engine.load_json("validation.json")

    def _write_file(self, path: str, content: str) -> None:
        self._ensure_dir(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _map_type(self, t: str) -> str:
        return self._naming.map_type(t)

    def _parse_props(self, lines: list) -> list:
        return self._naming.parse_props(lines)

    def _build_default_mapping(self, source_props: list, target_props: list) -> list:
        return self._naming.build_default_mapping(source_props, target_props)

    def _resolve_dto_mapping(self, create_mapping: list, response_mapping: list, create_dto_props: list, response_dto_props: list, entity_props: list) -> dict:
        return self._naming.resolve_dto_mapping(create_mapping, response_mapping, create_dto_props, response_dto_props, entity_props)

    def _render_entity_class(self, name: str, props: list, root_namespace: str) -> str:
        return render_entity_class(name, props, root_namespace)

    def _render_interface(
        self,
        name: str,
        methods: list,
        root_namespace: str,
        namespace_suffix: str,
        using_namespace: str,
    ) -> str:
        return render_interface(name, methods, root_namespace, namespace_suffix, using_namespace)

    def _render_service_class(self, name: str, iface: str, repo_iface: str, methods: list, root_namespace: str) -> str:
        return render_service_class(name, iface, repo_iface, methods, root_namespace)

    def _render_repository_class(self, name: str, iface: str, methods: list, root_namespace: str) -> str:
        return render_repository_class(name, iface, methods, root_namespace)

    def _render_controller(
        self,
        name: str,
        service_iface: str,
        routes: list,
        route_base: str,
        action_names: dict,
        service_calls: dict,
        create_dto: str,
        id_type: str,
        root_namespace: str,
        validation_guards: list | None = None,
    ) -> str:
        return render_controller(
            name,
            service_iface,
            routes,
            route_base,
            action_names,
            service_calls,
            create_dto,
            id_type,
            root_namespace,
            validation_guards,
        )

    def _render_controller_from_actions(
        self,
        name: str,
        service_iface: str,
        route_base: str,
        action_lines: list,
        root_namespace: str,
    ) -> str:
        return render_controller_from_actions(
            name,
            service_iface,
            route_base,
            action_lines,
            root_namespace,
        )

    def _render_dto_class(self, name: str, props: list, has_from: bool, has_to: bool, entity_name: str, dto_mapping: dict, root_namespace: str) -> str:
        return render_dto_class(name, props, has_from, has_to, entity_name, dto_mapping, root_namespace)

    def _extract_type_token(self, text: str) -> str:
        return self._naming.extract_type_token(text)

    def _infer_return_type_from_output(self, output_text: str, default_type: str) -> str:
        return self._naming.infer_return_type_from_output(output_text, default_type)

    def _apply_nullable_hint(self, signature: str, default_type: str) -> str:
        return self._naming.apply_nullable_hint(signature, default_type)

    def _infer_nullable_return(self, method_specs: dict, key: str, default_type: str) -> str:
        return self._naming.infer_nullable_return(method_specs, key, default_type)

    def _build_module_method_return_map(self, modules: list) -> dict:
        return self._naming.build_module_method_return_map(modules)

    def _infer_id_type(self, entity_name: str, entities: list, hints_entities: dict) -> str:
        return self._naming.infer_id_type(entity_name, entities, hints_entities)

    def _map_target_framework(self, target: str) -> str:
        return self._naming.map_target_framework(target)

    def _render_csproj(self, project_name: str, target: str, provider: str, strategy: str) -> str:
        tfm = self._map_target_framework(target)
        packages = []
        if str(provider).lower() == "sqlserver":
            packages.append("Microsoft.Data.SqlClient")
        if str(strategy).lower() == "dapper":
            packages.append("Dapper")
        package_lines = []
        if packages:
            package_lines.append("  <ItemGroup>")
            for pkg in packages:
                package_lines.append(f"    <PackageReference Include=\"{pkg}\" Version=\"*\" />")
            package_lines.append("  </ItemGroup>")
        return render_csproj(project_name, tfm, package_lines)

    def _render_test_csproj(self, project_name: str, target: str) -> str:
        tfm = self._map_target_framework(target)
        test_name = f"{project_name}.Tests"
        return render_test_csproj(test_name, tfm, project_name)

    def _render_service_tests(self, test_context: dict, root_namespace: str) -> str:
        generator = TestGenerator(self.workspace_root)
        result = generator.generate_tests(
            mode="service",
            test_context=test_context,
            root_namespace=root_namespace,
        )
        if isinstance(result, dict) and result.get("status") == "success":
            return result.get("content", "")
        return ""

    def _render_program(self, service_regs: str, repo_regs: str, provider: str, root_namespace: str) -> str:
        db_registration = ""
        if provider.lower() == "sqlserver":
            db_registration = "builder.Services.AddScoped<IDbConnection>(_ => new SqlConnection(builder.Configuration.GetConnectionString(\"Default\")));"
        return render_program(service_regs, repo_regs, db_registration, root_namespace)

    def _render_appsettings(self) -> str:
        return render_appsettings()

    def _ensure_method_spec(self, specs: dict, full_name: str) -> dict:
        return self._spec_completion.ensure_method_spec(specs, full_name)

    def _default_service_steps(self, method_kind: str) -> list:
        return self._spec_completion.default_service_steps(method_kind)

    def _default_repo_steps(self, method_kind: str) -> list:
        return self._spec_completion.default_repo_steps(method_kind)

    def _build_default_service_core_logic(self, method_kind: str, entity_name: str, response_dto: str) -> list:
        return self._spec_completion.build_default_service_core_logic(method_kind, entity_name, response_dto)

    def _build_default_repo_core_logic(self, method_kind: str, entity_name: str, table_name: str, select_columns: list, insert_columns: list, update_columns: list) -> list:
        return self._spec_completion.build_default_repo_core_logic(
            method_kind,
            entity_name,
            table_name,
            select_columns,
            insert_columns,
            update_columns,
        )

    def _complete_method_specs_for_generation(
        self,
        method_specs: dict,
        entity_specs: list,
        entities: list,
        crud_template: dict,
    ) -> dict:
        return self._spec_completion.complete_method_specs_for_generation(
            method_specs,
            entity_specs,
            entities,
            crud_template,
        )

    def _extract_ops_from_core(self, core_logic: list) -> list:
        ops = []
        for line in core_logic or []:
            text = str(line)
            if "[ops:" not in text.lower():
                continue
            start = text.lower().find("[ops:")
            end = text.find("]", start)
            if start == -1 or end == -1:
                continue
            raw = text[start + 5:end]
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            ops.extend([p.lower() for p in parts])
        return ops

    def _extract_method_body_lines(self, code: str, method_name: str) -> list:
        if not code or not method_name:
            return []
        lines = code.splitlines()
        start_idx = None
        for i, line in enumerate(lines):
            if method_name + "(" in line:
                start_idx = i
                break
        if start_idx is None:
            return []
        brace_count = 0
        started = False
        body_lines = []
        for i in range(start_idx, len(lines)):
            line = lines[i]
            if not started:
                if "{" in line:
                    started = True
                    brace_count += line.count("{") - line.count("}")
                continue
            else:
                brace_count += line.count("{") - line.count("}")
                if brace_count <= 0:
                    break
                body_lines.append(line.strip())
        return [l for l in body_lines if l]

    def _filter_synth_body_lines(self, body_lines: list) -> list:
        if not body_lines:
            return []
        filtered = []
        i = 0
        while i < len(body_lines):
            text = str(body_lines[i])
            next_text = str(body_lines[i + 1]) if i + 1 < len(body_lines) else ""
            if "ArgumentNullException" in text:
                i += 1
                continue
            if "== null" in text and text.strip().startswith("if"):
                if "ArgumentNullException" in next_text:
                    i += 1
                    continue
                if not any(token in next_text for token in ["return", "{"]):
                    i += 1
                    continue
            filtered.append(text)
            i += 1
        return filtered


    def _build_structured_spec_for_controller(
        self,
        action_name: str,
        action_kind: str,
        service_call: str,
        create_dto: str,
        id_type: str,
    ) -> dict:
        return self._controller_gen.build_structured_spec_for_controller(
            action_name,
            action_kind,
            service_call,
            create_dto,
            id_type,
        )

    def _synthesize_controller_action_body(
        self,
        action_name: str,
        action_kind: str,
        service_call: str,
        create_dto: str,
        id_type: str,
    ) -> list:
        return self._controller_gen.synthesize_controller_action_body(
            action_name,
            action_kind,
            service_call,
            create_dto,
            id_type,
        )

    def _format_name(self, template: str, entity: str, entity_plural: str) -> str:
        return self._naming.format_name(template, entity, entity_plural)

    def _build_validation_guards(self, dto_name: str, var_name: str, validation_rules: dict, field_types: dict, validation_templates: dict) -> list:
        return build_service_validation_guards(dto_name, var_name, validation_rules, field_types, validation_templates)

    def _build_controller_validation_guards(self, dto_name: str, var_name: str, validation_rules: dict, field_types: dict, validation_templates: dict) -> list:
        return build_controller_validation_guards(dto_name, var_name, validation_rules, field_types, validation_templates)

    def _build_service_method_name_map(self, service_name: str, method_specs: dict) -> dict:
        return self._naming.build_service_method_name_map(service_name, method_specs)

    def _build_repo_method_name_map(self, repo_name: str, method_specs: dict) -> dict:
        return self._naming.build_repo_method_name_map(repo_name, method_specs)

    def _build_crud_template_override(self, crud_template: dict, service_name_map: dict, repo_name_map: dict) -> dict:
        return self._naming.build_crud_template_override(crud_template, service_name_map, repo_name_map)

    def _infer_route_base(self, routes: list, default_base: str) -> str:
        return self._naming.infer_route_base(routes, default_base)

    def _render_step_lines(self, step_key: str, step_templates: dict, context: dict) -> list:
        lines = step_templates.get(step_key, [])
        rendered = []
        for line in lines:
            if line == "{ValidationGuards}":
                rendered.extend(context.get("ValidationGuards", []))
                continue
            if line == "{UpdateAssignments}":
                rendered.extend(context.get("UpdateAssignments", []))
                continue
            if line == "{TimestampAssignment}":
                assignment = context.get("TimestampAssignment")
                if assignment:
                    rendered.append(assignment)
                continue
            text = line
            for k, v in context.items():
                if isinstance(v, str):
                    text = text.replace("{" + k + "}", v)
            rendered.append(text)
        return rendered

    def _to_camel(self, name: str) -> str:
        return self._naming.to_camel(name)

    def generate(self, spec: dict, output_root: str) -> None:
        project_name = spec.get("project_name") or "GeneratedProject"
        ps = spec.get("spec", {})
        tech = ps.get("tech", {})
        data_access = ps.get("data_access", {})
        provider = data_access.get("Provider", "SqlServer")
        modules = ps.get("modules", [])
        entities = ps.get("entities", [])
        dtos = ps.get("dtos", [])
        method_specs = ps.get("method_specs", {})
        module_method_returns = self._build_module_method_return_map(modules)
        validation_rules = ps.get("validation", {})
        generation_hints = ps.get("generation_hints", {})
        step_templates = self._load_step_templates()
        validation_templates = self._load_validation_templates()
        hints_entities = generation_hints.get("entities", {}) if isinstance(generation_hints, dict) else {}
        crud_template = generation_hints.get("crud_template", {}) if isinstance(generation_hints, dict) else {}
        entity_specs = generation_hints.get("entity_specs", []) if isinstance(generation_hints, dict) else []
        if not entity_specs:
            entity_name = hints_entities.get("Primary Entity") or (entities[0].get("name") if entities else "Entity")
            entity_plural = hints_entities.get("Entity Plural") or f"{entity_name}s"
            create_dto = hints_entities.get("Create Request DTO") or (dtos[0].get("name") if dtos else f"{entity_name}CreateRequest")
            response_dto = hints_entities.get("Response DTO") or (dtos[1].get("name") if len(dtos) > 1 else f"{entity_name}Response")
            entity_specs = [
                {
                    "name": entity_name,
                    "plural": entity_plural,
                    "create_dto": create_dto,
                    "response_dto": response_dto,
                    "controller": next((m.get("name") for m in modules if str(m.get("type", "")).lower() == "controller"), f"{entity_plural}Controller"),
                    "service": next((m.get("name") for m in modules if str(m.get("type", "")).lower() == "service"), f"{entity_name}Service"),
                    "repository": next((m.get("name") for m in modules if str(m.get("type", "")).lower() == "repository"), f"{entity_name}Repository"),
                    "routes": [],
                    "create_mapping": generation_hints.get("dto_mapping", {}).get("create_to_entity", []),
                    "response_mapping": generation_hints.get("dto_mapping", {}).get("entity_to_response", []),
                }
            ]

        method_specs = self._complete_method_specs_for_generation(
            method_specs,
            entity_specs,
            entities,
            crud_template,
        )

        def _module_names_by_type(mods: list, type_name: str) -> set:
            names = set()
            for m in mods or []:
                if str(m.get("type", "")).lower() != type_name:
                    continue
                name = m.get("name")
                if name:
                    names.add(name)
            return names

        def _warn_missing_module(entity_specs_list: list, type_name: str, key: str, declared: set) -> None:
            if not declared:
                return
            missing = []
            for spec_item in entity_specs_list or []:
                name = spec_item.get(key)
                if name and name not in declared and name not in missing:
                    missing.append(name)
            if missing:
                joined = ", ".join(missing)
                print(f"[!] Module definition missing {type_name}: {joined}")

        declared_controllers = _module_names_by_type(modules, "controller")
        declared_services = _module_names_by_type(modules, "service")
        declared_repos = _module_names_by_type(modules, "repository")
        _warn_missing_module(entity_specs, "controller", "controller", declared_controllers)
        _warn_missing_module(entity_specs, "service", "service", declared_services)
        _warn_missing_module(entity_specs, "repository", "repository", declared_repos)

        self._ensure_dir(output_root)
        self._ensure_dir(os.path.join(output_root, "Controllers"))
        self._ensure_dir(os.path.join(output_root, "Services"))
        self._ensure_dir(os.path.join(output_root, "Repositories"))
        self._ensure_dir(os.path.join(output_root, "Models"))
        self._ensure_dir(os.path.join(output_root, "DTO"))

        for e in entities:
            name = e.get("name")
            props = self._parse_props(e.get("properties"))
            if name:
                self._write_file(
                    os.path.join(output_root, "Models", f"{name}.cs"),
                    self._render_entity_class(name, props, project_name),
                )

        for d in dtos:
            name = d.get("name")
            props = self._parse_props(d.get("properties"))
            if not name:
                continue
            spec_item = next((s for s in entity_specs if s.get("create_dto") == name or s.get("response_dto") == name), None)
            if spec_item:
                entity_name = spec_item.get("name")
                has_from = name == spec_item.get("response_dto")
                has_to = name == spec_item.get("create_dto")
                create_dto_props = next((dto.get("properties") for dto in dtos if dto.get("name") == spec_item.get("create_dto")), [])
                response_dto_props = next((dto.get("properties") for dto in dtos if dto.get("name") == spec_item.get("response_dto")), [])
                entity_props = next((e.get("properties") for e in entities if e.get("name") == entity_name), [])
                dto_mapping = self._resolve_dto_mapping(
                    spec_item.get("create_mapping", []),
                    spec_item.get("response_mapping", []),
                    create_dto_props,
                    response_dto_props,
                    entity_props,
                )
            else:
                entity_name = (entities[0].get("name") if entities else "Entity")
                has_from = False
                has_to = False
                dto_mapping = generation_hints.get("dto_mapping", {})
            self._write_file(
                os.path.join(output_root, "DTO", f"{name}.cs"),
                self._render_dto_class(name, props, has_from, has_to, entity_name, dto_mapping, project_name),
            )

        logic_findings = []
        refiner_findings = []
        resolver_stats = {
            "morph": 0,
            "syntactic": 0,
            "semantic": 0,
            "ukb_search": 0,
            "ukb_hits": 0,
        }
        for spec_item in entity_specs:
            entity_name = spec_item.get("name")
            entity_plural = spec_item.get("plural", f"{entity_name}s")
            id_type = self._infer_id_type(entity_name, entities, hints_entities)
            create_dto = spec_item.get("create_dto")
            response_dto = spec_item.get("response_dto")
            controller_name = spec_item.get("controller")
            service_name = spec_item.get("service")
            repo_name = spec_item.get("repository")
            routes = spec_item.get("routes", [])
            create_dto_props = next((d.get("properties") for d in dtos if d.get("name") == create_dto), [])
            response_dto_props = next((d.get("properties") for d in dtos if d.get("name") == response_dto), [])
            entity_props = next((e.get("properties") for e in entities if e.get("name") == entity_name), [])
            dto_mapping = self._resolve_dto_mapping(
                spec_item.get("create_mapping", []),
                spec_item.get("response_mapping", []),
                create_dto_props,
                response_dto_props,
                entity_props,
            )
            create_to_entity = dto_mapping.get("create_to_entity", [])
            insert_fields = [m.get("to") for m in create_to_entity if isinstance(m, dict) and m.get("to")]
            entity_fields = {name for name, _ in self._parse_props(entity_props)}
            update_fields = [f for f in insert_fields if f and f.lower() != "createdat"]
            if "UpdatedAt" in entity_fields and "UpdatedAt" not in update_fields:
                update_fields.append("UpdatedAt")
            param_name = self._to_camel(entity_name)
            field_types = {name: typ for name, typ in self._parse_props(create_dto_props)}
            controller_validation_guards = self._build_controller_validation_guards(
                create_dto,
                "req",
                validation_rules,
                field_types,
                validation_templates,
            )
            list_service = self._format_name(crud_template.get("List", {}).get("Service", "Get{EntityPlural}"), entity_name, entity_plural)
            get_service = self._format_name(crud_template.get("GetById", {}).get("Service", "Get{Entity}ById"), entity_name, entity_plural)
            create_service = self._format_name(crud_template.get("Create", {}).get("Service", "Create{Entity}"), entity_name, entity_plural)
            update_service = self._format_name(crud_template.get("Update", {}).get("Service", "Update{Entity}"), entity_name, entity_plural)
            delete_service = self._format_name(crud_template.get("Delete", {}).get("Service", "Delete{Entity}"), entity_name, entity_plural)
            repo_list = crud_template.get("List", {}).get("Repository", "FetchAll")
            repo_get = crud_template.get("GetById", {}).get("Repository", "FetchById")
            repo_create = crud_template.get("Create", {}).get("Repository", "Insert")
            repo_update = crud_template.get("Update", {}).get("Repository", "Update")
            repo_delete = crud_template.get("Delete", {}).get("Repository", "Delete")
            service_name_map = self._build_service_method_name_map(service_name, method_specs)
            if service_name_map:
                list_service = service_name_map.get("list", list_service)
                get_service = service_name_map.get("get", get_service)
                create_service = service_name_map.get("create", create_service)
                update_service = service_name_map.get("update", update_service)
                delete_service = service_name_map.get("delete", delete_service)
            repo_name_map = self._build_repo_method_name_map(repo_name, method_specs)
            if repo_name_map:
                repo_list = repo_name_map.get("list", repo_list)
                repo_get = repo_name_map.get("get", repo_get)
                repo_create = repo_name_map.get("create", repo_create)
                repo_update = repo_name_map.get("update", repo_update)
                repo_delete = repo_name_map.get("delete", repo_delete)
            action_names = {
                "list": list_service,
                "get": get_service,
                "create": create_service,
                "update": update_service,
                "delete": delete_service,
            }
            service_calls = {
                "list": list_service,
                "get": get_service,
                "create": create_service,
                "update": update_service,
                "delete": delete_service,
            }
            repo_calls = {
                "list": repo_list,
                "get": repo_get,
                "create": repo_create,
                "update": repo_update,
                "delete": repo_delete,
            }

            service_iface = "I" + service_name
            repo_iface = "I" + repo_name

            service_bodies = self._service_gen.build_service_method_bodies(
                method_specs,
                service_name,
                service_calls,
                repo_calls,
                response_dto,
                create_dto,
                dto_mapping,
                validation_rules,
                field_types,
                validation_templates,
                step_templates,
                entity_name,
                id_type,
                entity_props,
            )
            repo_bodies = self._repo_gen.build_repo_method_bodies(
                method_specs,
                repo_name,
                entity_name,
                entity_props,
                insert_fields,
                update_fields,
                param_name,
                id_type,
                step_templates,
                repo_calls,
            )

            # Logic audit (existing feature) for inferred or explicit core logic
            service_method_keys = {
                list_service: "list",
                get_service: "get",
                create_service: "create",
                update_service: "update",
                delete_service: "delete",
            }
            for method_name in service_method_keys.keys():
                spec_key = f"{service_name}.{method_name}"
                core = (method_specs.get(spec_key, {}) or {}).get("core_logic", [])
                body = service_bodies.get(method_name, [])
                logic_findings.extend(self._audit_helpers.audit_logic(core, body, spec_key))

            repo_method_keys = {
                repo_list: "list",
                repo_get: "get",
                repo_create: "create",
                repo_update: "update",
                repo_delete: "delete",
            }
            for method_name in repo_method_keys.keys():
                spec_key = f"{repo_name}.{method_name}"
                core = (method_specs.get(spec_key, {}) or {}).get("core_logic", [])
                body = repo_bodies.get(method_name, [])
                logic_findings.extend(self._audit_helpers.audit_logic(core, body, spec_key))
            resolver = self._get_ops_resolver()
            stats = resolver.get_stats()
            for k in resolver_stats:
                resolver_stats[k] += stats.get(k, 0)
            service_get_users_ret = self._infer_nullable_return(method_specs, f"{service_name}.{list_service}", f"List<{response_dto}>")
            service_get_by_id_ret = self._infer_nullable_return(method_specs, f"{service_name}.{get_service}", response_dto)
            service_create_ret = self._infer_nullable_return(method_specs, f"{service_name}.{create_service}", response_dto)
            service_update_ret = self._infer_nullable_return(method_specs, f"{service_name}.{update_service}", response_dto)
            service_delete_ret = self._infer_nullable_return(method_specs, f"{service_name}.{delete_service}", "bool")
            repo_fetch_all_ret = self._infer_nullable_return(method_specs, f"{repo_name}.{repo_list}", f"List<{entity_name}>")
            repo_fetch_by_id_ret = self._infer_nullable_return(method_specs, f"{repo_name}.{repo_get}", entity_name)
            repo_insert_ret = self._infer_nullable_return(method_specs, f"{repo_name}.{repo_create}", entity_name)
            repo_update_ret = self._infer_nullable_return(method_specs, f"{repo_name}.{repo_update}", entity_name)
            repo_delete_ret = self._infer_nullable_return(method_specs, f"{repo_name}.{repo_delete}", "bool")
            if service_name:
                key = f"{service_name}.{list_service}"
                service_get_users_ret = self._apply_nullable_hint(module_method_returns.get(key, ""), service_get_users_ret)
                key = f"{service_name}.{get_service}"
                service_get_by_id_ret = self._apply_nullable_hint(module_method_returns.get(key, ""), service_get_by_id_ret)
                key = f"{service_name}.{create_service}"
                service_create_ret = self._apply_nullable_hint(module_method_returns.get(key, ""), service_create_ret)
                key = f"{service_name}.{update_service}"
                service_update_ret = self._apply_nullable_hint(module_method_returns.get(key, ""), service_update_ret)
                key = f"{service_name}.{delete_service}"
                service_delete_ret = self._apply_nullable_hint(module_method_returns.get(key, ""), service_delete_ret)
            if repo_name:
                key = f"{repo_name}.{repo_list}"
                repo_fetch_all_ret = self._apply_nullable_hint(module_method_returns.get(key, ""), repo_fetch_all_ret)
                key = f"{repo_name}.{repo_get}"
                repo_fetch_by_id_ret = self._apply_nullable_hint(module_method_returns.get(key, ""), repo_fetch_by_id_ret)
                key = f"{repo_name}.{repo_create}"
                repo_insert_ret = self._apply_nullable_hint(module_method_returns.get(key, ""), repo_insert_ret)
                key = f"{repo_name}.{repo_update}"
                repo_update_ret = self._apply_nullable_hint(module_method_returns.get(key, ""), repo_update_ret)
                key = f"{repo_name}.{repo_delete}"
                repo_delete_ret = self._apply_nullable_hint(module_method_returns.get(key, ""), repo_delete_ret)
            service_methods = [
                (f"public {service_get_users_ret} {list_service}()", service_bodies.get(list_service, [f"return new List<{response_dto}>();"])),
                (f"public {service_get_by_id_ret} {get_service}({id_type} id)", service_bodies.get(get_service, ["return null;"])),
                (f"public {service_create_ret} {create_service}({create_dto} req)", service_bodies.get(create_service, ["return null;"])),
                (f"public {service_update_ret} {update_service}({id_type} id, {create_dto} req)", service_bodies.get(update_service, ["return null;"])),
                (f"public {service_delete_ret} {delete_service}({id_type} id)", service_bodies.get(delete_service, ["return false;"])),
            ]
            repo_methods = [
                (f"public {repo_fetch_all_ret} {repo_list}()", repo_bodies.get(repo_list, [f"return new List<{entity_name}>();"])),
                (f"public {repo_fetch_by_id_ret} {repo_get}({id_type} id)", repo_bodies.get(repo_get, ["return null;"])),
                (f"public {repo_insert_ret} {repo_create}({entity_name} {param_name})", repo_bodies.get(repo_create, ["return " + param_name + ";"])),
                (f"public {repo_update_ret} {repo_update}({id_type} id, {entity_name} {param_name})", repo_bodies.get(repo_update, ["return null;"])),
                (f"public {repo_delete_ret} {repo_delete}({id_type} id)", repo_bodies.get(repo_delete, ["return false;"])),
            ]
            repo_method_sigs = [m[0] for m in repo_methods]
            service_method_sigs = [m[0] for m in service_methods]

            self._write_file(
                os.path.join(output_root, "Services", f"{service_iface}.cs"),
                self._render_interface(
                    service_iface,
                    service_method_sigs,
                    project_name,
                    "Services",
                    f"{project_name}.DTO",
                ),
            )
            self._write_file(
                os.path.join(output_root, "Services", f"{service_name}.cs"),
                self._render_service_class(service_name, service_iface, repo_iface, service_methods, project_name),
            )
            service_path = os.path.join(output_root, "Services", f"{service_name}.cs")
            try:
                with open(service_path, "r", encoding="utf-8") as f:
                    service_code = f.read()
            except OSError:
                service_code = ""
            for method_name in service_method_keys.keys():
                spec_key = f"{service_name}.{method_name}"
                design_doc = self._build_method_design_doc(spec_key, method_specs.get(spec_key, {}))
                refiner_findings.extend(self._audit_helpers.audit_design_doc(design_doc, service_path, spec_key, service_code))
            self._write_file(
                os.path.join(output_root, "Repositories", f"{repo_iface}.cs"),
                self._render_interface(
                    repo_iface,
                    repo_method_sigs,
                    project_name,
                    "Repositories",
                    f"{project_name}.Models",
                ),
            )
            self._write_file(
                os.path.join(output_root, "Repositories", f"{repo_name}.cs"),
                self._render_repository_class(repo_name, repo_iface, repo_methods, project_name),
            )
            repo_path = os.path.join(output_root, "Repositories", f"{repo_name}.cs")
            try:
                with open(repo_path, "r", encoding="utf-8") as f:
                    repo_code = f.read()
            except OSError:
                repo_code = ""
            for method_name in repo_method_keys.keys():
                spec_key = f"{repo_name}.{method_name}"
                design_doc = self._build_method_design_doc(spec_key, method_specs.get(spec_key, {}))
                refiner_findings.extend(self._audit_helpers.audit_design_doc(design_doc, repo_path, spec_key, repo_code))
            if routes:
                route_base = self._infer_route_base(routes, entity_plural.lower())
                if self._force_synth_project:
                    action_lines = []
                    for route in routes:
                        method, path = route.split(" ", 1) if " " in route else ("GET", route)
                        method = method.upper()
                        path = path.strip()
                        attr = "HttpGet"
                        if method == "POST":
                            attr = "HttpPost"
                        if method == "PUT":
                            attr = "HttpPut"
                        if method == "DELETE":
                            attr = "HttpDelete"
                        if path.startswith("/"):
                            path = path[1:]
                        if route_base:
                            if path == route_base:
                                path = ""
                            elif path.startswith(route_base + "/"):
                                path = path[len(route_base) + 1 :]
                        if not path:
                            path = ""
                        action_lines.append(f"    [{attr}(\"{path}\")]")
                        if "{id}" in path:
                            if method == "PUT":
                                action_kind = "update"
                                action_name = action_names.get("update", "UpdateItem")
                                service_call = service_calls.get("update", action_name)
                                action_lines.append(f"    public IActionResult {action_name}({id_type} id, [FromBody] {create_dto} req)")
                            elif method == "DELETE":
                                action_kind = "delete"
                                action_name = action_names.get("delete", "DeleteItem")
                                service_call = service_calls.get("delete", action_name)
                                action_lines.append(f"    public IActionResult {action_name}({id_type} id)")
                            else:
                                action_kind = "get"
                                action_name = action_names.get("get", "GetItemById")
                                service_call = service_calls.get("get", action_name)
                                action_lines.append(f"    public IActionResult {action_name}({id_type} id)")
                        elif method == "POST":
                            action_kind = "create"
                            action_name = action_names.get("create", "CreateItem")
                            service_call = service_calls.get("create", action_name)
                            action_lines.append(f"    public IActionResult {action_name}([FromBody] {create_dto} req)")
                        else:
                            action_kind = "list"
                            action_name = action_names.get("list", "GetItems")
                            service_call = service_calls.get("list", action_name)
                            action_lines.append(f"    public IActionResult {action_name}()")
                        body = self._synthesize_controller_action_body(action_name, action_kind, service_call, create_dto, id_type)
                        if not body:
                            raise RuntimeError(f"Controller synth failed: {controller_name}.{action_name}")
                        if action_kind in ["create", "update"] and controller_validation_guards:
                            body = controller_validation_guards + body
                        action_lines.append("    {")
                        action_lines.extend([f"        {b}" for b in body])
                        action_lines.append("    }")
                    self._write_file(
                        os.path.join(output_root, "Controllers", f"{controller_name}.cs"),
                        self._render_controller_from_actions(
                            controller_name,
                            service_iface,
                            route_base,
                            action_lines,
                            project_name,
                        ),
                    )
                else:
                    self._write_file(
                        os.path.join(output_root, "Controllers", f"{controller_name}.cs"),
                        self._render_controller(
                            controller_name,
                            service_iface,
                            routes,
                            route_base,
                            action_names,
                            service_calls,
                            create_dto,
                            id_type,
                            project_name,
                            controller_validation_guards,
                        ),
                    )

        service_regs = []
        repo_regs = []
        for spec_item in entity_specs:
            svc = spec_item.get("service")
            repo = spec_item.get("repository")
            if svc:
                service_regs.append(f"builder.Services.AddScoped<I{svc}, {svc}>();")
            if repo:
                repo_regs.append(f"builder.Services.AddScoped<I{repo}, {repo}>();")
        self._write_file(
            os.path.join(output_root, "Program.cs"),
            self._render_program("\n".join(service_regs), "\n".join(repo_regs), provider, project_name),
        )
        self._write_file(os.path.join(output_root, "appsettings.json"), self._render_appsettings())
        self._write_file(os.path.join(output_root, f"{project_name}.csproj"), self._render_csproj(project_name, tech.get("Target"), provider, data_access.get("Strategy", "Dapper")))
        if any(v > 0 for v in resolver_stats.values()):
            print("[*] Resolver stats:",
                  f"morph={resolver_stats['morph']}",
                  f"syntactic={resolver_stats['syntactic']}",
                  f"semantic={resolver_stats['semantic']}",
                  f"ukb_search={resolver_stats['ukb_search']}",
                  f"ukb_hits={resolver_stats['ukb_hits']}")

        test_dir = os.path.join(output_root, "Tests")
        self._ensure_dir(test_dir)
        self._write_file(os.path.join(test_dir, f"{project_name}.Tests.csproj"), self._render_test_csproj(project_name, tech.get("Target")))
        for spec_item in entity_specs:
            service_name = spec_item.get("service")
            repo_name = spec_item.get("repository")
            entity_name = spec_item.get("name")
            create_dto = spec_item.get("create_dto")
            entity_plural = spec_item.get("plural", f"{entity_name}s")
            list_service = self._format_name(crud_template.get("List", {}).get("Service", "Get{EntityPlural}"), entity_name, entity_plural)
            get_service = self._format_name(crud_template.get("GetById", {}).get("Service", "Get{Entity}ById"), entity_name, entity_plural)
            create_service = self._format_name(crud_template.get("Create", {}).get("Service", "Create{Entity}"), entity_name, entity_plural)
            update_service = self._format_name(crud_template.get("Update", {}).get("Service", "Update{Entity}"), entity_name, entity_plural)
            delete_service = self._format_name(crud_template.get("Delete", {}).get("Service", "Delete{Entity}"), entity_name, entity_plural)
            repo_list = crud_template.get("List", {}).get("Repository", "FetchAll")
            repo_get = crud_template.get("GetById", {}).get("Repository", "FetchById")
            repo_create = crud_template.get("Create", {}).get("Repository", "Insert")
            repo_update = crud_template.get("Update", {}).get("Repository", "Update")
            repo_delete = crud_template.get("Delete", {}).get("Repository", "Delete")
            service_name_map = self._build_service_method_name_map(service_name, method_specs)
            if service_name_map:
                list_service = service_name_map.get("list", list_service)
                get_service = service_name_map.get("get", get_service)
                create_service = service_name_map.get("create", create_service)
                update_service = service_name_map.get("update", update_service)
                delete_service = service_name_map.get("delete", delete_service)
            repo_name_map = self._build_repo_method_name_map(repo_name, method_specs)
            if repo_name_map:
                repo_list = repo_name_map.get("list", repo_list)
                repo_get = repo_name_map.get("get", repo_get)
                repo_create = repo_name_map.get("create", repo_create)
                repo_update = repo_name_map.get("update", repo_update)
                repo_delete = repo_name_map.get("delete", repo_delete)
            test_crud_template = self._build_crud_template_override(crud_template, service_name_map, repo_name_map)
            create_dto_props = next((d.get("properties") for d in dtos if d.get("name") == create_dto), [])
            field_types = {name: typ for name, typ in self._parse_props(create_dto_props)}
            entity_props = next((e.get("properties") for e in entities if e.get("name") == entity_name), [])
            entity_fields = [name for name, _ in self._parse_props(entity_props) if name not in ["Id", "CreatedAt"]]
            test_case_map = {}
            if service_name:
                prefix = service_name + "."
                for full_name, spec in (method_specs or {}).items():
                    if not full_name.startswith(prefix):
                        continue
                    method_name = full_name.split(".", 1)[1]
                    cases = spec.get("test_cases", []) if isinstance(spec, dict) else []
                    structured = [c for c in cases if isinstance(c, dict)]
                    if structured:
                        test_case_map[method_name] = structured
            test_generator = TestGenerator(self.workspace_root)
            test_context = test_generator.build_service_test_context(
                service_name=service_name,
                repo_name=repo_name,
                entity_name=entity_name,
                create_dto=create_dto,
                entity_plural=entity_plural,
                crud_template=test_crud_template,
                validation_rules=validation_rules,
                field_types=field_types,
                id_type=id_type,
                entity_fields=entity_fields,
                test_cases=test_case_map,
            )
            if service_name and repo_name and entity_name and create_dto:
                self._write_file(
                    os.path.join(test_dir, f"{service_name}Tests.cs"),
                    self._render_service_tests(test_context, project_name),
                )

        if logic_findings:
            print("[!] Logic audit warnings (project generation):")
            for finding in logic_findings:
                method_label = finding.get("method", "unknown")
                reason = finding.get("reason", "UNKNOWN")
                detail = finding.get("detail", "")
                print(f"    - {method_label}: {reason} {detail}".strip())
        if refiner_findings:
            print("[!] Design doc audit warnings (project generation):")
            for finding in refiner_findings:
                method_label = finding.get("method", "unknown")
                reason = finding.get("reason", "UNKNOWN")
                detail = finding.get("detail", "")
                print(f"    - {method_label}: {reason} {detail}".strip())
