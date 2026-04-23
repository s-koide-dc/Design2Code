from typing import Dict, List


def _build_valid_assignments(field_types: Dict[str, str], validation_rules: dict, create_dto: str) -> Dict[str, str]:
    valid_assignments: Dict[str, str] = {}
    for field, typ in field_types.items():
        rules = validation_rules.get(f"{create_dto}.{field}", [])
        if typ == "string":
            contains_token = ""
            min_len = None
            max_len = None
            for rule in rules:
                if rule.startswith("contains="):
                    contains_token = rule.split("=", 1)[1]
                elif rule.startswith("min_len="):
                    size = rule.split("=", 1)[1]
                    if size.isdigit():
                        min_len = int(size)
                elif rule.startswith("max_len="):
                    size = rule.split("=", 1)[1]
                    if size.isdigit():
                        max_len = int(size)
            value = "Value"
            if contains_token:
                value = f"Value{contains_token}"
            if min_len is not None and len(value) < min_len:
                value = value + ("a" * (min_len - len(value)))
            if max_len is not None and len(value) > max_len:
                value = value[:max_len]
            valid_assignments[field] = f"\"{value}\""
        elif typ in ["int", "long"]:
            valid_assignments[field] = "1"
        elif typ == "decimal":
            valid_assignments[field] = "1m"
        elif typ == "bool":
            valid_assignments[field] = "true"
        elif typ == "DateTime":
            valid_assignments[field] = "DateTime.UtcNow"
    return valid_assignments


def _build_invalid_test(
    create_dto: str,
    service_name: str,
    create_service: str,
    validation_rules: dict,
    field_types: Dict[str, str],
    valid_assignments: Dict[str, str],
) -> str:
    invalid_test = ""
    if any(k.startswith(create_dto + ".") for k in validation_rules.keys()):
        invalid_assignments = dict(valid_assignments)
        for field, typ in field_types.items():
            rules = validation_rules.get(f"{create_dto}.{field}")
            if not rules:
                continue
            if "required" in rules and typ == "string":
                invalid_assignments[field] = "\"\""
                break
            if any(r.startswith("contains=") for r in rules) and typ == "string":
                invalid_assignments[field] = "\"invalid\""
                break
            if any(r.startswith("max_len=") for r in rules) and typ == "string":
                size = [r for r in rules if r.startswith("max_len=")][0].split("=", 1)[1]
                if size.isdigit():
                    invalid_assignments[field] = f"new string('a', {int(size) + 1})"
                    break
            if "required" in rules and typ != "string":
                invalid_assignments[field] = "default"
                break
        invalid_init = "{ " + ", ".join([f"{k} = {v}" for k, v in invalid_assignments.items()]) + " }"
        invalid_test = "\n".join([
            "    [Fact]",
            f"    public void {create_service}_InvalidRequest_ReturnsNull()",
            "    {",
            "        var repo = new FakeRepo();",
            f"        var service = new {service_name}(repo);",
            f"        var req = new {create_dto} {invalid_init};",
            f"        var result = service.{create_service}(req);",
            "        Assert.Null(result);",
            "    }",
            "",
        ])
    return invalid_test


def build_service_test_context(
    service_name: str,
    repo_name: str,
    entity_name: str,
    create_dto: str,
    entity_plural: str,
    crud_template: dict,
    validation_rules: dict,
    field_types: Dict[str, str],
    id_type: str,
    entity_fields: List[str],
    test_cases: Dict[str, List[Dict[str, str]]] | None = None,
) -> Dict[str, str]:
    list_service = crud_template.get("List", {}).get("Service", "Get{EntityPlural}").replace("{Entity}", entity_name).replace("{EntityPlural}", entity_plural)
    get_service = crud_template.get("GetById", {}).get("Service", "Get{Entity}ById").replace("{Entity}", entity_name).replace("{EntityPlural}", entity_plural)
    create_service = crud_template.get("Create", {}).get("Service", "Create{Entity}").replace("{Entity}", entity_name).replace("{EntityPlural}", entity_plural)
    update_service = crud_template.get("Update", {}).get("Service", "Update{Entity}").replace("{Entity}", entity_name).replace("{EntityPlural}", entity_plural)
    delete_service = crud_template.get("Delete", {}).get("Service", "Delete{Entity}").replace("{Entity}", entity_name).replace("{EntityPlural}", entity_plural)
    repo_list = crud_template.get("List", {}).get("Repository", "FetchAll")
    repo_get = crud_template.get("GetById", {}).get("Repository", "FetchById")
    repo_create = crud_template.get("Create", {}).get("Repository", "Insert")
    repo_update = crud_template.get("Update", {}).get("Repository", "Update")
    repo_delete = crud_template.get("Delete", {}).get("Repository", "Delete")

    valid_assignments = _build_valid_assignments(field_types, validation_rules, create_dto)
    valid_init = "{ " + ", ".join([f"{k} = {v}" for k, v in valid_assignments.items()]) + " }" if valid_assignments else "{ }"
    invalid_test = _build_invalid_test(create_dto, service_name, create_service, validation_rules, field_types, valid_assignments)

    entity_init = ", ".join([f"{f} = entity.{f}" for f in entity_fields])
    update_assignments = "\n".join([f"            existing.{f} = entity.{f}!;" for f in entity_fields])

    structured_cases = []
    if test_cases:
        for method_name, cases in test_cases.items():
            for case in cases or []:
                if not isinstance(case, dict):
                    continue
                case_method = case.get("method") or method_name
                name = case.get("name")
                arrange = case.get("arrange")
                act = case.get("act")
                asserts = case.get("assert")
                case_type = case.get("type")
                scenario = case.get("scenario")
                if not case_method:
                    continue
                if not act and not case_type:
                    continue
                structured_cases.append({
                    "method": case_method,
                    "name": name,
                    "arrange": arrange if isinstance(arrange, list) else [],
                    "act": act if isinstance(act, str) else "",
                    "assert": asserts if isinstance(asserts, list) else [],
                    "type": case_type,
                    "scenario": scenario,
                })

    return {
        "ServiceClass": service_name,
        "RepositoryInterface": "I" + repo_name,
        "EntityClass": entity_name,
        "CreateDto": create_dto,
        "IdType": id_type,
        "IdValue": "default" if id_type != "string" else "\"\"",
        "RepoList": repo_list,
        "RepoGet": repo_get,
        "RepoCreate": repo_create,
        "RepoUpdate": repo_update,
        "RepoDelete": repo_delete,
        "ListMethod": list_service,
        "GetMethod": get_service,
        "CreateMethod": create_service,
        "UpdateMethod": update_service,
        "DeleteMethod": delete_service,
        "EntityInit": (", " + entity_init) if entity_init else "",
        "UpdateAssignments": update_assignments or "            return existing;",
        "ValidRequestInit": valid_init,
        "InvalidTest": invalid_test,
        "StructuredTestCases": structured_cases,
    }
