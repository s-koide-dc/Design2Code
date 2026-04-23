from typing import List, Dict, Any

from src.code_synthesis.action_handlers.action_utils import to_csharp_string_literal
from src.utils.text_parser import extract_first_quoted_literal


def process_transform_ops(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any], ops: List[str]) -> List[Dict[str, Any]] | None:
    new_p = action_synthesizer.synthesizer._copy_path(path)
    intent = node.get("intent")
    output_type = node.get("output_type", "string")
    ops_set = {o.lower() for o in ops}
    source_var = path.get("active_scope_item")
    transform_ops = action_synthesizer.ukb.get("transform_ops", {}) if (action_synthesizer.ukb and hasattr(action_synthesizer.ukb, "get")) else {}
    if not source_var:
        res = action_synthesizer.semantic_binder._resolve_source_var(node, path, "string")
        if res:
            v_name, bridge = res
            source_var = bridge.replace("{var}", v_name) if bridge else v_name
    if "trim_upper" in ops_set and not source_var:
        src_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string", "input", new_p, prefix="input", role="content")
        new_p["statements"].append({"type": "raw", "code": f"var {src_var} = Console.ReadLine();", "node_id": node.get("id"), "intent": intent})
        new_p.setdefault("type_to_vars", {}).setdefault("string", []).append({"var_name": src_var, "node_id": node.get("id"), "role": "content", "target_entity": "string"})
        source_var = src_var

    for op in ops_set:
        op_cfg = transform_ops.get(op)
        if not op_cfg:
            continue
        if op == "split_lines" and not source_var:
            continue
        if op == "csv_serialize":
            dict_type = "Dictionary<string, decimal>"
            dict_vars = path.get("type_to_vars", {}).get(dict_type, [])
            if not dict_vars:
                continue
            source_var = dict_vars[-1]["var_name"]

        out_type = op_cfg.get("output_type", output_type)
        out_name = op_cfg.get("output_name", "result")
        out_role = op_cfg.get("output_role", "content")
        out_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, out_type, out_name, new_p, prefix=out_name, role=out_role)
        code_template = op_cfg.get("code", "{out} = {src};")
        code = code_template.format(out=out_var, src=source_var, v0="{v0}", v1="{v1}")
        code = code.strip()
        if code.endswith(";"):
            code = code[:-1]

        if op == "format_kv":
            string_vars = path.get("type_to_vars", {}).get("string", [])
            if len(string_vars) < 2:
                continue
            mode_var = string_vars[-2]["var_name"]
            region_var = string_vars[-1]["var_name"]
            code = f"{out_var} = $\"MODE={{{mode_var}}}, REGION={{{region_var}}}\";"
            code_template = None

        consumes_vars = [source_var] if source_var else []
        if op == "format_kv":
            consumes_vars = [mode_var, region_var]
        if code_template is None:
            new_p["statements"].append({"type": "raw", "code": f"var {code}", "node_id": node.get("id"), "intent": intent, "out_var": out_var, "consumes": consumes_vars})
        else:
            new_p["statements"].append({"type": "raw", "code": f"var {code};", "node_id": node.get("id"), "intent": intent, "out_var": out_var, "consumes": consumes_vars})
        new_p.setdefault("type_to_vars", {}).setdefault(out_type, []).append({"var_name": out_var, "node_id": node.get("id"), "role": out_role, "target_entity": "string"})
        for u in op_cfg.get("usings", []):
            new_p.setdefault("all_usings", set()).add(u)
        new_p["active_scope_item"] = out_var
        new_p.setdefault("consumed_ids", set()).add(node.get("id"))
        new_p["completed_nodes"] += 1
        return [new_p]
    return None


def process_display_transform_specialized(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any]) -> List[Dict[str, Any]] | None:
    intent = node.get("intent")
    entity = node.get("target_entity", "Item")
    output_type = node.get("output_type", "void")
    text = node.get("original_text", "")
    semantic_roles = action_synthesizer._get_semantic_roles(node)
    display_scope = semantic_roles.get("display_scope")
    display_after_loop = str(display_scope).lower() in ["after_loop", "afterloop", "post_loop", "postloop"]
    ops = semantic_roles.get("ops", []) or []
    if intent == "TRANSFORM" and ops:
        res = process_transform_ops(action_synthesizer, node, path, ops)
        if res is not None:
            return res
    if intent == "TRANSFORM":
        return_value = semantic_roles.get("return_value")
        if return_value:
            new_p = action_synthesizer.synthesizer._copy_path(path)
            all_vars = {v.get("var_name") for vs in new_p.get("type_to_vars", {}).values() for v in vs if isinstance(v, dict)}
            if return_value in all_vars:
                return_expr = return_value
            else:
                return_expr = to_csharp_string_literal(return_value)
            new_p["statements"].append({"type": "raw", "code": f"return {return_expr};", "node_id": node.get("id"), "intent": intent})
            new_p.setdefault("consumed_ids", set()).add(node.get("id"))
            new_p["completed_nodes"] += 1
            return [new_p]
    explicit_message = semantic_roles.get("content") or semantic_roles.get("message") or semantic_roles.get("notification")
    if intent == "DISPLAY" and explicit_message:
        msg_literal = to_csharp_string_literal(explicit_message)
        new_p = action_synthesizer.synthesizer._copy_path(path)
        stmt = {"type": "raw", "code": f"Console.WriteLine({msg_literal});", "node_id": node.get("id"), "intent": intent, "semantic_role": "notification"}
        if display_after_loop and new_p.get("in_loop"):
            stmt = dict(stmt)
            stmt["deferred_from"] = node.get("id")
            new_p.setdefault("deferred_statements", []).append(stmt)
        else:
            new_p["statements"].append(stmt)
        new_p.setdefault("consumed_ids", set()).add(node.get("id"))
        new_p["completed_nodes"] += 1
        return [new_p]
    if intent == "DISPLAY" and not explicit_message:
        literal = extract_first_quoted_literal(text)
        if literal:
            msg_literal = to_csharp_string_literal(literal)
            new_p = action_synthesizer.synthesizer._copy_path(path)
            stmt = {"type": "raw", "code": f"Console.WriteLine({msg_literal});", "node_id": node.get("id"), "intent": intent, "semantic_role": "notification"}
            if display_after_loop and new_p.get("in_loop"):
                stmt = dict(stmt)
                stmt["deferred_from"] = node.get("id")
                new_p.setdefault("deferred_statements", []).append(stmt)
            else:
                new_p["statements"].append(stmt)
            new_p.setdefault("consumed_ids", set()).add(node.get("id"))
            new_p["completed_nodes"] += 1
            return [new_p]
    if intent == "DISPLAY" and "display_names" in ops:
        new_p = action_synthesizer.synthesizer._copy_path(path)
        active_item = path.get("active_scope_item")
        if path.get("in_loop") and active_item:
            stmt = {"type": "raw", "code": f"Console.WriteLine({active_item}.Name);", "node_id": node.get("id"), "intent": intent}
            if display_after_loop and new_p.get("in_loop"):
                stmt = dict(stmt)
                stmt["deferred_from"] = node.get("id")
                new_p.setdefault("deferred_statements", []).append(stmt)
            else:
                new_p["statements"].append(stmt)
            new_p.setdefault("consumed_ids", set()).add(node.get("id"))
            new_p["completed_nodes"] += 1
            return [new_p]
        collection_var = None
        for vt, vars_list in path.get("type_to_vars", {}).items():
            if any(k in vt for k in ["IEnumerable<", "List<", "[]"]):
                if vars_list:
                    collection_var = vars_list[-1]["var_name"]
        if not collection_var:
            collection_var = active_item
        if not collection_var:
            res = action_synthesizer.semantic_binder._resolve_source_var(node, path, entity)
            if res and res[0]:
                v_name, bridge = res
                collection_var = bridge.replace("{var}", v_name) if bridge else v_name
        if not collection_var:
            collection_var = "items"
        item_name = action_synthesizer.stmt_builder.get_semantic_var_name(node, entity, "item", new_p, prefix="item", role="item")
        report_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string", "report", new_p, role="content")
        new_p["statements"].append({"type": "raw", "code": f"var {report_var} = string.Join(Environment.NewLine, {collection_var}.Select({item_name} => {item_name}.Name));", "node_id": node.get("id"), "intent": intent})
        stmt = {"type": "raw", "code": f"Console.WriteLine({report_var});", "node_id": node.get("id"), "intent": intent}
        if display_after_loop and new_p.get("in_loop"):
            stmt = dict(stmt)
            stmt["deferred_from"] = node.get("id")
            new_p.setdefault("deferred_statements", []).append(stmt)
        else:
            new_p["statements"].append(stmt)
        new_p.setdefault("type_to_vars", {}).setdefault("string", []).append({"var_name": report_var, "node_id": node.get("id"), "role": "content", "target_entity": "string"})
        new_p["active_scope_item"] = report_var
        new_p["active_scope_item_role"] = "report_content"
        new_p.setdefault("all_usings", set()).add("System.Linq")
        new_p.setdefault("consumed_ids", set()).add(node.get("id"))
        new_p["completed_nodes"] += 1
        return [new_p]
    is_notification = action_synthesizer._has_tag(text, "notification")
    var_to_display = path.get("active_scope_item")
    explicit_display_var = semantic_roles.get("display_var") or semantic_roles.get("display_target")
    display_prop = semantic_roles.get("property") or semantic_roles.get("field") or semantic_roles.get("display_property")
    if not var_to_display or var_to_display == "result":
        vars_of_type = path.get("type_to_vars", {}).get(entity, [])
        if vars_of_type:
            var_to_display = vars_of_type[-1]["var_name"]
        else:
            res = action_synthesizer.semantic_binder._resolve_source_var(node, path, entity)
            if res:
                v_name, bridge = res
                var_to_display = bridge.replace("{var}", v_name) if bridge else v_name
            else:
                var_to_display = "item"
    if explicit_display_var:
        var_to_display = explicit_display_var
    resolved_display_prop = None
    if display_prop:
        props = path.get("poco_defs", {}).get(entity, {})
        if props:
            resolved_display_prop = action_synthesizer.semantic_binder._resolve_prop(
                str(display_prop),
                "string",
                props,
                node
            )
        if not resolved_display_prop:
            resolved_display_prop = str(display_prop)
    var_type = None
    for vt, vars_list in path.get("type_to_vars", {}).items():
        if any(v.get("var_name") == var_to_display for v in vars_list):
            var_type = vt
            break
    if intent == "DISPLAY" and is_notification and not explicit_message and output_type != "string":
        primitive_types = ["int", "long", "decimal", "double", "float", "bool", "string"]
        prefer_value = entity in primitive_types or output_type in primitive_types
        if prefer_value and var_to_display and var_to_display != "result":
            new_p = action_synthesizer.synthesizer._copy_path(path)
            stmt = {"type": "raw", "code": f"Console.WriteLine({var_to_display});", "node_id": node.get("id"), "intent": intent, "semantic_role": "notification"}
            if display_after_loop and new_p.get("in_loop"):
                stmt = dict(stmt)
                stmt["deferred_from"] = node.get("id")
                new_p.setdefault("deferred_statements", []).append(stmt)
            else:
                new_p["statements"].append(stmt)
            new_p.setdefault("consumed_ids", set()).add(node.get("id"))
            new_p["completed_nodes"] += 1
            return [new_p]
        msg = "全ての処理が完了しました。" if "完了" in text else "処理結果を報告します。"
        new_p = action_synthesizer.synthesizer._copy_path(path)
        stmt = {"type": "raw", "code": f"Console.WriteLine(\"{msg}\");", "node_id": node.get("id"), "intent": intent, "semantic_role": "notification"}
        if display_after_loop and new_p.get("in_loop"):
            stmt = dict(stmt)
            stmt["deferred_from"] = node.get("id")
            new_p.setdefault("deferred_statements", []).append(stmt)
        else:
            new_p["statements"].append(stmt)
        new_p.setdefault("consumed_ids", set()).add(node.get("id"))
        new_p["completed_nodes"] += 1
        return [new_p]
    is_collection = node.get("cardinality") == "COLLECTION"
    if not is_collection and var_to_display:
        for vt, vars_list in path.get("type_to_vars", {}).items():
            if any(v.get("var_name") == var_to_display for v in vars_list):
                if "IEnumerable" in vt or "List" in vt or vt.endswith("[]"):
                    is_collection = True
                    break
    if intent == "DISPLAY" and is_collection and var_to_display:
        if output_type == "string":
            new_p = action_synthesizer.synthesizer._copy_path(path)
            item_type = entity if entity in path.get("poco_defs", {}) else "var"
            item_name = action_synthesizer.stmt_builder.get_semantic_var_name(node, item_type, "item", new_p, prefix="item", role="item")
            if resolved_display_prop:
                display_expr = f"{item_name}.{resolved_display_prop}"
            elif entity in path.get("poco_defs", {}):
                display_expr = action_synthesizer.stmt_builder.build_poco_display_expression(item_name, entity, new_p)
            else:
                display_expr = item_name
            report_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string", "report", new_p, role="content")
            new_p["statements"].append({"type": "raw", "code": f"var {report_var} = string.Join(Environment.NewLine, {var_to_display}.Select({item_name} => {display_expr}));", "node_id": node.get("id"), "intent": intent})
            new_p.setdefault("type_to_vars", {}).setdefault("string", []).append({"var_name": report_var, "node_id": node.get("id"), "role": "content", "target_entity": "string"})
            new_p["active_scope_item"] = report_var
            new_p["active_scope_item_role"] = "report_content"
            new_p.setdefault("all_usings", set()).add("System.Linq")
            new_p.setdefault("consumed_ids", set()).add(node.get("id"))
            new_p["completed_nodes"] += 1
            return [new_p]
        new_p = action_synthesizer.synthesizer._copy_path(path)
        item_type = entity if entity in path.get("poco_defs", {}) else "var"
        item_name = action_synthesizer.stmt_builder.get_semantic_var_name(node, item_type, "item", new_p, prefix="item", role="item")
        if resolved_display_prop:
            display_expr = f"{item_name}.{resolved_display_prop}"
        elif entity in path.get("poco_defs", {}):
            display_expr = action_synthesizer.stmt_builder.build_poco_display_expression(item_name, entity, new_p)
        else:
            display_expr = item_name
        loop_stmt = {
            "type": "foreach",
            "source": var_to_display,
            "item_name": item_name,
            "var_type": item_type,
            "body": [{"type": "raw", "code": f"Console.WriteLine({display_expr});", "node_id": node.get("id"), "intent": intent}],
            "node_id": node.get("id"),
            "intent": intent,
        }
        if display_after_loop and new_p.get("in_loop"):
            loop_stmt = dict(loop_stmt)
            loop_stmt["deferred_from"] = node.get("id")
            new_p.setdefault("deferred_statements", []).append(loop_stmt)
        else:
            new_p["statements"].append(loop_stmt)
        new_p.setdefault("all_usings", set()).add("System.Linq")
        new_p.setdefault("consumed_ids", set()).add(node.get("id"))
        new_p["completed_nodes"] += 1
        return [new_p]
    if intent == "DISPLAY" and var_to_display and output_type == "string":
        new_p = action_synthesizer.synthesizer._copy_path(path)
        if resolved_display_prop:
            stmt = {"type": "raw", "code": f"Console.WriteLine({var_to_display}.{resolved_display_prop});", "node_id": node.get("id"), "intent": intent}
        else:
            stmt = {"type": "raw", "code": f"Console.WriteLine({var_to_display});", "node_id": node.get("id"), "intent": intent}
        if display_after_loop and new_p.get("in_loop"):
            stmt = dict(stmt)
            stmt["deferred_from"] = node.get("id")
            new_p.setdefault("deferred_statements", []).append(stmt)
        else:
            new_p["statements"].append(stmt)
        new_p.setdefault("consumed_ids", set()).add(node.get("id"))
        new_p["completed_nodes"] += 1
        return [new_p]
    if intent == "DISPLAY" and var_to_display:
        new_p = action_synthesizer.synthesizer._copy_path(path)
        if resolved_display_prop:
            stmt = {"type": "raw", "code": f"Console.WriteLine({var_to_display}.{resolved_display_prop});", "node_id": node.get("id"), "intent": intent}
        else:
            stmt = {"type": "raw", "code": f"Console.WriteLine({var_to_display});", "node_id": node.get("id"), "intent": intent}
        if display_after_loop and new_p.get("in_loop"):
            stmt = dict(stmt)
            stmt["deferred_from"] = node.get("id")
            new_p.setdefault("deferred_statements", []).append(stmt)
        else:
            new_p["statements"].append(stmt)
        new_p.setdefault("consumed_ids", set()).add(node.get("id"))
        new_p["completed_nodes"] += 1
        return [new_p]
    if intent == "TRANSFORM":
        new_p = action_synthesizer.synthesizer._copy_path(path)
        if var_type and var_type not in ["string", "object", None] and var_to_display:
            new_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string", "result", new_p, role="content")
            new_p["statements"].append({"type": "raw", "code": f"var {new_var} = {var_to_display}.ToString();", "node_id": node.get("id"), "intent": intent})
            new_p.setdefault("type_to_vars", {}).setdefault("string", []).append({"var_name": new_var, "node_id": node.get("id"), "role": "content", "target_entity": "string"})
            new_p["active_scope_item"] = new_var
            new_p.setdefault("consumed_ids", set()).add(node.get("id"))
            new_p["completed_nodes"] += 1
            return [new_p]
        literal = extract_first_quoted_literal(text)
        string_vars = path.get("type_to_vars", {}).get("string", [])
        if literal and string_vars:
            parts = str(literal).split("...")
            placeholders = max(len(parts) - 1, 0)
            if placeholders > 0 and len(string_vars) >= placeholders:
                vars_in_order = [v["var_name"] for v in string_vars[-placeholders:]]
                expr_parts = []
                for idx, part in enumerate(parts):
                    expr_parts.append(part.replace("\"", "\"\""))
                    if idx < placeholders:
                        expr_parts.append(f"{{{vars_in_order[idx]}}}")
                expr = "$\"" + "".join(expr_parts) + "\""
                out_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string", "result", new_p, role="content")
                new_p["statements"].append({"type": "raw", "code": f"var {out_var} = {expr};", "node_id": node.get("id"), "intent": intent})
                new_p.setdefault("type_to_vars", {}).setdefault("string", []).append({"var_name": out_var, "node_id": node.get("id"), "role": "content", "target_entity": "string"})
                new_p["active_scope_item"] = out_var
                new_p.setdefault("consumed_ids", set()).add(node.get("id"))
                new_p["completed_nodes"] += 1
                return [new_p]
        if var_to_display and var_type == "string":
            out_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string", "result", new_p, role="content")
            new_p["statements"].append({"type": "raw", "code": f"var {out_var} = {var_to_display};", "node_id": node.get("id"), "intent": intent})
            new_p.setdefault("type_to_vars", {}).setdefault("string", []).append({"var_name": out_var, "node_id": node.get("id"), "role": "content", "target_entity": "string"})
            new_p["active_scope_item"] = out_var
            new_p.setdefault("consumed_ids", set()).add(node.get("id"))
            new_p["completed_nodes"] += 1
            return [new_p]
    return None
