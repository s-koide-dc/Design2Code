"""Project-wide semantic contract validation for ProjectSpec documents.

This validator deliberately operates on the parsed specification rather than
generated source text.  The C# compiler can prove that symbols and types exist,
but it cannot prove that a controller route, service method, repository method,
and DTO/entity contract describe the same operation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from pathlib import Path


@dataclass(frozen=True)
class ContractIssue:
    code: str
    message: str
    location: str
    blocking: bool = True

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "location": self.location, "blocking": self.blocking}


def _spec_root(project_spec: dict[str, Any]) -> dict[str, Any]:
    root = project_spec.get("spec", project_spec)
    return root if isinstance(root, dict) else {}


def _module_map(root: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for module in root.get("modules", []) or []:
        if not isinstance(module, dict):
            continue
        name = str(module.get("name") or "").strip()
        if name:
            result[name] = module
    return result


def _declared_methods(module: dict[str, Any]) -> list[str]:
    methods = module.get("methods", []) or []
    return [str(method).strip() for method in methods if str(method).strip()]


def _method_name(signature: str) -> str:
    paren = signature.find("(")
    return signature[:paren].strip() if paren >= 0 else signature.split(":", 1)[0].strip()


def _return_type(signature: str) -> str:
    colon = signature.rfind(":")
    return signature[colon + 1 :].strip() if colon >= 0 else ""


def _signature_parameter_types(signature: str) -> list[str]:
    start = signature.find("(")
    end = signature.rfind(")")
    if start < 0 or end < start:
        return []
    raw = signature[start + 1 : end].strip()
    if not raw:
        return []
    result = []
    for parameter in raw.split(","):
        token = parameter.strip().split(":", 1)
        result.append(token[1].strip() if len(token) == 2 else "")
    return result


def _type_names(root: dict[str, Any], key: str) -> set[str]:
    return {
        str(item.get("name") or "").strip()
        for item in root.get(key, []) or []
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }


def _base_type(type_text: str) -> str:
    value = type_text.strip()
    if value.endswith("?"):
        value = value[:-1].strip()
    if value.startswith("List<") and value.endswith(">"):
        value = value[5:-1].strip()
    return value


def _normalized_output_type(output: str) -> str:
    value = output.replace("`", "").strip()
    for marker in (" or null", " (empty list if none)"):
        if marker in value:
            value = value.split(marker, 1)[0].strip()
    if value.endswith("?"):
        value = value[:-1].strip()
    return value


def _matching_layer(module_by_name: dict[str, dict[str, Any]], controller: str, suffix: str) -> str | None:
    stem = controller[:-len("Controller")] if controller.endswith("Controller") else controller
    candidates = [stem, stem[:-1] if stem.endswith("s") else stem]
    for name, module in module_by_name.items():
        if str(module.get("type") or "") != suffix:
            continue
        prefix = name[:-len(suffix)] if name.endswith(suffix) else name
        if prefix in candidates:
            return name
    return None


def validate_project_contract(project_spec: dict[str, Any]) -> list[ContractIssue]:
    """Return semantic contract violations in a parsed ProjectSpec."""
    root = _spec_root(project_spec)
    modules = root.get("modules", []) or []
    method_specs = root.get("method_specs", {}) or {}
    entities = _type_names(root, "entities")
    dtos = _type_names(root, "dtos")
    known_types = entities | dtos | {"bool", "int", "long", "decimal", "double", "float", "string", "datetime", "void", "none"}
    issues: list[ContractIssue] = []
    seen_modules: set[str] = set()

    for module in modules:
        if not isinstance(module, dict):
            continue
        kind = str(module.get("type") or "").strip()
        name = str(module.get("name") or "").strip()
        location = f"module:{name or '<unnamed>'}"
        if not name:
            issues.append(ContractIssue("module_name_missing", "Module name is missing.", location))
            continue
        if name in seen_modules:
            issues.append(ContractIssue("duplicate_module", f"Module '{name}' is declared more than once.", location))
        seen_modules.add(name)
        if kind not in {"Controller", "Service", "Repository"}:
            continue

        for signature in _declared_methods(module):
            method = _method_name(signature)
            full_name = f"{name}.{method}"
            spec = method_specs.get(full_name)
            if not isinstance(spec, dict):
                issues.append(ContractIssue("method_spec_missing", f"Declared method '{full_name}' has no method spec; generation defaults will be used.", full_name, blocking=False))
                continue
            declared_return = _normalized_output_type(_return_type(signature))
            spec_output = str(spec.get("output") or "").strip()
            if declared_return and spec_output:
                output_token = _normalized_output_type(spec_output)
                if output_token and output_token.lower() != declared_return.lower():
                    issues.append(ContractIssue("method_return_mismatch", f"Declared return '{declared_return}' differs from spec output '{output_token}'.", full_name))
            for parameter_type in _signature_parameter_types(signature):
                base = _base_type(parameter_type)
                if base and base.lower() not in {item.lower() for item in known_types}:
                    issues.append(ContractIssue("unknown_parameter_type", f"Parameter type '{base}' is not declared as an entity or DTO.", full_name))

    module_by_name = _module_map(root)
    for module in modules:
        if not isinstance(module, dict) or str(module.get("type") or "") != "Controller":
            continue
        controller = str(module.get("name") or "").strip()
        if not controller.endswith("Controller"):
            continue
        service_name = _matching_layer(module_by_name, controller, "Service")
        repository_name = _matching_layer(module_by_name, controller, "Repository")
        if service_name is None:
            issues.append(ContractIssue("controller_service_missing", f"Controller '{controller}' has no matching service.", controller))
        if repository_name is None:
            issues.append(ContractIssue("controller_repository_missing", f"Controller '{controller}' has no matching repository.", controller))
        routes = module.get("routes", []) or []
        for route in routes:
            parts = str(route).strip().split(None, 1)
            if len(parts) != 2 or parts[0].upper() not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                issues.append(ContractIssue("invalid_route_contract", f"Route '{route}' must contain an HTTP verb and path.", controller))

    return issues


def format_contract_issues(issues: list[ContractIssue]) -> list[str]:
    return [f"{issue.code}: {issue.location}: {issue.message}" for issue in issues]


def validate_generated_project_contract(project_spec: dict[str, Any], output_root: str) -> list[ContractIssue]:
    """Validate cross-file links in a generated project directory.

    Compilation already validates C# syntax and type references.  This check
    covers contracts the compiler cannot express: expected layer files,
    controller service fields, and explicit DI registrations.
    """
    root = _spec_root(project_spec)
    modules = root.get("modules", []) or []
    module_by_name = _module_map(root)
    base = Path(output_root)
    issues: list[ContractIssue] = []

    def read(relative: str) -> str:
        path = base / relative
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    program = read("Program.cs")
    if not program:
        issues.append(ContractIssue("generated_program_missing", "Generated Program.cs is missing or unreadable.", "Program.cs"))

    for module in modules:
        if not isinstance(module, dict):
            continue
        kind = str(module.get("type") or "").strip()
        name = str(module.get("name") or "").strip()
        if not name or kind not in {"Controller", "Service", "Repository"}:
            continue
        folder = {"Controller": "Controllers", "Service": "Services", "Repository": "Repositories"}[kind]
        source = read(f"{folder}/{name}.cs")
        if not source:
            issues.append(ContractIssue("generated_module_missing", f"Generated {kind} '{name}' is missing.", f"{folder}/{name}.cs"))
            continue
        if kind == "Service":
            expected = f"public class {name} : I{name}"
            if expected not in source:
                issues.append(ContractIssue("service_interface_link_missing", f"Service '{name}' does not implement I{name}.", name))
            if f"AddScoped<I{name}, {name}>();" not in program:
                issues.append(ContractIssue("service_di_registration_missing", f"Service '{name}' is not registered in Program.cs.", name))
        elif kind == "Repository":
            expected = f"public class {name} : I{name}"
            if expected not in source:
                issues.append(ContractIssue("repository_interface_link_missing", f"Repository '{name}' does not implement I{name}.", name))
            if f"AddScoped<I{name}, {name}>();" not in program:
                issues.append(ContractIssue("repository_di_registration_missing", f"Repository '{name}' is not registered in Program.cs.", name))
        else:
            service_name = _matching_layer(module_by_name, name, "Service")
            if service_name is None:
                continue
            if f"private readonly I{service_name} _service;" not in source:
                issues.append(ContractIssue("controller_service_field_missing", f"Controller '{name}' is not linked to I{service_name}.", name))
            for signature in _declared_methods(module_by_name[service_name]):
                method = _method_name(signature)
                if method and f"_service.{method}(" not in source:
                    issues.append(ContractIssue("controller_service_call_missing", f"Controller '{name}' does not call service method '{method}'.", name))
    return issues
