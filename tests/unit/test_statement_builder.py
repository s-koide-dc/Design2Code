# -*- coding: utf-8 -*-
import unittest

from src.code_synthesis.statement_builder import StatementBuilder


class TestStatementBuilder(unittest.TestCase):
    def test_render_try_catch_formats_return_line_with_block_indent(self):
        builder = StatementBuilder(type_system=None)
        path = {"indent_level": 2, "method_return_type": "bool"}
        code = builder.render_try_catch(
            [{"type": "raw", "code": 'content = File.ReadAllText("input.txt");'}],
            "FETCH",
            "ReadAllText",
            path,
        )

        return_lines = [line for line in code.splitlines() if "return false;" in line]
        self.assertEqual(["            return false;"], return_lines)
        self.assertIn('GeneratedErrorLog.Write("FETCH", "ReadAllText", ex);', code)
        self.assertEqual(1, len(path.get("extra_code") or []))

    def test_render_try_catch_returns_hoisted_result_when_type_matches(self):
        builder = StatementBuilder(type_system=None)
        code = builder.render_try_catch(
            [{"type": "raw", "code": "result0 = Load();"}],
            "FETCH",
            "Load",
            {"indent_level": 2, "method_return_type": "string"},
            has_hoisted_result=True,
            hoisted_result_var="result0",
            hoisted_result_type="string",
        )

        self.assertIn("            return result0;", code)
        self.assertNotIn("return null;", code)

    def test_console_error_helper_is_registered_once_per_path(self):
        builder = StatementBuilder(type_system=None)
        path = {"indent_level": 2, "method_return_type": "string"}

        builder.render_try_catch(
            [{"type": "raw", "code": "first = LoadFirst();"}],
            "FETCH",
            "LoadFirst",
            path,
        )
        builder.render_try_catch(
            [{"type": "raw", "code": "second = LoadSecond();"}],
            "FETCH",
            "LoadSecond",
            path,
        )

        extra_code = path.get("extra_code") or []
        self.assertEqual(1, len(extra_code))
        self.assertIn("internal static class GeneratedErrorLog", extra_code[0])

    def test_wrap_with_try_catch_returns_structured_statement(self):
        builder = StatementBuilder(type_system=None)
        path = {"indent_level": 2, "method_return_type": "string"}

        wrapped = builder.wrap_with_try_catch(
            {
                "type": "call",
                "call_expr": 'File.ReadAllText("input.txt")',
                "out_var": "content",
                "var_type": "string",
            },
            "FETCH",
            "File.ReadAllText",
            path,
        )

        self.assertEqual("try_catch", wrapped["type"])
        self.assertTrue(wrapped["rethrow_operation_canceled"])
        self.assertEqual("content", wrapped["out_var"])
        self.assertEqual("string", wrapped["var_type"])
        self.assertEqual(True, wrapped["body"][0]["is_assignment_only"])
        catch_codes = [stmt.get("code") for stmt in wrapped["catch_body"]]
        self.assertIn('GeneratedErrorLog.Write("FETCH", "File.ReadAllText", ex);', catch_codes)
        self.assertIn("return content;", catch_codes)

    def test_wrap_async_resilient_call_uses_operation_result_helper(self):
        builder = StatementBuilder(type_system=None)
        path = {"indent_level": 2, "method_return_type": "Task<bool>", "is_async_needed": True}

        wrapped = builder.wrap_with_try_catch(
            {
                "type": "call",
                "call_expr": '_dbConnection.QueryAsync<User>("SELECT * FROM Users", null)',
                "out_var": "users",
                "var_type": "IEnumerable<User>",
                "is_async": True,
            },
            "DATABASE_QUERY",
            "Query",
            path,
        )

        self.assertIsInstance(wrapped, list)
        codes = [stmt.get("code", "") for stmt in wrapped]
        self.assertTrue(any("RunGeneratedOperationAsync<IEnumerable<User>>" in code for code in codes))
        self.assertTrue(any("users = usersOperation.Value;" in code for code in codes))
        self.assertTrue(any("if (!usersOperation.Succeeded) return default;" in code for code in codes))
        self.assertTrue(any("IEnumerable<User> users = new List<User>();" == h.get("code") for h in path.get("hoisted_statements", [])))
        extra_code = "\n".join(path.get("extra_code", []))
        self.assertIn("GeneratedOperationResult<T>", extra_code)
        self.assertIn("RunGeneratedOperationAsync<T>", extra_code)
        self.assertIn("catch (System.OperationCanceledException)", extra_code)

    def test_structured_http_get_string_helper_is_registered_once(self):
        builder = StatementBuilder(type_system=None)
        path = {}

        first_name = builder.ensure_structured_http_get_string_helper(path)
        second_name = builder.ensure_structured_http_get_string_helper(path)

        self.assertEqual("SendGeneratedHttpGetStringAsync", first_name)
        self.assertEqual(first_name, second_name)
        self.assertEqual(1, len(path.get("extra_code") or []))
        helper_code = path["extra_code"][0]
        self.assertIn("System.Net.Http.HttpRequestMessage", helper_code)
        self.assertIn("request.Headers.Add(headerName, headerValue);", helper_code)
        self.assertIn("httpClient.SendAsync(request, requestTimeout.Token)", helper_code)

    def test_text_file_helpers_are_registered_once(self):
        builder = StatementBuilder(type_system=None)
        path = {}

        read_name = builder.ensure_text_file_read_helper(path)
        write_name = builder.ensure_text_file_write_helper(path)
        builder.ensure_text_file_read_helper(path)
        builder.ensure_text_file_write_helper(path)

        self.assertEqual("ReadGeneratedTextFileOrDefault", read_name)
        self.assertEqual("WriteGeneratedTextFile", write_name)
        extra_code = "\n".join(path.get("extra_code", []))
        self.assertEqual(3, len(path.get("extra_code", [])))
        self.assertIn("System.IO.File.ReadAllText(path)", extra_code)
        self.assertIn("System.IO.File.WriteAllText(path, contents)", extra_code)
        self.assertIn("GeneratedErrorLog.Write", extra_code)

    def test_render_statements_uses_structured_try_catch_catch_body(self):
        builder = StatementBuilder(type_system=None)
        path = {"indent_level": 2, "method_return_type": "bool"}

        code = builder.render_statements(
            [{
                "type": "try_catch",
                "body": [{"type": "raw", "code": "Run();"}],
                "catch_body": [{"type": "raw", "code": "return false;"}],
                "rethrow_operation_canceled": False,
                "intent": "FETCH",
                "method_name": "Run",
            }],
            path,
        )

        self.assertIn("            Run();", code)
        self.assertIn("            return false;", code)
        self.assertNotIn("OperationCanceledException", code)
        self.assertNotIn("GeneratedErrorLog.Write", code)

    def test_fix_placeholders_updates_call_expr_and_catch_body(self):
        builder = StatementBuilder(type_system=None)
        statements = [{
            "type": "try_catch",
            "body": [{
                "type": "call",
                "method": "Query<OldEntity>",
                "call_expr": "Query<OldEntity>()",
                "var_type": "List<OldEntity>",
            }],
            "catch_body": [{
                "type": "raw",
                "code": "return new List<OldEntity>();",
                "var_type": "List<OldEntity>",
            }],
        }]

        builder.fix_placeholders_recursive(statements, "OldEntity", "NewEntity")

        body_stmt = statements[0]["body"][0]
        catch_stmt = statements[0]["catch_body"][0]
        self.assertEqual("Query<NewEntity>", body_stmt["method"])
        self.assertEqual("Query<NewEntity>()", body_stmt["call_expr"])
        self.assertEqual("List<NewEntity>", body_stmt["var_type"])
        self.assertEqual("return new List<NewEntity>();", catch_stmt["code"])
        self.assertEqual("List<NewEntity>", catch_stmt["var_type"])


if __name__ == "__main__":
    unittest.main()
