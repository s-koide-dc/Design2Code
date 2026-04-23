from typing import List


def build_validation_guards(
    dto_name: str,
    var_name: str,
    validation_rules: dict,
    field_types: dict,
    validation_templates: dict,
    return_action: str,
) -> list:
    guards: List[str] = []
    for key, rules in (validation_rules or {}).items():
        parts = key.split(".")
        if len(parts) != 2:
            continue
        dto_key, field = parts
        if dto_key != dto_name:
            continue
        field_type = field_types.get(field, "string")
        for rule in rules:
            if rule == "required":
                if field_type != "string":
                    continue
                tmpl = validation_templates.get("required.string")
                if tmpl:
                    guards.append(tmpl.replace("{Var}", var_name).replace("{Field}", field))
            elif rule.startswith("max_len="):
                size = rule.split("=", 1)[1]
                if size.isdigit():
                    if field_type == "string":
                        tmpl = validation_templates.get("max_len")
                        if tmpl:
                            guards.append(tmpl.replace("{Var}", var_name).replace("{Field}", field).replace("{Max}", size))
            elif rule.startswith("min_len="):
                size = rule.split("=", 1)[1]
                if size.isdigit():
                    if field_type == "string":
                        tmpl = validation_templates.get("min_len")
                        if tmpl:
                            guards.append(tmpl.replace("{Var}", var_name).replace("{Field}", field).replace("{Min}", size))
            elif rule.startswith("contains="):
                token = rule.split("=", 1)[1]
                if token:
                    if field_type == "string":
                        tmpl = validation_templates.get("contains")
                        if tmpl:
                            guards.append(tmpl.replace("{Var}", var_name).replace("{Field}", field).replace("{Token}", token))
            elif rule.startswith("min_value="):
                value = rule.split("=", 1)[1]
                tmpl = validation_templates.get("min_value")
                if tmpl:
                    guards.append(tmpl.replace("{Var}", var_name).replace("{Field}", field).replace("{Min}", value))
            elif rule.startswith("max_value="):
                value = rule.split("=", 1)[1]
                tmpl = validation_templates.get("max_value")
                if tmpl:
                    guards.append(tmpl.replace("{Var}", var_name).replace("{Field}", field).replace("{Max}", value))
    if return_action != "return null;":
        return [guard.replace("return null;", return_action) for guard in guards]
    return guards


def build_service_validation_guards(
    dto_name: str,
    var_name: str,
    validation_rules: dict,
    field_types: dict,
    validation_templates: dict,
) -> list:
    return build_validation_guards(dto_name, var_name, validation_rules, field_types, validation_templates, "return null;")


def build_controller_validation_guards(
    dto_name: str,
    var_name: str,
    validation_rules: dict,
    field_types: dict,
    validation_templates: dict,
) -> list:
    guards = build_validation_guards(dto_name, var_name, validation_rules, field_types, validation_templates, "return BadRequest();")
    if var_name:
        guards = [f"if ({var_name} == null) return BadRequest();"] + guards
    return guards
