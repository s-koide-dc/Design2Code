# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional, Tuple

class StatementBuilder:
    """論理ステートメント（IR）から具体的な C# コード断片を構築するクラス"""

    def __init__(self, type_system, entity_schema=None, structural_memory=None, knowledge_base=None):
        self.type_system = type_system
        self.entity_schema = entity_schema or {}
        self.structural_memory = structural_memory
        self.kb = knowledge_base

    def render_statements(self, statements: List[Dict[str, Any]], path: Dict[str, Any]) -> str:
        code_lines = []
        indent = "    " * path.get("indent_level", 2)
        
        for stmt in statements:
            s_type = stmt.get("type")
            if s_type == "call":
                method_expr = stmt.get("call_expr") or stmt.get("method")
                args = stmt.get("args")
                if method_expr and "(" not in str(method_expr):
                    if args is not None:
                        method_expr = f"{method_expr}({', '.join(args)})"
                    else:
                        method_expr = f"{method_expr}()"
                if isinstance(method_expr, tuple): method_expr = method_expr[0]
                
                if not method_expr: continue
                
                prefix = ""
                if stmt.get("out_var"):
                    if stmt.get("is_assignment_only"):
                        prefix = f"{stmt['out_var']} = "
                    else:
                        v_type = stmt.get("var_type", "var")
                        prefix = f"{v_type} {stmt['out_var']} = "
                
                await_pref = "await " if stmt.get("is_async") else ""
                full_line = f"{indent}{prefix}{await_pref}{method_expr}"
                
                if not any(full_line.strip().endswith(c) for c in [";", "}", "{"]):
                    full_line += ";"
                code_lines.append(full_line)
            
            elif s_type == "foreach":
                code_lines.append(self.render_foreach(stmt["source"], stmt["item_name"], stmt["var_type"], stmt["body"], path))
            
            elif s_type == "if":
                code_lines.append(self.render_if(stmt["condition"], stmt["body"], stmt.get("else_body", []), path))
            
            elif s_type == "raw":
                full_line = f"{indent}{stmt['code']}"
                if full_line.strip().endswith("}"):
                    full_line = full_line.rstrip().rstrip(";")
                code_lines.append(full_line)
                
            elif s_type == "comment":
                code_lines.append(f"{indent}// {stmt['text']}")

            elif s_type == "try_catch":
                code_lines.append(self.render_try_catch(stmt["body"], stmt["intent"], stmt["method_name"], path))
                
        return "\n".join(code_lines)

    def render_try_catch(self, body: List[Dict[str, Any]], intent: str, method_name: str, path: Dict[str, Any]) -> str:
        cur_indent = path.get("indent_level", 2)
        indent = "    " * cur_indent
        inner_path = path.copy()
        inner_path["indent_level"] = cur_indent + 1
        body_code = self.render_statements(body, inner_path)
        
        code = f"{indent}try\n{indent}{{\n{body_code}\n{indent}}}\n"
        
        # 27.395: Smart return for resilient blocks
        ret_val = ""
        method_ret = path.get("method_return_type", "void")
        is_async = path.get("is_async_needed", False) # 27.401 Check if we are in async context

        if is_async or "Task" in method_ret:
            if method_ret == "void" or method_ret == "Task": ret_val = " return;"
            else: ret_val = " return default;"
        elif method_ret != "void":
            if method_ret in ["int", "long", "decimal", "double", "float"]: ret_val = " return 0;"
            elif method_ret == "bool": ret_val = " return false;"
            else: ret_val = " return null;"
        else: ret_val = " return;"

        if path.get("use_logger"):
            log_line = f"_logger.LogError(ex, \"Error during {intent} in {method_name}\");"
        else:
            log_line = f"Console.Error.WriteLine(\"Error during {intent} in {method_name}: \" + ex.Message);"
        code += f"{indent}catch (Exception ex)\n{indent}{{\n{indent}    {log_line}\n{indent}   {ret_val}\n{indent}}}"
        return code

    def wrap_with_try_catch(self, stmt: Dict[str, Any], intent: str, method_name: str, path: Dict[str, Any]) -> Any:
        # 27.275: Phase 5 D-2 Wrapped with pre-rendering to handle indentation in raw blocks
        resilient_intents = ["DATABASE_QUERY", "HTTP_REQUEST", "FILE_IO", "FETCH", "PERSIST", "JSON_DESERIALIZE"]
        if intent not in resilient_intents:
            return stmt
            
        out_var = stmt.get("out_var")
        var_type = stmt.get("var_type", "var")
        
        hoisted_decl = None
        if out_var:
            type_defaults = {
                "int": "0", "long": "0L", "double": "0.0", "float": "0.0f", "decimal": "0m",
                "bool": "false", "string": "string.Empty"
            }
            default_val = type_defaults.get(var_type, "null")
            if "IEnumerable" in var_type or "List" in var_type: 
                concrete = var_type.replace('IEnumerable', 'List')
                if not concrete.startswith("List<"): concrete = f"List<{concrete}>"
                default_val = f"new {concrete}()"
            
            hoisted_decl = {"type": "raw", "code": f"{var_type} {out_var} = {default_val};", "var_type": var_type}
            
            existing_codes = [h.get("code") for h in path.setdefault("hoisted_statements", [])]
            if hoisted_decl["code"] not in existing_codes:
                path["hoisted_statements"].append(hoisted_decl)
                path.setdefault("used_names", set()).add(out_var)
            stmt_copy = stmt.copy(); stmt_copy["is_assignment_only"] = True
            stmt_body = [stmt_copy]
        else:
            stmt_body = [stmt]

        code = self.render_try_catch(stmt_body, intent, method_name, path)
        return {
            "type": "raw",
            "code": code,
            "node_id": stmt.get("node_id"),
            "intent": intent,
            "method_name": method_name,
            "out_var": out_var,
            "var_type": var_type,
        }

    def get_normalized_method_name(self, name: str) -> str:
        parts = []
        current = []
        for ch in str(name):
            if ch.isalnum():
                current.append(ch)
            else:
                if current:
                    parts.append("".join(current))
                    current = []
        if current:
            parts.append("".join(current))
        normalized = ""
        for p in parts:
            if not p: continue
            if p.isupper(): normalized += p.capitalize()
            else: normalized += p[0].upper() + p[1:]
        return normalized

    def render_method_call(self, m: Dict[str, Any], args: List[str], target_entity: str, cardinality: str, path: Dict[str, Any]) -> str:
        code_template = m.get("code")
        if isinstance(code_template, str) and "(" in code_template and "{" not in code_template and "}" not in code_template:
            return code_template
        if isinstance(code_template, str) and "(" in code_template and "{" in code_template and "}" in code_template:
            if target_entity and target_entity != "Item" and "<T>" in code_template:
                code_template = code_template.replace("<T>", f"<{target_entity}>")
            class SafeDict(dict):
                def __missing__(self, key):
                    return "null"
            param_names = [p.get("name") for p in m.get("params", []) if isinstance(p, dict)]
            mapping = {}
            for idx, pname in enumerate(param_names):
                if pname:
                    mapping[pname] = args[idx] if idx < len(args) else "null"
            try:
                return code_template.format_map(SafeDict(mapping))
            except Exception:
                # Fallback to raw template if formatting fails
                return code_template
        m_class = m.get("class", "")
        static_classes = ["Console", "File", "JsonSerializer", "Utils", "Math", "Directory", "Enumerable", "System.IO.File", "System.Console"]
        if self.kb:
            kb_statics = self.kb.get("resolution_rules", {}).get("static_classes", [])
            for sc in kb_statics:
                if sc not in static_classes: static_classes.append(sc)

        class_to_field = {
            "System.Net.Http.HttpClient": "_httpClient",
            "System.Data.IDbConnection": "_dbConnection",
            "Dapper.SqlMapper": "_dbConnection"
        }
        full_class = m.get("class", "")
        instance_name = m.get("target") or m.get("target_instance") or class_to_field.get(full_class)
        
        receiver = ""
        if not instance_name and m_class and m_class not in static_classes and full_class not in static_classes:
            simple_class_name = m_class.split(".")[-1]
            inferred_field = "_" + simple_class_name[0].lower() + simple_class_name[1:]
            instance_name = inferred_field
            path.setdefault("field_type_map", {})[instance_name] = full_class

        if instance_name:
            is_predefined = instance_name in ["_dbConnection", "_httpClient"]
            is_new_di = "field_type_map" in path and instance_name in path["field_type_map"]
            if is_predefined or is_new_di or instance_name in path.get("referenced_fields", set()):
                receiver = f"{instance_name}."
                path.setdefault("referenced_fields", set()).add(instance_name)
                
                if args:
                    first_arg = args[0].strip()
                    if first_arg == instance_name or first_arg == f"_{instance_name.lstrip('_')}":
                        args = args[1:]
                m_class = ""
        elif m.get("is_extension") and args:
            receiver = f"{args[0]}."
            args = args[1:]
            m_class = ""
        
        display_class = m_class
        if "." in m_class:
            class_simple = m_class.split(".")[-1]
            if m_class in path.get("all_usings", set()) or any(u == m_class.rsplit('.', 1)[0] for u in path.get("all_usings", set())):
                display_class = class_simple

        final_prefix = ""
        if receiver: final_prefix = receiver
        elif display_class and display_class not in ["Utils", ""]:
            final_prefix = f"{display_class}."
            
        if m.get("is_constructor"):
            final_prefix = f"new {display_class} "
            if receiver: final_prefix = f"new {display_class} "

        m_name = m.get("name", "")
        is_io_class = full_class in ["System.Data.IDbConnection", "Dapper.SqlMapper", "System.Net.Http.HttpClient"]
        if is_io_class and not m_name.endswith("Async"):
            if m_name in ["Query", "QuerySingle", "QueryFirstOrDefault", "Execute", "Get", "Post", "Put", "Delete"]:
                m_name += "Async"
                path["has_async_io"] = True
                if hasattr(m, "__setitem__"): m["is_async"] = True

        if m.get("requires_generic") or "<T>" in m_name:
            t_arg = target_entity
            is_dapper_query = m_name.startswith("Query") and (full_class == "Dapper.SqlMapper" or full_class.endswith("IDbConnection"))
            if cardinality == "COLLECTION" and not is_dapper_query:
                if "IEnumerable" not in t_arg and "List" not in t_arg:
                    t_arg = f"List<{t_arg}>"
            if "<T>" in m_name: m_name = m_name.replace("<T>", f"<{t_arg}>")
            else: m_name = f"{m_name}<{t_arg}>"
        
        safe_args = [str(a) if a is not None else "\"\"" for a in args]
        return f"{final_prefix}{m_name}({', '.join(safe_args)})"

    def render_foreach(self, source: str, item_name: str, var_type: str, body: List[Dict[str, Any]], path: Dict[str, Any]) -> str:
        target_ent = var_type
        if isinstance(var_type, str):
            prefix = "IEnumerable<"
            if var_type.startswith(prefix) and var_type.endswith(">"):
                target_ent = var_type[len(prefix):-1].strip()
        if target_ent == var_type: target_ent = "var"
        v_info = {"var_name": item_name, "node_id": "loop", "semantic_role": "item", "target_entity": target_ent}
        path.setdefault("type_to_vars", {}).setdefault(target_ent, []).append(v_info)
        path.setdefault("name_to_role", {})[item_name] = "item"
        indent = "    " * path.get("indent_level", 2)
        path["indent_level"] += 1
        body_code = self.render_statements(body, path)
        path["indent_level"] -= 1
        return f"{indent}foreach (var {item_name} in {source})\n{indent}{{\n{body_code}\n{indent}}}"

    def render_if(self, condition: str, body: List[Dict[str, Any]], else_body: List[Dict[str, Any]], path: Dict[str, Any]) -> str:
        indent = "    " * path.get("indent_level", 2)
        path["indent_level"] += 1
        body_code = self.render_statements(body, path)
        path["indent_level"] -= 1
        code = f"{indent}if ({condition})\n{indent}{{\n{body_code}\n{indent}}}"
        if else_body:
            path["indent_level"] += 1
            else_code = self.render_statements(else_body, path)
            path["indent_level"] -= 1
            code += f"\n{indent}else\n{indent}{{\n{else_code}\n{indent}}}"
        return code

    def get_semantic_var_name(self, node, var_type, method_name, path, prefix=None, role=None) -> str:
        if prefix: base = prefix
        else:
            ent = node.get("target_entity", "Item").lower()
            base = ent if ent not in ["item", "string", "int", "decimal", "bool", "object", "void"] else "result"
            
        reserved = ["abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char", "checked", "class", "const", "continue", "decimal", "default", "delegate", "do", "double", "else", "enum", "event", "explicit", "extern", "false", "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit", "in", "int", "interface", "internal", "is", "lock", "long", "namespace", "new", "null", "object", "operator", "out", "override", "params", "private", "protected", "public", "readonly", "ref", "return", "sbyte", "sealed", "short", "sizeof", "stackalloc", "static", "string", "struct", "switch", "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked", "unsafe", "ushort", "using", "virtual", "void", "volatile", "while"]
        if base in reserved: base = "result"
        
        used_names = path.setdefault("used_names", set())
        candidate = base
        if base == "result" and candidate not in used_names and not any(n.startswith("result") for n in used_names):
            candidate = "result0"
        counter = 1
        
        while candidate in used_names:
            candidate = f"{base}{counter}"
            counter += 1
            
        used_names.add(candidate)
        if role:
            path.setdefault("name_to_role", {})[candidate] = role
        return candidate

    def register_entity(self, entity_name: str, path: Dict[str, Any]):
        existing_props = None
        if self.structural_memory: existing_props = self.structural_memory.get_class_properties(entity_name)
        if existing_props:
            merged = dict(existing_props)
            if entity_name in self.entity_schema.get("entities_map", {}):
                for k, v in self.entity_schema["entities_map"][entity_name]["properties"].items():
                    if k not in merged:
                        merged[k] = v
            else:
                for ent in self.entity_schema.get("entities", []):
                    if ent.get("name") == entity_name:
                        for k, v in ent.get("properties", {}).items():
                            if k not in merged:
                                merged[k] = v
                        break
            path.setdefault("poco_defs", {})[entity_name] = merged
        elif entity_name in self.entity_schema.get("entities_map", {}):
            path.setdefault("poco_defs", {})[entity_name] = self.entity_schema["entities_map"][entity_name]["properties"]
        else:
            for ent in self.entity_schema.get("entities", []):
                if ent["name"] == entity_name: path.setdefault("poco_defs", {})[entity_name] = ent["properties"]; break

    def build_poco_display_expression(self, var_name: str, entity_name: str, path: Dict[str, Any]) -> str:
        props = path.get("poco_defs", {}).get(entity_name, {})
        if not props: return var_name
        p_list = [f"{p}: {{{var_name}.{p}}}" for p in props.keys()]
        return f"$\"{entity_name} {{{{ {', '.join(p_list)} }}}}\""

    def fix_placeholders_recursive(self, statements: List[Dict[str, Any]], old: str, new: str):
        for stmt in statements:
            if stmt.get("method"): 
                m_code = stmt["method"][0] if isinstance(stmt["method"], tuple) else stmt["method"]
                stmt["method"] = m_code.replace(f"<{old}>", f"<{new}>")
            if stmt.get("var_type"): stmt["var_type"] = stmt["var_type"].replace(old, new)
            if stmt.get("body"): self.fix_placeholders_recursive(stmt["body"], old, new)
            if stmt.get("else_body"): self.fix_placeholders_recursive(stmt["else_body"], old, new)
