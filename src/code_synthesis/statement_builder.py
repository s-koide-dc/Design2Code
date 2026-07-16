# -*- coding: utf-8 -*-
from typing import List, Dict, Any
from src.utils.semantic_intents import (
    INTENT_DATABASE_QUERY,
    INTENT_FETCH,
    INTENT_FILE_IO,
    INTENT_HTTP_REQUEST,
    INTENT_JSON_DESERIALIZE,
    INTENT_PERSIST,
)

class StatementBuilder:
    """論理ステートメント（IR）から具体的な C# コード断片を構築するクラス"""

    def __init__(self, type_system, entity_schema=None, structural_memory=None, knowledge_base=None):
        self.type_system = type_system
        self.entity_schema = entity_schema or {}
        self.structural_memory = structural_memory
        self.kb = knowledge_base

    def _ensure_console_error_helper(self, path: Dict[str, Any]) -> None:
        helper_code = """namespace Generated
{
    internal static class GeneratedErrorLog
    {
        public static void Write(string intent, string methodName, System.Exception ex)
        {
            System.Console.Error.WriteLine("Error during " + intent + " in " + methodName + ": " + ex.Message);
        }
    }
}"""
        extra_code = path.setdefault("extra_code", [])
        if helper_code not in extra_code:
            extra_code.append(helper_code)

    def _csharp_string_literal(self, value: Any) -> str:
        text = str(value or "")
        escaped = text.replace("\\", "\\\\").replace("\"", "\\\"")
        return f"\"{escaped}\""

    def _default_return_for_return_type(self, return_type: str) -> str:
        if not return_type or return_type in ["void", "Task"]:
            return "return;"
        if isinstance(return_type, str) and return_type.startswith("Task<"):
            inner = return_type[len("Task<"):-1].strip() if return_type.endswith(">") else ""
            if inner.startswith(("List<", "IEnumerable<", "IReadOnlyList<", "ICollection<")) and inner.endswith(">"):
                element_type = inner[inner.find("<") + 1:-1].strip()
                return f"return new List<{element_type}>();"
            return "return default;"
        if isinstance(return_type, str) and return_type.startswith(("List<", "IReadOnlyList<", "ICollection<")) and return_type.endswith(">"):
            element_type = return_type[return_type.find("<") + 1:-1].strip()
            return f"return new List<{element_type}>();"
        if return_type in ["int", "long", "decimal", "double", "float"]:
            return "return 0;"
        if return_type == "bool":
            return "return false;"
        return "return null;"

    def _catch_action_for_policy(
        self,
        *,
        path: Dict[str, Any],
        error_policy: str,
        has_hoisted_result: bool = False,
        hoisted_result_var: str | None = None,
        hoisted_result_type: str | None = None,
    ) -> str:
        method_ret = path.get("method_return_type", "void")
        is_async = path.get("is_async_needed", False)
        effective_ret = method_ret
        if isinstance(method_ret, str) and method_ret.startswith("Task<") and method_ret.endswith(">"):
            effective_ret = method_ret[len("Task<"):-1].strip()

        def _can_return_hoisted_result() -> bool:
            if not has_hoisted_result or not hoisted_result_var:
                return False
            if not isinstance(effective_ret, str) or not isinstance(hoisted_result_type, str):
                return False
            return effective_ret == hoisted_result_type

        if error_policy == "continue":
            return ""
        if error_policy == "rethrow":
            return "throw;"
        if _can_return_hoisted_result():
            return f"return {hoisted_result_var};"
        if is_async or "Task" in method_ret:
            return self._default_return_for_return_type(method_ret)
        if method_ret != "void":
            return self._default_return_for_return_type(method_ret)
        return "return;"

    def _catch_log_statement(self, intent: str, method_name: str, path: Dict[str, Any]) -> Dict[str, Any]:
        if path.get("use_logger"):
            log_line = f"_logger.LogError(ex, \"Error during {intent} in {method_name}\");"
        else:
            self._ensure_console_error_helper(path)
            log_line = (
                "GeneratedErrorLog.Write("
                f"{self._csharp_string_literal(intent)}, "
                f"{self._csharp_string_literal(method_name)}, "
                "ex);"
            )
        return {"type": "raw", "code": log_line}

    def _build_catch_body(
        self,
        *,
        intent: str,
        method_name: str,
        path: Dict[str, Any],
        error_policy: str,
        has_hoisted_result: bool = False,
        hoisted_result_var: str | None = None,
        hoisted_result_type: str | None = None,
    ) -> List[Dict[str, Any]]:
        catch_body = [self._catch_log_statement(intent, method_name, path)]
        action = self._catch_action_for_policy(
            path=path,
            error_policy=error_policy,
            has_hoisted_result=has_hoisted_result,
            hoisted_result_var=hoisted_result_var,
            hoisted_result_type=hoisted_result_type,
        )
        if action:
            catch_body.append({"type": "raw", "code": action})
        return catch_body

    def ensure_json_deserialize_helper(
        self,
        path: Dict[str, Any],
        *,
        output_type: str,
        fallback_expr: str,
    ) -> str:
        helper_suffix = self.get_normalized_method_name(output_type)
        helper_name = f"Deserialize{helper_suffix}OrDefault"
        self._ensure_console_error_helper(path)
        helper_code = f"""namespace Generated
{{
    public partial class GeneratedProcessor
    {{
        private static {output_type} {helper_name}(string json, out bool succeeded)
        {{
            succeeded = true;
            try
            {{
                return System.Text.Json.JsonSerializer.Deserialize<{output_type}>(json) ?? {fallback_expr};
            }}
            catch (System.OperationCanceledException)
            {{
                throw;
            }}
            catch (System.Exception ex)
            {{
                succeeded = false;
                GeneratedErrorLog.Write("JSON_DESERIALIZE", "JsonSerializer.Deserialize", ex);
                return {fallback_expr};
            }}
        }}
    }}
}}"""
        extra_code = path.setdefault("extra_code", [])
        if helper_code not in extra_code:
            extra_code.append(helper_code)
        return helper_name

    def _ensure_operation_result_helper(self, path: Dict[str, Any]) -> str:
        helper_name = "RunGeneratedOperationAsync"
        self._ensure_console_error_helper(path)
        helper_code = """namespace Generated
{
    internal readonly struct GeneratedOperationResult<T>
    {
        public GeneratedOperationResult(T value, bool succeeded)
        {
            Value = value;
            Succeeded = succeeded;
        }

        public T Value { get; }
        public bool Succeeded { get; }
    }

    public partial class GeneratedProcessor
    {
        private static async System.Threading.Tasks.Task<GeneratedOperationResult<T>> RunGeneratedOperationAsync<T>(
            System.Func<System.Threading.Tasks.Task<T>> operation,
            string intent,
            string methodName,
            T fallback)
        {
            try
            {
                return new GeneratedOperationResult<T>(await operation(), true);
            }
            catch (System.OperationCanceledException)
            {
                throw;
            }
            catch (System.Exception ex)
            {
                GeneratedErrorLog.Write(intent, methodName, ex);
                return new GeneratedOperationResult<T>(fallback, false);
            }
        }
    }
}"""
        extra_code = path.setdefault("extra_code", [])
        if helper_code not in extra_code:
            extra_code.append(helper_code)
        return helper_name

    def ensure_structured_http_get_string_helper(self, path: Dict[str, Any]) -> str:
        helper_name = "SendGeneratedHttpGetStringAsync"
        helper_code = """namespace Generated
{
    public partial class GeneratedProcessor
    {
        private static async System.Threading.Tasks.Task<string> SendGeneratedHttpGetStringAsync(
            System.Net.Http.HttpClient httpClient,
            string url,
            string headerName,
            string headerValue,
            int timeoutMs)
        {
            using var request = new System.Net.Http.HttpRequestMessage(System.Net.Http.HttpMethod.Get, url);
            request.Headers.Add(headerName, headerValue);
            using var requestTimeout = new System.Threading.CancellationTokenSource(System.TimeSpan.FromMilliseconds(timeoutMs));
            using var response = await httpClient.SendAsync(request, requestTimeout.Token);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadAsStringAsync(requestTimeout.Token);
        }
    }
}"""
        extra_code = path.setdefault("extra_code", [])
        if helper_code not in extra_code:
            extra_code.append(helper_code)
        return helper_name

    def ensure_text_file_read_helper(self, path: Dict[str, Any]) -> str:
        helper_name = "ReadGeneratedTextFileOrDefault"
        self._ensure_console_error_helper(path)
        helper_code = """namespace Generated
{
    public partial class GeneratedProcessor
    {
        private static string ReadGeneratedTextFileOrDefault(string path, out bool succeeded)
        {
            succeeded = true;
            try
            {
                return System.IO.File.ReadAllText(path);
            }
            catch (System.OperationCanceledException)
            {
                throw;
            }
            catch (System.Exception ex)
            {
                succeeded = false;
                GeneratedErrorLog.Write("FETCH", "File.ReadAllText", ex);
                return string.Empty;
            }
        }
    }
}"""
        extra_code = path.setdefault("extra_code", [])
        if helper_code not in extra_code:
            extra_code.append(helper_code)
        return helper_name

    def ensure_text_file_write_helper(self, path: Dict[str, Any]) -> str:
        helper_name = "WriteGeneratedTextFile"
        self._ensure_console_error_helper(path)
        helper_code = """namespace Generated
{
    public partial class GeneratedProcessor
    {
        private static bool WriteGeneratedTextFile(string path, string contents)
        {
            try
            {
                System.IO.File.WriteAllText(path, contents);
                return true;
            }
            catch (System.OperationCanceledException)
            {
                throw;
            }
            catch (System.Exception ex)
            {
                GeneratedErrorLog.Write("PERSIST", "File.WriteAllText", ex);
                return false;
            }
        }
    }
}"""
        extra_code = path.setdefault("extra_code", [])
        if helper_code not in extra_code:
            extra_code.append(helper_code)
        return helper_name

    def _default_local_declaration(self, var_type: str, out_var: str, path: Dict[str, Any]) -> Dict[str, Any]:
        type_defaults = {
            "int": "0", "long": "0L", "double": "0.0", "float": "0.0f", "decimal": "0m",
            "bool": "false", "string": "string.Empty"
        }
        default_val = type_defaults.get(var_type, "null")
        decl_type = var_type
        value_types = {"int", "long", "double", "float", "decimal", "bool", "char", "byte", "short", "uint", "ulong", "ushort", "DateTime", "Guid"}
        if "IEnumerable" in var_type or "List" in var_type:
            concrete = var_type.replace('IEnumerable', 'List')
            if not concrete.startswith("List<"):
                concrete = f"List<{concrete}>"
            default_val = f"new {concrete}()"
            path.setdefault("all_usings", set()).add("System.Collections.Generic")
        elif isinstance(var_type, str) and var_type.endswith("[]"):
            element_type = var_type[:-2].strip()
            default_val = f"Array.Empty<{element_type}>()"
            path.setdefault("all_usings", set()).add("System")
        elif default_val == "null" and isinstance(var_type, str) and var_type and not var_type.endswith("?") and var_type not in value_types:
            decl_type = f"{var_type}?"
        return {"type": "raw", "code": f"{decl_type} {out_var} = {default_val};", "var_type": decl_type}

    def _wrap_async_call_with_result_helper(
        self,
        stmt: Dict[str, Any],
        intent: str,
        method_name: str,
        path: Dict[str, Any],
        error_policy: str,
    ) -> List[Dict[str, Any]]:
        out_var = stmt.get("out_var")
        var_type = stmt.get("var_type", "var")
        call_expr = stmt.get("call_expr")
        if not out_var or not call_expr:
            return [stmt]

        hoisted_decl = self._default_local_declaration(var_type, out_var, path)
        existing_codes = [h.get("code") for h in path.setdefault("hoisted_statements", [])]
        if hoisted_decl["code"] not in existing_codes:
            path["hoisted_statements"].append(hoisted_decl)
            path.setdefault("used_names", set()).add(out_var)

        helper_name = self._ensure_operation_result_helper(path)
        result_var = self.get_semantic_var_name(
            {"target_entity": "operation"},
            f"GeneratedOperationResult<{var_type}>",
            "operationResult",
            path,
            prefix=f"{out_var}Operation",
            role="status",
        )
        catch_action = self._catch_action_for_policy(
            path=path,
            error_policy=error_policy,
            has_hoisted_result=True,
            hoisted_result_var=out_var,
            hoisted_result_type=var_type,
        )
        fallback_expr = out_var
        if (
            isinstance(hoisted_decl.get("var_type"), str)
            and hoisted_decl["var_type"].endswith("?")
            and isinstance(var_type, str)
            and not var_type.endswith("?")
        ):
            fallback_expr = f"{out_var}!"
        helper_call = (
            f"var {result_var} = await {helper_name}<{var_type}>("
            f"() => {call_expr}, "
            f"{self._csharp_string_literal(intent)}, "
            f"{self._csharp_string_literal(method_name)}, "
            f"{fallback_expr});"
        )
        statements = [
            {
                "type": "raw",
                "code": helper_call,
                "node_id": stmt.get("node_id"),
                "intent": intent,
            },
            {
                "type": "raw",
                "code": f"{out_var} = {result_var}.Value;",
                "node_id": stmt.get("node_id"),
                "intent": intent,
            },
        ]
        if catch_action:
            statements.append({
                "type": "raw",
                "code": f"if (!{result_var}.Succeeded) {catch_action}",
                "node_id": stmt.get("node_id"),
                "intent": intent,
            })
        path.setdefault("all_usings", set()).add("System")
        return statements

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
                code_lines.append(
                    self.render_try_catch(
                        stmt.get("body", []),
                        stmt.get("intent", ""),
                        stmt.get("method_name", ""),
                        path,
                        catch_body=stmt.get("catch_body"),
                        rethrow_operation_canceled=stmt.get("rethrow_operation_canceled", True),
                    )
                )

        return "\n".join(code_lines)

    def render_try_catch(
        self,
        body: List[Dict[str, Any]],
        intent: str,
        method_name: str,
        path: Dict[str, Any],
        error_policy: str = "return_default",
        has_hoisted_result: bool = False,
        hoisted_result_var: str | None = None,
        hoisted_result_type: str | None = None,
        catch_body: List[Dict[str, Any]] | None = None,
        rethrow_operation_canceled: bool = True,
    ) -> str:
        cur_indent = path.get("indent_level", 2)
        indent = "    " * cur_indent
        inner_path = path.copy()
        inner_path["indent_level"] = cur_indent + 1
        body_code = self.render_statements(body, inner_path)

        code = f"{indent}try\n{indent}{{\n{body_code}\n{indent}}}\n"

        effective_catch_body = catch_body
        if effective_catch_body is None:
            effective_catch_body = self._build_catch_body(
                intent=intent,
                method_name=method_name,
                path=path,
                error_policy=error_policy,
                has_hoisted_result=has_hoisted_result,
                hoisted_result_var=hoisted_result_var,
                hoisted_result_type=hoisted_result_type,
            )
        catch_code = self.render_statements(effective_catch_body, inner_path)
        if rethrow_operation_canceled:
            code += (
                f"{indent}catch (OperationCanceledException)\n"
                f"{indent}{{\n"
                f"{indent}    throw;\n"
                f"{indent}}}\n"
            )
        code += (
            f"{indent}catch (Exception ex)\n"
            f"{indent}{{\n"
            f"{catch_code}\n"
            f"{indent}}}"
        )
        path.setdefault("all_usings", set()).add("System")
        return code

    def wrap_with_try_catch(self, stmt: Dict[str, Any], intent: str, method_name: str, path: Dict[str, Any], error_policy: str = "return_default") -> Any:
        # 27.275: Phase 5 D-2 Wrapped with pre-rendering to handle indentation in raw blocks
        resilient_intents = [INTENT_DATABASE_QUERY, INTENT_HTTP_REQUEST, INTENT_FILE_IO, INTENT_FETCH, INTENT_PERSIST, INTENT_JSON_DESERIALIZE]
        if intent not in resilient_intents:
            return stmt

        out_var = stmt.get("out_var")
        var_type = stmt.get("var_type", "var")
        if (
            error_policy == "return_default"
            and stmt.get("type") == "call"
            and stmt.get("is_async")
            and out_var
            and stmt.get("call_expr")
            and intent in [INTENT_DATABASE_QUERY, INTENT_HTTP_REQUEST, INTENT_PERSIST]
        ):
            return self._wrap_async_call_with_result_helper(
                stmt,
                intent,
                method_name,
                path,
                error_policy,
            )

        hoisted_decl = None
        if out_var:
            hoisted_decl = self._default_local_declaration(var_type, out_var, path)

            existing_codes = [h.get("code") for h in path.setdefault("hoisted_statements", [])]
            if hoisted_decl["code"] not in existing_codes:
                path["hoisted_statements"].append(hoisted_decl)
                path.setdefault("used_names", set()).add(out_var)
            stmt_copy = stmt.copy(); stmt_copy["is_assignment_only"] = True
            stmt_body = [stmt_copy]
        else:
            stmt_body = [stmt]

        catch_body = self._build_catch_body(
            intent=intent,
            method_name=method_name,
            path=path,
            error_policy=error_policy,
            has_hoisted_result=hoisted_decl is not None,
            hoisted_result_var=out_var,
            hoisted_result_type=var_type,
        )
        path.setdefault("all_usings", set()).add("System")
        return {
            "type": "try_catch",
            "body": stmt_body,
            "catch_body": catch_body,
            "rethrow_operation_canceled": True,
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
            if stmt.get("call_expr"):
                stmt["call_expr"] = stmt["call_expr"].replace(f"<{old}>", f"<{new}>")
            if stmt.get("code"):
                stmt["code"] = stmt["code"].replace(f"<{old}>", f"<{new}>").replace(old, new)
            if stmt.get("var_type"): stmt["var_type"] = stmt["var_type"].replace(old, new)
            if stmt.get("body"): self.fix_placeholders_recursive(stmt["body"], old, new)
            if stmt.get("else_body"): self.fix_placeholders_recursive(stmt["else_body"], old, new)
            if stmt.get("catch_body"): self.fix_placeholders_recursive(stmt["catch_body"], old, new)
