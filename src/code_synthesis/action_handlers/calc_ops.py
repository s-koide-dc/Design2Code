from typing import List, Dict, Any

from src.code_synthesis.action_handlers.action_utils import is_known_state_property, to_csharp_string_literal
from src.utils.text_parser import extract_percentage_value


def process_csv_aggregate(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any]) -> List[Dict[str, Any]]:
    new_path = action_synthesizer.synthesizer._copy_path(path)
    intent = node.get("intent")
    dict_type = "Dictionary<string, decimal>"
    dict_vars = new_path.get("type_to_vars", {}).get(dict_type, [])
    if dict_vars:
        totals_var = dict_vars[-1]["var_name"]
    else:
        totals_var = action_synthesizer.stmt_builder.get_semantic_var_name(
            node,
            dict_type,
            "totals",
            new_path,
            prefix="totals",
            role="accumulator",
        )
        new_path.setdefault("hoisted_statements", []).append({
            "type": "raw",
            "code": f"var {totals_var} = new Dictionary<string, decimal>();",
            "node_id": f"hoist_{node.get('id')}",
            "intent": intent,
        })
        new_path.setdefault("type_to_vars", {}).setdefault(dict_type, []).append({
            "var_name": totals_var,
            "node_id": node.get("id"),
            "role": "accumulator",
        })
        new_path.setdefault("used_names", set()).add(totals_var)
        new_path.setdefault("all_usings", set()).add("System.Collections.Generic")

    line_var = path.get("active_scope_item")
    if not line_var:
        res = action_synthesizer.semantic_binder._resolve_source_var(node, path, "string")
        if res:
            v_name, bridge = res
            line_var = bridge.replace("{var}", v_name) if bridge else v_name
    if not line_var:
        return [new_path]

    columns_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string[]", "columns", new_path, prefix="columns", role="data")
    amount_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "decimal", "amount", new_path, prefix="amount", role="data")
    product_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "string", "product", new_path, prefix="productName", role="data")

    new_path["statements"].append({
        "type": "raw",
        "code": f"var {columns_var} = {line_var}.Split(',');",
        "node_id": node.get("id"),
        "intent": intent,
    })
    condition = f"{columns_var}.Length >= 2 && decimal.TryParse({columns_var}[1], out var {amount_var})"
    body = [
        {"type": "raw", "code": f"var {product_var} = {columns_var}[0].Trim();", "node_id": node.get("id"), "intent": intent},
        {"type": "raw", "code": f"if (!{totals_var}.ContainsKey({product_var})) {totals_var}[{product_var}] = 0m;", "node_id": node.get("id"), "intent": intent},
        {"type": "raw", "code": f"{totals_var}[{product_var}] += {amount_var};", "node_id": node.get("id"), "intent": intent},
    ]
    new_path["statements"].append({
        "type": "if",
        "condition": condition,
        "body": body,
        "else_body": [],
        "node_id": node.get("id"),
        "intent": intent,
    })
    new_path["active_scope_item"] = totals_var
    new_path.setdefault("consumed_ids", set()).add(node.get("id"))
    new_path["completed_nodes"] += 1
    return [new_path]


def process_calc_node(action_synthesizer, node: Dict[str, Any], path: Dict[str, Any]) -> List[Dict[str, Any]]:
    semantic_roles = action_synthesizer._get_semantic_roles(node)
    ops = semantic_roles.get("ops", []) or []
    if "aggregate_by_product" in ops:
        return process_csv_aggregate(action_synthesizer, node, path)
    new_path = action_synthesizer.synthesizer._copy_path(path)
    target_entity = node.get("target_entity", "Item")
    text = node.get("original_text", "")
    is_update_intent = action_synthesizer._has_tag(text, "update_intent")
    is_aggregation = action_synthesizer._has_tag(text, "aggregation_intent") or (semantic_roles.get("aggregation") is True)
    primitive_types = ["int", "long", "decimal", "double", "float", "bool", "string", "object"]
    effective_entity = target_entity
    if target_entity in primitive_types or target_entity not in new_path.get("poco_defs", {}):
        scope_item = path.get("active_scope_item")
        if scope_item:
            for vt, vs in path.get("type_to_vars", {}).items():
                if any(v.get("var_name") == scope_item for v in vs):
                    if vt not in primitive_types and vt in new_path.get("poco_defs", {}):
                        effective_entity = vt
                        break

    active_ent = None
    props = {}
    if path.get("active_scope_item"):
        if effective_entity in new_path.get("poco_defs", {}):
            active_ent = effective_entity
            props = new_path.get("poco_defs", {}).get(effective_entity, {})
        else:
            for ent, p_props in new_path.get("poco_defs", {}).items():
                if p_props and ent != "Item":
                    active_ent = ent
                    props = p_props
                    break
    if not props:
        schema = getattr(action_synthesizer.synthesizer, "entity_schema", {}) or {}
        for ent in schema.get("entities", []):
            if ent.get("name") == target_entity and isinstance(ent.get("properties"), dict):
                props = ent["properties"]
                break

    expr = action_synthesizer.semantic_binder.generate_logic_expression(
        node.get("semantic_map", {}),
        effective_entity,
        new_path,
        node=node,
    )
    if expr in ["true", "false", "", None]:
        expr = ""
    assignment_target = None
    logic_goals = node.get("semantic_map", {}).get("logic", [])
    calc_goals = [g for g in logic_goals if g.get("type") == "calculation"]

    target_hint = semantic_roles.get("target_hint") or semantic_roles.get("variable_hint")
    explicit_prop = semantic_roles.get("property") or semantic_roles.get("field") or semantic_roles.get("assignment_target")
    if explicit_prop and props:
        assignment_target = action_synthesizer.semantic_binder._resolve_prop(explicit_prop, "numeric", props, node)
    target_hint = target_hint or explicit_prop
    target_hint = target_hint if target_hint else None
    if calc_goals:
        for goal in calc_goals:
            if not target_hint:
                target_hint = goal.get("target_hint") or goal.get("variable_hint")
            if target_hint and not assignment_target:
                assignment_target = action_synthesizer.semantic_binder._resolve_prop(target_hint, "numeric", props, node)
            if assignment_target:
                break

    specialized_assignment = None
    datetime_hint = semantic_roles.get("datetime")
    if datetime_hint in ["now", "datetime_now", "current", "local"]:
        specialized_assignment = "DateTime.Now"
    elif datetime_hint in ["utc_now", "utc", "datetime_utc_now"]:
        specialized_assignment = "DateTime.UtcNow"
    if not specialized_assignment:
        if action_synthesizer._has_tag(text, "datetime_now"):
            specialized_assignment = "DateTime.Now"
        elif action_synthesizer._has_tag(text, "datetime_utc_now"):
            specialized_assignment = "DateTime.UtcNow"

    if not assignment_target and specialized_assignment:
        if action_synthesizer._has_tag(text, "last_hint"):
            assignment_target = action_synthesizer.semantic_binder._resolve_prop("LastLoginAt", "datetime", props, node) or "LastLoginAt"
        else:
            assignment_target = action_synthesizer.semantic_binder._resolve_prop("UpdatedAt", "datetime", props, node) or "UpdatedAt"

    def _format_decimal_literal(value: Any) -> str:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped.endswith("m") else f"{stripped}m"
        if isinstance(value, int):
            return f"{value}m"
        if isinstance(value, float):
            return f"{value}m"
        return "0m"

    def _resolve_prop_name(prop_hint: str) -> str:
        if not prop_hint:
            return ""
        if props:
            resolved = action_synthesizer.semantic_binder._resolve_prop(prop_hint, "numeric", props, node)
            if resolved:
                return resolved
        return prop_hint

    rate_rules = semantic_roles.get("rate_rules")
    if not rate_rules and isinstance(semantic_roles, dict):
        rule_items = [value for key, value in semantic_roles.items() if str(key).startswith("rate_rule")]
        if rule_items:
            rate_rules = rule_items
    if rate_rules and isinstance(rate_rules, list):
        is_aggregation = False

    var_name = path.get("active_scope_item")
    collection_var = None
    collection_type = None
    if not path.get("in_loop"):
        for vt, vs in reversed(list(path.get("type_to_vars", {}).items())):
            if any(k in vt for k in ["IEnumerable", "List", "[]"]) and vt != "string":
                if vs:
                    collection_var = vs[-1].get("var_name")
                    collection_type = vt
                    break
    if var_name:
        if not path.get("in_loop"):
            if not (collection_var and var_name == collection_var and (rate_rules or is_aggregation)):
                for vt, vs in path.get("type_to_vars", {}).items():
                    if any(v["var_name"] == var_name for v in vs):
                        if "IEnumerable<" in vt or "List<" in vt:
                            var_name = f"{var_name}.First()"
                            break
    if not var_name:
        for vt, vars_list in reversed(list(path.get("type_to_vars", {}).items())):
            if vt not in ["int", "string", "bool", "decimal", "object", "DateTime"] and not vt.startswith("I"):
                var_name = vars_list[-1]["var_name"]
                break
        if not var_name:
            for vt, vars_list in reversed(list(path.get("type_to_vars", {}).items())):
                if "IEnumerable<" in vt or "List<" in vt:
                    var_name = vars_list[-1]["var_name"] + ".First()"
                    break
        if not var_name:
            var_name = "item"

    calc_target = var_name
    loop_item_name = None
    loop_item_type = None
    use_collection_loop = False
    if collection_var and collection_type and (var_name == collection_var):
        loop_item_type = action_synthesizer.type_system.extract_generic_inner(collection_type) or target_entity
        loop_item_name = action_synthesizer.stmt_builder.get_semantic_var_name(node, loop_item_type, "item", new_path, prefix="item", role="item")
        calc_target = loop_item_name
        use_collection_loop = True

    if rate_rules and isinstance(rate_rules, list):
        value_prop_hint = semantic_roles.get("value_prop") or semantic_roles.get("source_prop")
        value_prop = _resolve_prop_name(value_prop_hint)
        assignment_hint = semantic_roles.get("assignment_target") or semantic_roles.get("property")
        if assignment_hint:
            assignment_target = action_synthesizer.semantic_binder._resolve_prop(assignment_hint, "numeric", props, node) if props else assignment_hint
        if value_prop and assignment_target and var_name:
            def _build_condition(cond: Dict[str, Any]) -> str:
                if not isinstance(cond, dict):
                    return ""
                prop = cond.get("prop")
                op = cond.get("op")
                val = cond.get("value")
                if not prop or not op:
                    return ""
                resolved_prop = _resolve_prop_name(prop)
                left = f"{calc_target}.{resolved_prop}"
                if isinstance(val, str):
                    right = to_csharp_string_literal(val)
                else:
                    right = str(val)
                expr_local = f"{left} {op} {right}"
                and_cond = cond.get("and")
                if and_cond:
                    and_expr = _build_condition(and_cond)
                    if and_expr:
                        expr_local = f"({expr_local} && {and_expr})"
                return expr_local

            pieces = []
            default_expr = ""
            for rule in rate_rules:
                if not isinstance(rule, dict):
                    continue
                rate = rule.get("rate")
                rate_expr = f"{calc_target}.{value_prop} * {_format_decimal_literal(rate)}"
                when = rule.get("when")
                if when:
                    cond_expr = _build_condition(when)
                    if cond_expr:
                        pieces.append((cond_expr, rate_expr))
                else:
                    default_expr = rate_expr
            if pieces:
                if not default_expr:
                    default_expr = "0m"
                expr = default_expr
                for cond_expr, rate_expr in reversed(pieces):
                    expr = f"({cond_expr}) ? {rate_expr} : {expr}"

    def _early_return_for_method(method_ret: str) -> str:
        if not method_ret:
            return "return;"
        if method_ret in ["void", "Task"]:
            return "return;"
        if method_ret.startswith("Task<"):
            return "return default;"
        if method_ret in ["int", "long", "decimal", "double", "float"]:
            return "return 0;"
        if method_ret == "bool":
            return "return false;"
        return "return null;"

    if isinstance(var_name, str) and var_name.endswith(".First()"):
        collection_var = var_name[:-8]
        safe_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "var", "item", new_path, prefix="item", role="item")
        new_path["statements"].append({"type": "raw", "code": f"var {safe_var} = {collection_var}.FirstOrDefault();", "node_id": node.get("id")})
        return_stmt = _early_return_for_method(new_path.get("method_return_type", "void"))
        new_path["statements"].append({"type": "raw", "code": f"if ({safe_var} == null) {return_stmt}", "node_id": node.get("id")})
        new_path.setdefault("all_usings", set()).add("System.Linq")
        var_name = safe_var

    qty_hint = semantic_roles.get("quantity_prop")
    price_hint = semantic_roles.get("price_prop")
    qty_flag = semantic_roles.get("quantity") is True
    price_flag = semantic_roles.get("price") is True
    qty_prop = None
    price_prop = None
    if props and (qty_hint or qty_flag):
        if qty_hint and not isinstance(qty_hint, bool):
            qty_prop = action_synthesizer.semantic_binder._resolve_prop(str(qty_hint), "numeric", props, node)
        if not qty_prop and qty_flag and "Quantity" in props:
            qty_prop = "Quantity"
        if not qty_prop and qty_flag:
            qty_prop = action_synthesizer.semantic_binder._resolve_prop("quantity", "numeric", props, node)
            if not qty_prop:
                qty_prop = next((p for p in props.keys() if p.lower() in ["quantity", "qty", "count"]), None)
    if props and (price_hint or price_flag):
        if price_hint and not isinstance(price_hint, bool):
            price_prop = action_synthesizer.semantic_binder._resolve_prop(str(price_hint), "numeric", props, node)
            if not price_prop:
                hint_lower = str(price_hint).lower()
                price_prop = next((p for p in props.keys() if p.lower() == hint_lower), None)
        if not price_prop and price_flag and "Price" in props:
            price_prop = "Price"
        if not price_prop and price_flag:
            price_prop = action_synthesizer.semantic_binder._resolve_prop("price", "numeric", props, node)
            if not price_prop:
                price_prop = next((p for p in props.keys() if "price" in p.lower() and "discount" not in p.lower()), None)
    if price_prop and qty_prop:
        expr = f"{var_name}.{price_prop} * {var_name}.{qty_prop}"
    if not expr and (qty_flag or price_flag) and props:
        numeric_props = []
        for pn, pt in props.items():
            if pt in ["int", "long", "decimal", "double", "float"]:
                numeric_props.append(pn)
        if numeric_props:
            if not price_prop:
                price_prop = next((p for p in numeric_props if "price" in p.lower() and "discount" not in p.lower()), None)
            if not qty_prop:
                qty_prop = next((p for p in numeric_props if p.lower() in ["quantity", "qty", "count"]), None)
            if price_prop and qty_prop:
                expr = f"{var_name}.{price_prop} * {var_name}.{qty_prop}"
    if not expr and action_synthesizer._has_tag(text, "quantity"):
        qty_prop = None
        price_prop = None
        for pn, pt in props.items():
            if pt in ["int", "long", "decimal", "double", "float"]:
                if pn.lower() in ["quantity", "qty", "count"]:
                    qty_prop = pn
                if pn.lower() == "price":
                    price_prop = pn
                elif "price" in pn.lower() and "discount" not in pn.lower() and not price_prop:
                    price_prop = pn
                elif "price" in pn.lower() and not price_prop:
                    price_prop = pn
        if price_prop and qty_prop:
            expr = f"{var_name}.{price_prop} * {var_name}.{qty_prop}"
    if not expr:
        numeric_props = []
        for pn, pt in props.items():
            if pt in ["int", "long", "decimal", "double", "float"]:
                numeric_props.append(pn)
        if numeric_props and action_synthesizer._has_tag(text, "quantity"):
            price_prop = next((p for p in numeric_props if "price" in p.lower()), None)
            qty_prop = next((p for p in numeric_props if p.lower() in ["quantity", "qty", "count"]), None)
            if price_prop and qty_prop:
                expr = f"{var_name}.{price_prop} * {var_name}.{qty_prop}"
        preferred = None
        for key in ["total", "amount", "price", "sum", "points", "discount", "score", "count"]:
            for pn in numeric_props:
                if key in pn.lower():
                    preferred = pn
                    break
            if preferred:
                break
        if not preferred and numeric_props:
            preferred = numeric_props[0]
        if preferred:
            expr = f"{var_name}.{preferred}" if var_name else preferred

    percent_value = extract_percentage_value(text)
    if percent_value is not None and not rate_rules:
        hint_source = target_hint or explicit_prop
        if not hint_source:
            for g in calc_goals + logic_goals:
                candidate_hint = g.get("target_hint") or g.get("variable_hint")
                if candidate_hint:
                    hint_source = candidate_hint
                    break
        base_prop = None
        if props and hint_source:
            base_prop = action_synthesizer.semantic_binder._resolve_prop(str(hint_source), "numeric", props, node)
        if not base_prop and props:
            numeric_props = [pn for pn, pt in props.items() if pt in ["int", "long", "decimal", "double", "float"]]
            preferred = None
            for key in ["total", "amount", "price", "sum", "discount", "points", "score", "count"]:
                for pn in numeric_props:
                    if key in pn.lower():
                        preferred = pn
                        break
                if preferred:
                    break
            if not preferred and numeric_props:
                preferred = numeric_props[0]
            base_prop = preferred
        if base_prop:
            base_expr = f"{var_name}.{base_prop}" if var_name and path.get("in_loop") else base_prop
            expr = f"{base_expr} * ({percent_value}m / 100m)"

    explicit_assignment = bool(semantic_roles.get("assignment_target") or semantic_roles.get("property") or semantic_roles.get("field") or rate_rules)

    if is_aggregation:
        value_prop_hint = semantic_roles.get("value_prop") or target_hint or explicit_prop
        value_prop = _resolve_prop_name(value_prop_hint)
        if value_prop:
            if use_collection_loop and calc_target:
                expr = f"{calc_target}.{value_prop}"
            elif var_name:
                expr = f"{var_name}.{value_prop}"
        clean_agg_hint = target_hint or "total"
        if clean_agg_hint and str(clean_agg_hint).strip().isdigit():
            clean_agg_hint = "total"
        agg_var = action_synthesizer.stmt_builder.get_normalized_method_name(clean_agg_hint)
        if not agg_var:
            agg_var = "Total"
        agg_var = agg_var[0].lower() + agg_var[1:]
        if agg_var not in new_path.get("used_names", set()):
            decl_code = f"decimal {agg_var} = 0m;"
            new_path.setdefault("hoisted_statements", []).append({"type": "raw", "code": decl_code, "node_id": "hoist_" + node.get("id")})
            new_path.setdefault("used_names", set()).add(agg_var)
            new_path.setdefault("name_to_role", {})[agg_var] = "accumulator"
            new_path.setdefault("type_to_vars", {}).setdefault("decimal", []).append({"var_name": agg_var, "node_id": node.get("id"), "semantic_role": "data", "target_entity": "decimal", "role": "accumulator"})
        code = f"{agg_var} += {expr};"
        if use_collection_loop and loop_item_name and collection_var:
            loop_stmt = {
                "type": "foreach",
                "source": collection_var,
                "item_name": loop_item_name,
                "var_type": loop_item_type or "var",
                "body": [{"type": "raw", "code": code, "node_id": node.get("id")}],
                "node_id": node.get("id"),
                "intent": node.get("intent"),
            }
            new_path["statements"].append(loop_stmt)
        else:
            new_path["statements"].append({"type": "raw", "code": code, "node_id": node.get("id")})
        new_path["active_scope_item"] = agg_var
    elif assignment_target and (explicit_assignment or is_update_intent or is_known_state_property(assignment_target) or specialized_assignment):
        actual_expr = specialized_assignment if specialized_assignment else expr
        if use_collection_loop and loop_item_name:
            assign_code = f"{loop_item_name}.{assignment_target} = {actual_expr};"
            loop_stmt = {
                "type": "foreach",
                "source": collection_var,
                "item_name": loop_item_name,
                "var_type": loop_item_type or "var",
                "body": [{"type": "raw", "code": assign_code, "node_id": node.get("id")}],
                "node_id": node.get("id"),
                "intent": node.get("intent"),
            }
            new_path["statements"].append(loop_stmt)
            new_path["active_scope_item"] = collection_var
        else:
            code = f"{var_name}.{assignment_target} = {actual_expr};"
            new_path["statements"].append({"type": "raw", "code": code, "node_id": node.get("id")})
            new_path["active_scope_item"] = var_name
    else:
        actual_expr = specialized_assignment if specialized_assignment else expr
        local_var = action_synthesizer.stmt_builder.get_semantic_var_name(node, "decimal", target_hint or "result", new_path, role="data")
        new_path["statements"].append({"type": "raw", "code": f"var {local_var} = {actual_expr};", "node_id": node.get("id")})
        new_path.setdefault("type_to_vars", {}).setdefault("decimal", []).append({"var_name": local_var, "node_id": node.get("id"), "semantic_role": "data"})
        new_path["active_scope_item"] = local_var
    new_path.setdefault("consumed_ids", set()).add(node.get("id"))
    new_path["completed_nodes"] += 1
    return [new_path]
