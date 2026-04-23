# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional, Tuple

import json
import os
from src.utils.text_parser import extract_first_quoted_literal
class SemanticBinder:
    """
    [High-fidelity Logical Synthesis Layer]
    IR ノード、セマンティック・マップ、型システムを組み合わせ、
    具体的な C# コード（引数バインド、論理式）を生成するクラス。
    """

    def __init__(self, type_system, matcher=None, knowledge_base=None, stmt_builder=None, config=None, morph_analyzer=None):
        self.type_system = type_system
        self.matcher = matcher
        self.ukb = knowledge_base
        self.stmt_builder = stmt_builder
        self.config = config
        self.morph_analyzer = morph_analyzer
        strict_cfg = {}
        if hasattr(config, "get_section"):
            strict_cfg = config.get_section("generation") or {}
        if not isinstance(strict_cfg, dict):
            strict_cfg = {}
        self.strict_semantics = bool(strict_cfg.get("strict_semantics", False))

    def _is_identifier(self, value: Optional[str]) -> bool:
        if value is None:
            return False
        s = str(value).strip()
        if not s:
            return False
        if not (s[0].isalpha() or s[0] == "_"):
            return False
        return all(ch.isalnum() or ch == "_" for ch in s[1:])

    def bind_parameters(self, method: Dict[str, Any], node: Dict[str, Any], path: Dict[str, Any]) -> Optional[List[str]]:
        expected_params = method.get("params", [])
        if not expected_params: return []
        
        param_values = []
        semantic_roles = node.get("semantic_map", {}).get("semantic_roles", {})
        path.setdefault("last_literal_map", {})
        disallow_null_roles = {"data", "content", "predicate", "logic", "selector", "source", "keySelector"}
        
        for p in expected_params:
            pn, pt, prole = p.get("name"), p.get("type"), p.get("role")
            constraints = p.get("constraints", [])
            val = None
            
            if prole in semantic_roles:
                raw = semantic_roles[prole]
                if raw == "{context}":
                    res = self._resolve_source_var(node, path, pt, role_hint=prole)
                    if res:
                        v_name, bridge = res
                        val = bridge.replace("{var}", v_name) if bridge else v_name
                        raw = None
                if pt == "HttpContent" and raw == "{context}":
                    raw = None
                if pt == "string":
                    if "variable_only" in constraints:
                        val = self._resolve_source_var(node, path, pt)
                    else:
                        if isinstance(raw, str):
                            all_vars = {v["var_name"] for vs in path.get("type_to_vars", {}).values() for v in vs}
                            if raw in all_vars:
                                val = raw
                            else:
                                escaped = str(raw).replace('"', '""')
                                val = f"@\"{escaped}\"" if '"' in str(raw) else f"\"{raw}\""
                                if prole in ["path", "url", "sql"]:
                                    path["last_literal_map"][prole] = val
                        else:
                            escaped = str(raw).replace('"', '""')
                            val = f"@\"{escaped}\"" if '"' in str(raw) else f"\"{raw}\""
                            if prole in ["path", "url", "sql"]:
                                path["last_literal_map"][prole] = val
                elif pt == "Uri" and isinstance(raw, str):
                    escaped = str(raw).replace('"', '""')
                    lit = f"@\"{escaped}\"" if '"' in str(raw) else f"\"{raw}\""
                    val = f"new Uri({lit})"
                else:
                    val = raw

            if val is None and prole in ["path", "url", "sql"]:
                # 27.260: Prevent SQL bleeding. Only use previous SQL if the current intent strongly implies it.
                if prole == "sql" and node.get("intent") not in ["DATABASE_QUERY", "LINQ", "FETCH"]:
                    pass # Do not inherit SQL for PERSIST, WRITE, etc.
                else:
                    val = path["last_literal_map"].get(prole)
            if val is None and prole == "path":
                # Prefer explicit quoted literals in the step text over empty path defaults.
                literal = extract_first_quoted_literal(
                    node.get("original_text")
                    or node.get("text")
                    or ""
                )
                if literal:
                    escaped = str(literal).replace('"', '""')
                    val = f"@\"{escaped}\"" if '"' in str(literal) else f"\"{literal}\""
                    path["last_literal_map"]["path"] = val

            if val is None and prole == "sql" and node.get("intent") == "PERSIST":
                val = self._build_persist_sql(node, path)
                if val:
                    path["last_literal_map"]["sql"] = f"\"{val}\""
                    val = f"\"{val}\""

            if val is None and prole in ["item", "params", "param", "parameters", "data"] and node.get("intent") == "DATABASE_QUERY":
                sql_text = semantic_roles.get("sql")
                param_names = self._extract_sql_param_names(sql_text) if isinstance(sql_text, str) else []
                input_vars = (
                    path.get("type_to_vars", {}).get("int", [])
                    + path.get("type_to_vars", {}).get("decimal", [])
                    + path.get("type_to_vars", {}).get("string", [])
                )
                if input_vars and param_names:
                    param_name = param_names[0]
                    input_name = input_vars[0]["var_name"]
                    val = f"new {{ {param_name} = {input_name} }}"
                elif input_vars:
                    val = input_vars[0]["var_name"]
            
            if val is None:
                res = self._resolve_source_var(node, path, pt, role_hint=prole)
                if res and res[0]:
                    v_name, bridge = res
                    val = bridge.replace("{var}", v_name) if bridge else v_name
            
            if val is None:
                if "literal_only" in constraints and pt == "string":
                    val = "\"\""
                    if prole in ["path", "url", "sql"]:
                        path["last_literal_map"][prole] = val
                elif "literal_only" not in constraints:
                    if pt == "string": val = "\"\""
                    elif pt in ["int", "decimal", "double", "float"]: val = "0"
                    elif pt == "bool": val = "false"
                    elif pt == "object": val = "null"
                    else: val = "null"

            if prole == "path":
                has_explicit_path = "path" in semantic_roles or path.get("last_literal_map", {}).get("path")
                if not has_explicit_path and node.get("source_kind") not in ["file"]:
                    return None

            if (val is None or str(val).strip() == "null") and pt == "HttpContent" and node.get("intent") == "HTTP_REQUEST":
                role = (node.get("role") or "").upper()
                text = node.get("original_text", "")
                is_write = role in ["WRITE", "PERSIST"]
                if not is_write:
                    return None
                item = self._resolve_source_var(node, path, "object", role_hint="item")
                if item:
                    v_name, bridge = item
                    item_expr = bridge.replace("{var}", v_name) if bridge else v_name
                    val = f"new StringContent(JsonSerializer.Serialize({item_expr}))"
                    path.setdefault("all_usings", set()).update(["System.Net.Http", "System.Text.Json"])

            if val is None: return None
            param_values.append(val)
            
        # 27.295: Phase 3 B-4 Strong Typing for Dapper Parameters
        is_sql_method = "Dapper.SqlMapper" in method.get("class", "") or "IDbConnection" in method.get("class", "") or method.get("name", "").startswith("Query") or method.get("name", "").startswith("Execute")
        if is_sql_method and param_values:
            # Avoid heuristic SQL parsing; rely on explicit semantic roles only
            pass

        # Parameter sanity checks to avoid meaningless calls
        linq_class = method.get("class", "")
        is_linq = "System.Linq.Enumerable" in linq_class or linq_class == "Enumerable"
        for i, p in enumerate(expected_params):
            prole = p.get("role")
            pt = str(p.get("type", ""))
            val = str(param_values[i]).strip() if i < len(param_values) else "null"
            if prole in disallow_null_roles and val == "null":
                return None
            if prole == "sql" and val == "\"\"":
                return None
            if "Func<" in pt and val == "null":
                return None
            if is_linq and val == "null":
                return None
        return param_values

    def _extract_sql_param_names(self, sql: Optional[str]) -> List[str]:
        if not sql:
            return []
        s = str(sql)
        names = []
        i = 0
        while i < len(s):
            ch = s[i]
            if ch != "@":
                i += 1
                continue
            j = i + 1
            if j >= len(s):
                i += 1
                continue
            name_chars = []
            while j < len(s):
                cj = s[j]
                if cj.isalnum() or cj == "_":
                    name_chars.append(cj)
                    j += 1
                    continue
                break
            if name_chars:
                name = "".join(name_chars)
                if self._is_identifier(name):
                    if name not in names:
                        names.append(name)
            i = j if j > i else i + 1
        return names

    def _build_persist_sql(self, node: Dict[str, Any], path: Dict[str, Any]) -> Optional[str]:
        return None

    def generate_logic_expression(self, semantic_map: Dict[str, Any], target_entity: str, path: Dict[str, Any], node: Dict[str, Any] = None) -> str:
        logic_goals = semantic_map.get("logic", [])
        path.setdefault("last_literal_map", {})
        
        if node and node.get("intent") == "EXISTS":
            s_roles = semantic_map.get("semantic_roles", {})
            if "path" in s_roles:
                path_val = s_roles["path"]
                escaped = str(path_val).replace('"', '""')
                literal_expr = f"@\"{escaped}\"" if '"' in str(path_val) else f"\"{path_val}\""
                expr = f"File.Exists({literal_expr})"
                path["last_literal_map"]["path"] = literal_expr
                path.setdefault("all_usings", set()).add("System.IO")
                return expr
            last_path = path.get("last_literal_map", {}).get("path")
            if last_path:
                expr = f"File.Exists({last_path})"
                path.setdefault("all_usings", set()).add("System.IO")
                return expr
            literal = extract_first_quoted_literal(
                semantic_map.get("original_text")
                or node.get("original_text")
                or semantic_map.get("text")
                or node.get("text")
            )
            if literal:
                escaped = str(literal).replace('"', '""')
                literal_expr = f"@\"{escaped}\"" if '"' in str(literal) else f"\"{literal}\""
                expr = f"File.Exists({literal_expr})"
                path["last_literal_map"]["path"] = literal_expr
                path.setdefault("all_usings", set()).add("System.IO")
                return expr
            if "url" in s_roles: return "true"
            return "true"
        
        if not logic_goals:
            # 27.380: Phase 6 E-3 Case: Falling back to existing boolean variable (e.g. from EXISTS)
            bool_vars = path.get("type_to_vars", {}).get("bool", [])
            if bool_vars:
                # Prioritize 'result' or variables mentioned in semantic_roles
                for v in reversed(bool_vars):
                    if v.get("semantic_role") == "condition" or v["var_name"] == "result":
                        return v["var_name"]
                return bool_vars[-1]["var_name"]
            return "true"
        
        props = path.get("poco_defs", {}).get(target_entity, {})
        expressions = []
        op_map = {
            "Greater": ">", "Less": "<", "GreaterEqual": ">=", "LessEqual": "<=",
            "Equal": "==", "NotEqual": "!=", "Contains": ".Contains", "StartsWith": ".StartsWith"
        }
        
        # 27.123: Use actual loop variable name instead of hardcoded 'x'
        var_name = path.get("active_scope_item", "x")
        
        current_conjunction = " && "
        for goal in logic_goals:
            g_type = goal.get("type")
            if g_type == "conjunction":
                current_conjunction = " || " if goal.get("value") == "OR" else " && "
                continue
                
            op, val, hint = goal.get("operator"), goal.get("expected_value"), goal.get("variable_hint", "")
            target_hint = goal.get("target_hint")
            if not props and target_entity == "string":
                prop_access = var_name
                if g_type == "string":
                    if op == "Equal":
                        expressions.append(f"{prop_access} == \"{val}\"")
                    elif op == "NotEqual":
                        expressions.append(f"{prop_access} != \"{val}\"")
                    else:
                        method = op_map.get(op, ".Contains")
                        expressions.append(f"{prop_access}{method}(\"{val}\")")
                elif g_type == "numeric":
                    csharp_op = op_map.get(op, "==")
                    expressions.append(f"{prop_access}.Length {csharp_op} {val}")
                elif g_type == "calculation":
                    expr = self._build_arithmetic_expr(goal, props, path)
                    if expr:
                        expressions.append(expr)
                continue
            prop_name = self._resolve_prop(hint, g_type, props, node, target_hint=target_hint)
            if not prop_name:
                if not prop_name: prop_name = list(props.keys())[0] if props else "Unknown"

            p_type = props.get(prop_name, "object")
            # 27.124: Dynamic loop variable access
            prop_access = f"{var_name}.{prop_name}" if path.get("in_loop") else prop_name
            
            if g_type == "numeric":
                csharp_op = op_map.get(op, "==")
                if val == "{input}":
                    input_vars = path.get("type_to_vars", {}).get("int", []) + path.get("type_to_vars", {}).get("decimal", [])
                    if input_vars:
                        resolved_val = "{input}"
                        for v in input_vars:
                            if v.get("node_id") == "input": resolved_val = v["var_name"]; break
                        if resolved_val == "{input}": resolved_val = input_vars[0]["var_name"]
                        val = resolved_val
                    else: val = "0"
                numeric_literal = isinstance(val, str) and self._is_numeric_literal(str(val))
                is_identifier = isinstance(val, str) and self._is_identifier(str(val))
                p_type_lower = str(p_type).lower()
                if p_type_lower == "string":
                    if op in ["Greater", "GreaterEqual"]:
                        expressions.append(f"{prop_access}.StartsWith(\"{val}\")")
                    elif op == "NotEqual":
                        expressions.append(f"{prop_access} != \"{val}\"")
                    else:
                        expressions.append(f"{prop_access} == \"{val}\"")
                    continue
                if not numeric_literal and not is_identifier:
                    val = "0"
                
                suffix = "m" if "decimal" in p_type.lower() or "decimal" in str(val) else ""
                expressions.append(f"{prop_access} {csharp_op} {val}{suffix}")
                
            elif g_type == "string":
                if op == "Equal": expressions.append(f"{prop_access} == \"{val}\"")
                elif op == "NotEqual": expressions.append(f"{prop_access} != \"{val}\"")
                else:
                    method = op_map.get(op, ".Contains")
                    expressions.append(f"{prop_access}{method}(\"{val}\")")
            
            elif g_type == "calculation":
                expr = self._build_arithmetic_expr(goal, props, path)
                if expr: expressions.append(expr)

        return current_conjunction.join(expressions) if expressions else "true"

    def _resolve_source_var(self, node: Dict[str, Any], path: Dict[str, Any], target_type: str, role_hint: str = None) -> Optional[Tuple[str, Optional[str]]]:
        preferred_vars = node.get("semantic_map", {}).get("semantic_roles", {}).get("preferred_vars")
        if preferred_vars:
            preferred_list = preferred_vars if isinstance(preferred_vars, list) else [preferred_vars]
            for name in preferred_list:
                if not isinstance(name, str):
                    continue
                for vs in path.get("type_to_vars", {}).values():
                    if any(v.get("var_name") == name for v in vs):
                        return name, None

        if self.strict_semantics:
            # Strict mode forbids heuristic selection. Require explicit preferred_vars or input_refs.
            return None, None

        # 27.299: Phase 5 D-2 Intelligent Persistence & Context Selection
        if role_hint in ["data", "params", "item"]:
            scope_item = path.get("active_scope_item")
            if scope_item:
                # If we have an active scope item (e.g. user.First()), check if it's compatible
                # Since active_scope_item is often string-injected (x.Prop), we can't easily check type
                # but we'll prioritize it for data/params roles.
                return scope_item, None

        # 27.460: Phase 7 F-1 Role-based context selection with scoring
        role_synonyms = self.ukb.get("role_synonyms", {}) if (self.ukb and hasattr(self.ukb, "get")) else {}
        if not isinstance(role_synonyms, dict):
            role_synonyms = {}
        syns = role_synonyms.get(role_hint, [])
        
        best_candidate = None
        best_role_score = -1
        
        all_compat_vars = []
        if target_type in path.get("type_to_vars", {}):
            all_compat_vars.extend(path["type_to_vars"][target_type])
        
        # Also check compatible types
        for t, vs in path.get("type_to_vars", {}).items():
            if t == target_type: continue
            is_compat, score, _ = self.type_system.is_compatible(target_type, t)
            if is_compat:
                all_compat_vars.extend(vs)
                
        # recency index
        var_count = len(all_compat_vars)
        for i, v in enumerate(reversed(all_compat_vars)):
            v_name = v["var_name"]
            v_role = v.get("role")
            recency_score = (var_count - i) / var_count
            
            # Prevent accidental DI service usage
            if role_hint in ["data", "params"] and v_name.startswith("_"): continue
            
            scoring = self.ukb.get("role_scoring", {}) if (self.ukb and hasattr(self.ukb, "get")) else {}
            if not isinstance(scoring, dict):
                scoring = {}
            exact_score = scoring.get("exact_match", 10)
            synonym_score = scoring.get("synonym_match", 5)
            fallback_score = scoring.get("fallback", 1)
            penalty = scoring.get("transform_penalty", -2)

            r_score = 0
            if v_role == role_hint: r_score = exact_score
            elif role_hint and v_role in syns: r_score = synonym_score
            elif role_hint is None: r_score = fallback_score
            
            # 27.470: Penalize old READ/FETCH variables if TRANSFORM result exists
            if v_role in ["READ", "FETCH"] and role_hint in ["data", "content", "TRANSFORM"]:
                r_score += penalty # Slight penalty
            
            total_score = r_score + recency_score
            if total_score > best_role_score:
                best_role_score = total_score
                best_candidate = (v_name, None)
        
        if best_candidate:
            return best_candidate
        return None, None

    def _resolve_prop(self, hint: str, goal_type: str, props: Dict[str, str], node: Dict[str, Any], target_hint: Optional[str] = None) -> Optional[str]:
        if not props:
            return None

        if node:
            semantic_roles = node.get("semantic_map", {}).get("semantic_roles", {}) if isinstance(node, dict) else {}
            explicit_prop = semantic_roles.get("property") or semantic_roles.get("field") or semantic_roles.get("target_property")
            if explicit_prop:
                explicit_lower = str(explicit_prop).lower()
                for p in props.keys():
                    if p.lower() == explicit_lower:
                        return p

        def _try_match(text: str) -> Optional[str]:
            text_clean = (text or "").strip("\"' ")
            if not text_clean:
                return None
            if self.matcher:
                best_res = self.matcher.find_best_match(text_clean, list(props.keys()))
                if isinstance(best_res, tuple):
                    best_prop, _score = best_res
                    if best_prop in props:
                        return best_prop
                elif best_res and best_res in props:
                    return best_res
            for p in props.keys():
                if p.lower() == text_clean.lower():
                    return p
            return None

        hint_clean = hint.strip("\"' ")
        if hint_clean:
            matched = _try_match(hint_clean)
            if matched:
                return matched
            if target_hint:
                matched = _try_match(target_hint)
                if matched:
                    return matched
            return None
        if target_hint:
            matched = _try_match(target_hint)
            if matched:
                return matched
            return None

        if goal_type == "numeric":
            for p, pt in props.items():
                if pt in ["int", "long", "decimal", "double", "float"]:
                    return p
        if goal_type == "string":
            for p, pt in props.items():
                if "string" in str(pt).lower():
                    return p
        return None

    def _build_arithmetic_expr(self, goal: Dict[str, Any], props: Dict[str, str], path: Dict[str, Any]) -> Optional[str]:
        text = goal.get("original_step", "").lower()
        hint = goal.get("variable_hint", "")
        target_hint = goal.get("target_hint")
        target_prop = self._resolve_prop(hint, "numeric", props, None, target_hint=target_hint)
        
        if not target_prop:
            target_prop = list(props.keys())[0] if props else "TotalAmount"
        if props and target_prop not in props:
            if target_prop.endswith("Amount"):
                base = target_prop[:-6]
                if base in props:
                    target_prop = base
            if target_prop not in props and "Total" in props:
                target_prop = "Total"
            if target_prop not in props:
                target_prop = list(props.keys())[0] if props else "TotalAmount"
            
        var_name = path.get("active_scope_item", "x")
        prop_access = f"{var_name}.{target_prop}" if path.get("in_loop") else target_prop
        raw_val = goal.get("value") or goal.get("expected_value")
        if raw_val is not None and self._is_numeric_literal(str(raw_val)):
            return f"{prop_access} * {raw_val}m"
        return None

    def _is_numeric_literal(self, value: str) -> bool:
        if value is None:
            return False
        s = str(value).strip()
        if not s:
            return False
        if s.isdigit():
            return True
        try:
            float(s)
            return True
        except Exception:
            return False
