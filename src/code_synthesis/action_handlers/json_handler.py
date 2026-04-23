from typing import List, Dict, Any


def handle_json(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any]) -> List[Dict[str, Any]]:
    new_p = action_synthesizer.synthesizer._copy_path(path)
    intent = node.get("intent")
    target_entity = node.get("target_entity", "Item")
    output_type = node.get("output_type")
    is_collection = node.get("cardinality") == "COLLECTION"

    semantic_roles = action_synthesizer._get_semantic_roles(node)
    source_var = semantic_roles.get("json_var") or semantic_roles.get("source_var")
    if not source_var:
        source_var = path.get("active_scope_item")
    if not source_var:
        res = action_synthesizer.semantic_binder._resolve_source_var(node, path, "string")
        if res:
            v_name, bridge = res
            source_var = bridge.replace("{var}", v_name) if bridge else v_name
    if not source_var:
        path_val = semantic_roles.get("path")
        if path_val:
            method_sig = {"params": [{"name": "path", "type": "string", "role": "path"}]}
            params = action_synthesizer.semantic_binder.bind_parameters(method_sig, node, path)
            if params:
                json_var = action_synthesizer.stmt_builder.get_semantic_var_name(
                    node,
                    "string",
                    "json",
                    new_p,
                    prefix="json",
                    role="content"
                )
                new_p["statements"].append({
                    "type": "raw",
                    "code": f"var {json_var} = File.ReadAllText({params[0]});",
                    "node_id": node.get("id"),
                    "intent": "FILE_IO"
                })
                new_p.setdefault("type_to_vars", {}).setdefault("string", []).append({
                    "var_name": json_var,
                    "node_id": node.get("id"),
                    "role": "content",
                    "target_entity": "string"
                })
                new_p["active_scope_item"] = json_var
                new_p.setdefault("all_usings", set()).add("System.IO")
                source_var = json_var
    if not source_var:
        source_var = "\"{}\""

    if not output_type or output_type == "string":
        if is_collection:
            output_type = f"List<{target_entity}>"
        else:
            output_type = target_entity

    base_name = semantic_roles.get("result_var") or ("items" if "List<" in output_type or "IEnumerable" in output_type else "item")
    existing_vars = new_p.get("type_to_vars", {}).get(output_type, [])
    result_var = existing_vars[-1].get("var_name") if existing_vars else None
    if not result_var:
        result_var = action_synthesizer.stmt_builder.get_semantic_var_name(
            node,
            output_type,
            base_name,
            new_p,
            prefix=base_name,
            role="data"
        )

    empty_expr = None
    if is_collection:
        type_system = action_synthesizer.type_system
        normalized = type_system.normalize_type(output_type)
        if normalized.endswith("[]"):
            inner = normalized[:-2].strip() or target_entity
            empty_expr = f"Array.Empty<{inner}>()"
            new_p.setdefault("all_usings", set()).add("System")
        else:
            base = normalized.split("<", 1)[0]
            inner = type_system.extract_generic_inner(normalized) or target_entity
            if base in ["IEnumerable", "ICollection", "IList", "IQueryable"]:
                empty_expr = f"Enumerable.Empty<{inner}>()"
                new_p.setdefault("all_usings", set()).add("System.Linq")
            elif base == "List":
                empty_expr = f"new {normalized}()"

    assignment_prefix = ""
    deserialize_code = f"{assignment_prefix}{result_var} = JsonSerializer.Deserialize<{output_type}>({source_var});"
    if empty_expr:
        deserialize_code = f"{assignment_prefix}{result_var} = JsonSerializer.Deserialize<{output_type}>({source_var}) ?? {empty_expr};"

    stmt = {
        "type": "raw",
        "code": deserialize_code,
        "node_id": node.get("id"),
        "intent": intent,
        "out_var": result_var,
        "var_type": output_type
    }
    wrapped_stmt = action_synthesizer.stmt_builder.wrap_with_try_catch(
        stmt,
        intent,
        "JsonSerializer.Deserialize",
        new_p
    )
    if isinstance(wrapped_stmt, list):
        new_p["statements"].extend(wrapped_stmt)
    else:
        new_p["statements"].append(wrapped_stmt)
    if not existing_vars:
        new_p.setdefault("type_to_vars", {}).setdefault(output_type, []).append({
            "var_name": result_var,
            "node_id": node.get("id"),
            "semantic_role": "data"
        })
    new_p["active_scope_item"] = result_var
    new_p.setdefault("all_usings", set()).add("System.Text.Json")
    if "List<" in output_type:
        new_p.setdefault("all_usings", set()).add("System.Collections.Generic")
    if target_entity and target_entity != "Item":
        action_synthesizer.stmt_builder.register_entity(target_entity, new_p)
    new_p.setdefault("consumed_ids", set()).add(node.get("id"))
    new_p["completed_nodes"] += 1
    return [new_p]
