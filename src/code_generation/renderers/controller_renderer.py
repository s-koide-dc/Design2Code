from typing import List


def render_controller(
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
    action_lines: List[str] = []
    guard_lines = validation_guards or []
    list_action = action_names.get("list", "GetItems")
    get_action = action_names.get("get", "GetItemById")
    create_action = action_names.get("create", "CreateItem")
    update_action = action_names.get("update", "UpdateItem")
    delete_action = action_names.get("delete", "DeleteItem")
    list_call = service_calls.get("list", "GetItems")
    get_call = service_calls.get("get", "GetItemById")
    create_call = service_calls.get("create", "CreateItem")
    update_call = service_calls.get("update", "UpdateItem")
    delete_call = service_calls.get("delete", "DeleteItem")
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
        if path.startswith("/" + route_base):
            path = path[len("/" + route_base) :]
        if path.startswith("/"):
            path = path[1:]
        if not path:
            path = ""
        action_lines.append(f"    [{attr}(\"{path}\")]")
        if "{id}" in path:
            if method == "PUT":
                action_lines.append(f"    public IActionResult {update_action}({id_type} id, [FromBody] {create_dto} req)")
                action_lines.append("    {")
                for guard in guard_lines:
                    action_lines.append(f"        {guard}")
                action_lines.append(f"        var result = _service.{update_call}(id, req);")
                action_lines.append("        return result == null ? NotFound() : Ok(result);")
                action_lines.append("    }")
            elif method == "DELETE":
                action_lines.append(f"    public IActionResult {delete_action}({id_type} id)")
                action_lines.append("    {")
                action_lines.append(f"        return _service.{delete_call}(id) ? Ok() : NotFound();")
                action_lines.append("    }")
            else:
                action_lines.append(f"    public IActionResult {get_action}({id_type} id)")
                action_lines.append("    {")
                action_lines.append(f"        var result = _service.{get_call}(id);")
                action_lines.append("        return result == null ? NotFound() : Ok(result);")
                action_lines.append("    }")
        elif method == "POST":
            action_lines.append(f"    public IActionResult {create_action}([FromBody] {create_dto} req)")
            action_lines.append("    {")
            for guard in guard_lines:
                action_lines.append(f"        {guard}")
            action_lines.append(f"        var result = _service.{create_call}(req);")
            action_lines.append("        return result == null ? BadRequest() : Ok(result);")
            action_lines.append("    }")
        else:
            action_lines.append(f"    public IActionResult {list_action}()")
            action_lines.append("    {")
            action_lines.append(f"        return Ok(_service.{list_call}());")
            action_lines.append("    }")
    return _render_controller_from_actions(name, service_iface, route_base, action_lines, root_namespace)


def render_controller_from_actions(
    name: str,
    service_iface: str,
    route_base: str,
    action_lines: list,
    root_namespace: str,
) -> str:
    return _render_controller_from_actions(name, service_iface, route_base, action_lines, root_namespace)


def _render_controller_from_actions(
    name: str,
    service_iface: str,
    route_base: str,
    action_lines: list,
    root_namespace: str,
) -> str:
    return "\n".join(
        [
            "using Microsoft.AspNetCore.Mvc;",
            f"using {root_namespace}.DTO;",
            f"using {root_namespace}.Services;",
            "",
            f"namespace {root_namespace}.Controllers;",
            "",
            "[ApiController]",
            f"[Route(\"{route_base}\")]",
            f"public class {name} : ControllerBase",
            "{",
            f"    private readonly {service_iface} _service;",
            "",
            f"    public {name}({service_iface} service)",
            "    {",
            "        _service = service;",
            "    }",
            "",
            "\n".join(action_lines),
            "}",
            "",
        ]
    )
