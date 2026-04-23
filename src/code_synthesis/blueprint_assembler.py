# -*- coding: utf-8 -*-
from typing import Dict, List, Any

class BlueprintAssembler:
    """
    [Phase 23.2: High-fidelity Blueprint Assembly]
    合成されたステートメント、型定義、フィールド、using を統合し、
    CodeBuilder が解釈可能な最終的な設計図を構築する。
    """
    def create_blueprint(self, method_name, path, inputs=None, ir_tree=None):
        usings = set(path.get("all_usings", []))
            
        # A-3. Async Signature Correction (Strict Enforcement)
        is_async = path.get("is_async_needed", False)
        if not is_async:
            for stmt in path.get("statements", []):
                if stmt.get("is_async"):
                    is_async = True; break
                code_text = str(stmt.get("code", "")) + str(stmt.get("method", ""))
                # token-based simple check. Substring search only.
                if "await " in code_text:
                    is_async = True; break
                    
        # Build parameters from inputs and detect required usings
        params = []
        if inputs:
            for inp in inputs:
                p_name = inp.get("name")
                p_type = inp.get("type_format") or inp.get("type") or "object"
                if not p_name:
                    continue
                if not p_type or p_type in ["void", "none"]:
                    continue
                params.append({"name": p_name, "type": p_type})
                if "IDbConnection" in p_type: usings.add("System.Data")
                if "HttpClient" in p_type: usings.add("System.Net.Http")
                if "ILogger" in p_type: usings.add("Microsoft.Extensions.Logging")

        # Determine the final return type of the method
        raw_ret = path.get("method_return_type") or "void"
        # ... (return type detection logic) ...
        if raw_ret == "void" and path.get("statements"):
            last_stmt = path["statements"][-1]
            if last_stmt.get("type") == "call" and last_stmt.get("out_var"):
                raw_ret = last_stmt.get("var_type", "dynamic")
            elif last_stmt.get("type") == "assign":
                raw_ret = last_stmt.get("var_type", "dynamic")
            elif last_stmt.get("type") == "raw" and last_stmt.get("out_var"):
                raw_ret = last_stmt.get("var_type", "dynamic")
        
        final_ret = raw_ret
        return_value_type = raw_ret
        if is_async:
            if isinstance(raw_ret, str) and raw_ret.startswith("Task<"):
                final_ret = raw_ret
                return_value_type = raw_ret[len("Task<"):-1].strip()
            elif raw_ret == "Task":
                final_ret = "Task"
                return_value_type = "void"
            else:
                final_ret = f"Task<{raw_ret}>" if raw_ret != "void" else "Task"
                return_value_type = raw_ret if raw_ret != "void" else "void"
            usings.add("System.Threading.Tasks")

        # Prepare body with node_id metadata inside statements
        final_body = []
        
        # 27.296: Phase 4 C-2: Guard Clauses (Input Validation)
        for p in params:
            p_name = p.get("name")
            p_type = p.get("type", "object")
            # Only check for reference types or nullable types (simplistic check for demo)
            is_val_type = p_type in ["int", "long", "double", "float", "decimal", "bool", "char", "Guid", "DateTime"]
            if p_name and not is_val_type:
                final_body.append({"type": "raw", "code": f"if ({p_name} == null) throw new ArgumentNullException(nameof({p_name}));", "node_id": "validation"})

        # 27.350: Phase 6 E-3 Inject Hoisted Statements (e.g. accumulator declarations)
        for h in path.get("hoisted_statements", []):
            final_body.append(h)

        for stmt in path.get("statements", []):
            final_body.append(stmt)

        if path.get("deferred_statements"):
            deferred = path.get("deferred_statements", [])
            for stmt in deferred:
                if isinstance(stmt, dict) and stmt.get("deferred_from"):
                    path.setdefault("consumed_ids", set()).add(stmt["deferred_from"])
                    path["completed_nodes"] = path.get("completed_nodes", 0) + 1
            for stmt in deferred:
                final_body.append(stmt)

        def _normalize_call_args(stmts):
            for s in stmts:
                if s.get("type") == "call":
                    m = s.get("method")
                    args = s.get("args")
                    if isinstance(m, str) and "(" in m and args:
                        s["args"] = []
                if s.get("body"):
                    _normalize_call_args(s.get("body", []))
                if s.get("else_body"):
                    _normalize_call_args(s.get("else_body", []))
        _normalize_call_args(final_body)
            
        # 27.298: Final Return Strategy
        if return_value_type != "void":
            last_non_comment = None
            for stmt in reversed(final_body):
                if stmt.get("type") != "comment":
                    last_non_comment = stmt
                    break
            last_is_return = False
            if last_non_comment and last_non_comment.get("type") == "raw":
                code = str(last_non_comment.get("code", "")).strip()
                if code.startswith("return "):
                    last_is_return = True
            if not last_is_return:
                ret_var = None
                ret_expr = None
                matching_vars = path.get("type_to_vars", {}).get(return_value_type, [])
                if matching_vars:
                    ret_var = matching_vars[-1]["var_name"]
                    ret_expr = ret_var

                def _extract_inner_type(type_name: str) -> str:
                    if not isinstance(type_name, str):
                        return ""
                    start = type_name.find("<")
                    end = type_name.rfind(">")
                    if 0 <= start < end:
                        return type_name[start + 1:end].strip()
                    return ""

                def _find_last_var_for_type(type_name: str) -> str:
                    candidates = path.get("type_to_vars", {}).get(type_name, [])
                    if not candidates:
                        return ""
                    return candidates[-1].get("var_name") or ""

                if not ret_expr:
                    inner = _extract_inner_type(return_value_type)
                    if inner:
                        list_type = f"List<{inner}>"
                        enumerable_type = f"IEnumerable<{inner}>"
                        ilist_type = f"IList<{inner}>"
                        icollection_type = f"ICollection<{inner}>"
                        if return_value_type.startswith("List<"):
                            enum_var = _find_last_var_for_type(enumerable_type) or _find_last_var_for_type(ilist_type) or _find_last_var_for_type(icollection_type)
                            if enum_var:
                                ret_expr = f"{enum_var}.ToList()"
                        elif return_value_type.startswith("IEnumerable<"):
                            list_var = _find_last_var_for_type(list_type) or _find_last_var_for_type(ilist_type) or _find_last_var_for_type(icollection_type)
                            if list_var:
                                ret_expr = list_var

                if ret_expr:
                    final_body.append({"type": "raw", "code": f"return {ret_expr};", "node_id": "return"})
                elif return_value_type in ["int", "long", "decimal", "double", "float"]:
                    final_body.append({"type": "raw", "code": f"return 0;", "node_id": "return_default"})
                elif return_value_type == "bool":
                    final_body.append({"type": "raw", "code": f"return true;", "node_id": "return_default"})
                else:
                    final_body.append({"type": "raw", "code": f"return null;", "node_id": "return_default"})

        def _scan_refs(stmts):
            found = set()
            for s in stmts:
                code_text = str(s.get("code", "")) + str(s.get("method", ""))
                if "_httpClient." in code_text:
                    found.add("_httpClient")
                if "_logger." in code_text:
                    found.add("_logger")
                if s.get("body"):
                    found.update(_scan_refs(s.get("body", [])))
                if s.get("else_body"):
                    found.update(_scan_refs(s.get("else_body", [])))
            return found
        detected_refs = _scan_refs(final_body)

        blueprint = {
            "namespace": "Generated",
            "class_name": "GeneratedProcessor",
            "usings": [], # Will fill later
            "fields": [],
            "methods": [{
                "name": method_name,
                "return_type": final_ret,
                "is_async": is_async,
                "params": params,
                "body": final_body
            }],
            "extra_classes": [],
            "extra_code": [],
            "optimize": True
        }

        
        # Dependency Injection (DI) Management
        field_types = {"_dbConnection": "IDbConnection", "_httpClient": "HttpClient", "_logger": f"ILogger<{blueprint.get('class_name', 'GeneratedProcessor')}>"}
        if "field_type_map" in path:
            field_types.update(path["field_type_map"])

        referenced_fields = set(path.get("referenced_fields", []))
        referenced_fields.update(detected_refs)
        
        # A-1. Resource Audit
        data_sources = path.get("data_sources", [])
        if not data_sources and ir_tree:
            data_sources = ir_tree.get("data_sources", [])
            
        for ds in data_sources:
            kind = ds.get("kind")
            if kind == "db": referenced_fields.add("_dbConnection")
            elif kind in ["http", "api"]: referenced_fields.add("_httpClient")
        
        for f in sorted(referenced_fields):
            if f in field_types:
                # 27.50: Skip static classes that were accidentally added to referenced_fields
                type_name = field_types[f]
                if type_name in ["Console", "File", "System.IO.File", "System.Console"]:
                    continue
                    
                blueprint["fields"].append({"name": f, "type": type_name})
                if f == "_dbConnection": usings.add("System.Data")
                if f == "_httpClient": usings.add("System.Net.Http")
                if f == "_logger": usings.add("Microsoft.Extensions.Logging")
                if "." in field_types[f]:
                    ns = ".".join(field_types[f].split('.')[:-1])
                    usings.add(ns)
        
        def _collect_required_usings(stmts, param_list, ret_type, has_async):
            required = set()
            code_blob = ""
            for s in stmts:
                code_blob += str(s.get("code", "")) + " " + str(s.get("method", "")) + " " + str(s.get("call_expr", "")) + " "
                if s.get("body"):
                    required.update(_collect_required_usings(s.get("body", []), [], "", False))
                if s.get("else_body"):
                    required.update(_collect_required_usings(s.get("else_body", []), [], "", False))
            type_blob = " ".join([str(ret_type or "")] + [f"{p.get('type','')}" for p in (param_list or [])])
            blob = code_blob + " " + type_blob

            if any(tok in blob for tok in ["Console.", "Exception", "ArgumentNullException", "Environment.", "DateTime", "StringSplitOptions"]):
                required.add("System")
            if any(tok in blob for tok in ["File.", "Directory.", "Path."]):
                required.add("System.IO")
            if any(tok in blob for tok in ["List<", "Dictionary<", "IEnumerable<"]):
                required.add("System.Collections.Generic")
            if any(tok in blob for tok in [".ToList(", ".Select(", ".Where(", ".Any(", ".First(", "Enumerable."]):
                required.add("System.Linq")
            if "JsonSerializer" in blob:
                required.add("System.Text.Json")
            if "JsonPropertyName" in blob:
                required.add("System.Text.Json.Serialization")
            if has_async or "Task<" in blob or "await " in blob:
                required.add("System.Threading.Tasks")
            if "HttpClient" in blob or "_httpClient" in blob:
                required.add("System.Net.Http")
            if "IDbConnection" in blob or "_dbConnection" in blob:
                required.add("System.Data")
            if "_logger" in blob or "ILogger<" in blob or "ILogger" in blob:
                required.add("Microsoft.Extensions.Logging")
            return required

        required_usings = _collect_required_usings(final_body, params, final_ret, is_async)
        usings.update(required_usings)
        blueprint["usings"] = sorted(list(usings))
        
        # POCO Generation
        def _collect_used_types(stmts):
            types = set()
            for s in stmts:
                for key in ["var_type", "varType"]:
                    t_val = s.get(key)
                    if isinstance(t_val, str):
                        types.add(t_val)
                if s.get("body"):
                    types.update(_collect_used_types(s.get("body", [])))
                if s.get("else_body"):
                    types.update(_collect_used_types(s.get("else_body", [])))
            return types

        used_types = _collect_used_types(final_body)
        used_types.add(raw_ret)
        if isinstance(final_ret, str):
            used_types.add(final_ret)

        def _flatten_types(type_name: str) -> List[str]:
            parts = set()
            if not isinstance(type_name, str):
                return []
            work = [type_name]
            while work:
                cur = work.pop()
                parts.add(cur)
                start = cur.find("<")
                end = cur.rfind(">")
                if 0 <= start < end:
                    inner = cur[start + 1:end]
                    for t in inner.split(","):
                        t_clean = t.strip()
                        if t_clean:
                            work.append(t_clean)
            return list(parts)

        used_type_tokens = set()
        for t in used_types:
            for token in _flatten_types(t):
                used_type_tokens.add(token.replace("IEnumerable<", "").replace("List<", "").replace(">", "").strip())

        for name, props in path.get("poco_defs", {}).items():
            if name == "Item" and len(path["poco_defs"]) > 1: continue
            if name not in used_type_tokens:
                continue
            
            poco_props = []
            for pn, pt in props.items():
                pascal_name = "".join(word.capitalize() for word in pn.split('_') if word) if "_" in pn else (pn[0].upper() + pn[1:] if pn else pn)
                p_entry = {"name": pascal_name, "type": pt}
                if pascal_name != pn:
                    p_entry["attributes"] = [f"JsonPropertyName(\"{pn}\")"]
                poco_props.append(p_entry)
                
            blueprint["extra_classes"].append({"name": name, "properties": poco_props})
        
        extra_code = path.get("extra_code", []) or []
        if extra_code:
            deduped = []
            seen = set()
            for code in extra_code:
                if not isinstance(code, str):
                    continue
                key = code.strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                deduped.append(code)
            blueprint["extra_code"] = deduped

        return blueprint
