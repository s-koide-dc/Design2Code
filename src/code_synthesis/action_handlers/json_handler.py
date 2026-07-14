from typing import List, Dict, Any
from src.utils.semantic_intents import INTENT_FILE_IO


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
                error_policy = str(
                    semantic_roles.get("error_policy") or "return_default"
                ).strip().lower()
                if error_policy not in {"return_default", "rethrow", "continue"}:
                    return action_synthesizer._unresolved_path(
                        path,
                        node,
                        "invalid_error_policy",
                        details={"error_policy": error_policy},
                    )
                json_var = action_synthesizer.stmt_builder.get_semantic_var_name(
                    node,
                    "string",
                    "json",
                    new_p,
                    prefix="json",
                    role="content"
                )
                if error_policy == "return_default":
                    helper_name = action_synthesizer.stmt_builder.ensure_text_file_read_helper(new_p)
                    success_var = action_synthesizer.stmt_builder.get_semantic_var_name(
                        node,
                        "bool",
                        "fileReadSucceeded",
                        new_p,
                        prefix=f"{json_var}Read",
                        role="status",
                    )
                    new_p["statements"].append({
                        "type": "raw",
                        "code": f"bool {success_var} = true;",
                        "node_id": f"{node.get('id')}_read_status",
                        "intent": INTENT_FILE_IO,
                    })
                    new_p["statements"].append({
                        "type": "call",
                        "method": helper_name,
                        "call_expr": f"{helper_name}({params[0]}, out {success_var})",
                        "args": [params[0], f"out {success_var}"],
                        "node_id": node.get("id"),
                        "intent": INTENT_FILE_IO,
                        "out_var": json_var,
                        "var_type": "string",
                    })
                    failure_action = action_synthesizer.stmt_builder._catch_action_for_policy(
                        path=new_p,
                        error_policy=error_policy,
                        has_hoisted_result=True,
                        hoisted_result_var=json_var,
                        hoisted_result_type="string",
                    )
                    if failure_action:
                        new_p["statements"].append({
                            "type": "raw",
                            "code": f"if (!{success_var}) {failure_action}",
                            "node_id": f"{node.get('id')}_read_failure",
                            "intent": INTENT_FILE_IO,
                        })
                else:
                    file_stmt = {
                        "type": "raw",
                        "code": f"{json_var} = File.ReadAllText({params[0]});",
                        "node_id": node.get("id"),
                        "intent": INTENT_FILE_IO,
                        "out_var": json_var,
                        "var_type": "string",
                    }
                    new_p["statements"].append(
                        action_synthesizer.stmt_builder.wrap_with_try_catch(
                            file_stmt,
                            INTENT_FILE_IO,
                            "File.ReadAllText",
                            new_p,
                            error_policy=error_policy,
                        )
                    )
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

    semantic_roles = action_synthesizer._get_semantic_roles(node)
    error_policy = str(
        semantic_roles.get("error_policy") or "return_default"
    ).strip().lower()
    if error_policy not in {"return_default", "rethrow", "continue"}:
        return action_synthesizer._unresolved_path(
            path,
            node,
            "invalid_error_policy",
            details={"error_policy": error_policy},
        )

    if error_policy == "return_default" and empty_expr:
        helper_name = action_synthesizer.stmt_builder.ensure_json_deserialize_helper(
            new_p,
            output_type=output_type,
            fallback_expr=empty_expr,
        )
        success_var = action_synthesizer.stmt_builder.get_semantic_var_name(
            node,
            "bool",
            "jsonDeserializeSucceeded",
            new_p,
            prefix=f"{result_var}Deserialized",
            role="status",
        )
        new_p["statements"].append({
            "type": "raw",
            "code": f"bool {success_var} = true;",
            "node_id": f"{node.get('id')}_deserialize_status",
        })
        new_p["statements"].append({
            "type": "call",
            "method": helper_name,
            "call_expr": f"{helper_name}({source_var}, out {success_var})",
            "args": [source_var, f"out {success_var}"],
            "node_id": node.get("id"),
            "intent": intent,
            "out_var": result_var,
            "var_type": output_type,
            "is_assignment_only": bool(existing_vars),
        })
        failure_action = action_synthesizer.stmt_builder._catch_action_for_policy(
            path=new_p,
            error_policy=error_policy,
            has_hoisted_result=True,
            hoisted_result_var=result_var,
            hoisted_result_type=output_type,
        )
        if failure_action:
            new_p["statements"].append({
                "type": "raw",
                "code": f"if (!{success_var}) {failure_action}",
                "node_id": f"{node.get('id')}_deserialize_failure",
                "intent": intent,
            })
    else:
        deserialize_code = f"{result_var} = JsonSerializer.Deserialize<{output_type}>({source_var});"
        if empty_expr:
            deserialize_code = f"{result_var} = JsonSerializer.Deserialize<{output_type}>({source_var}) ?? {empty_expr};"

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
            new_p,
            error_policy=error_policy,
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
    if any(generic in output_type for generic in ("List<", "IEnumerable<", "ICollection<", "IList<")):
        new_p.setdefault("all_usings", set()).add("System.Collections.Generic")
    if target_entity and target_entity != "Item":
        action_synthesizer.stmt_builder.register_entity(target_entity, new_p)
    new_p.setdefault("consumed_ids", set()).add(node.get("id"))
    new_p["completed_nodes"] += 1
    return [new_p]
