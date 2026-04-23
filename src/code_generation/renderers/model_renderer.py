from typing import List


def render_entity_class(name: str, props: list, root_namespace: str) -> str:
    prop_lines: List[str] = []
    for p_name, p_type in props:
        if p_type == "string":
            prop_lines.append(f"    public required {p_type} {p_name} {{ get; set; }}")
        else:
            prop_lines.append(f"    public {p_type} {p_name} {{ get; set; }}")
    return "\n".join(
        [
            "using System;",
            "",
            f"namespace {root_namespace}.Models;",
            "",
            f"public class {name}",
            "{",
            "\n".join(prop_lines),
            "}",
            "",
        ]
    )


def render_dto_class(
    name: str,
    props: list,
    has_from: bool,
    has_to: bool,
    entity_name: str,
    dto_mapping: dict,
    root_namespace: str,
) -> str:
    prop_lines: List[str] = []
    for p_name, p_type in props:
        if p_type == "string":
            prop_lines.append(f"    public required {p_type} {p_name} {{ get; set; }}")
        else:
            prop_lines.append(f"    public {p_type} {p_name} {{ get; set; }}")
    extra_methods: List[str] = []
    if has_from:
        response_mappings = dto_mapping.get("entity_to_response", [])
        extra_methods.append(f"    public static {name}? FromEntity({entity_name}? entity)")
        extra_methods.append("    {")
        extra_methods.append("        if (entity == null) return null;")
        extra_methods.append(f"        return new {name}")
        extra_methods.append("        {")
        for mapping in response_mappings:
            src = mapping.get("from")
            dest = mapping.get("to")
            if src and dest:
                extra_methods.append(f"            {dest} = entity.{src},")
        extra_methods.append("        };")
        extra_methods.append("    }")
    if has_to:
        create_mappings = dto_mapping.get("create_to_entity", [])
        extra_methods.append(f"    public {entity_name} ToEntity()");
        extra_methods.append("    {")
        extra_methods.append(f"        return new {entity_name}")
        extra_methods.append("        {")
        for mapping in create_mappings:
            src = mapping.get("from")
            dest = mapping.get("to")
            if not src or not dest:
                continue
            if src.lower() == "utcnow":
                extra_methods.append(f"            {dest} = DateTime.UtcNow,")
            else:
                extra_methods.append(f"            {dest} = {src},")
        extra_methods.append("        };")
        extra_methods.append("    }")
    extra_text = ""
    if extra_methods:
        extra_text = "\n" + "\n".join(extra_methods)
    return "\n".join(
        [
            "using System;",
            f"using {root_namespace}.Models;",
            "",
            f"namespace {root_namespace}.DTO;",
            "",
            f"public class {name}",
            "{",
            "\n".join(prop_lines),
            f"{extra_text}",
            "}",
            "",
        ]
    )


def render_interface(
    name: str,
    methods: list,
    root_namespace: str,
    namespace_suffix: str,
    using_namespace: str,
) -> str:
    method_lines: List[str] = []
    for sig in methods:
        method_lines.append(f"    {sig};")
    return "\n".join(
        [
            f"using {using_namespace};",
            "",
            f"namespace {root_namespace}.{namespace_suffix};",
            "",
            f"public interface {name}",
            "{",
            "\n".join(method_lines),
            "}",
            "",
        ]
    )
