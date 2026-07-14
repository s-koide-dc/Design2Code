# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple


_ASSERTION_KEYS = {
    "await",
    "method_args",
    "fixtures",
    "http_responses",
    "sqlite",
    "db_assertions",
    "return",
    "stdout",
    "stderr",
    "files",
    "http_requests",
}


_SUPPORTED_ARG_TYPES = (str, int, float, bool)


def _parse_json_object(value: Any) -> Tuple[Dict[str, Any] | None, str | None]:
    if not isinstance(value, str):
        return None, "expected value is not a string"
    text = value.strip()
    if not text:
        return None, "expected value is empty"
    if not text.startswith("{"):
        return None, None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"expected JSON is invalid: {exc.msg}"
    if not isinstance(parsed, dict):
        return None, "expected JSON must be an object"
    return parsed, None


def _as_string_list(value: Any, path: str) -> Tuple[List[str], List[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], [f"{path} must be a list"]
    items: List[str] = []
    issues: List[str] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            items.append(item)
        else:
            issues.append(f"{path}[{index}] must be a string")
    return items, issues


def _normalize_text_assertion(value: Any, path: str) -> Tuple[Dict[str, Any], List[str]]:
    if value is None:
        return {}, []
    if not isinstance(value, dict):
        return {}, [f"{path} must be an object"]
    normalized: Dict[str, Any] = {}
    issues: List[str] = []
    for key in ("contains", "not_contains"):
        items, item_issues = _as_string_list(value.get(key), f"{path}.{key}")
        if items:
            normalized[key] = items
        issues.extend(item_issues)
    unknown = sorted(k for k in value if k not in {"contains", "not_contains"})
    for key in unknown:
        issues.append(f"{path}.{key} is not a supported assertion")
    return normalized, issues


def _normalize_files(value: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["files must be a list"]
    normalized: List[Dict[str, Any]] = []
    issues: List[str] = []
    for index, item in enumerate(value):
        path = f"files[{index}]"
        if not isinstance(item, dict):
            issues.append(f"{path} must be an object")
            continue
        file_path = item.get("path")
        if not isinstance(file_path, str) or not file_path.strip():
            issues.append(f"{path}.path must be a non-empty string")
            continue
        text_assertion, text_issues = _normalize_text_assertion(
            {key: item.get(key) for key in ("contains", "not_contains") if key in item},
            path,
        )
        file_contract = {"path": file_path.strip()}
        file_contract.update(text_assertion)
        normalized.append(file_contract)
        issues.extend(text_issues)
        unknown = sorted(k for k in item if k not in {"path", "contains", "not_contains"})
        for key in unknown:
            issues.append(f"{path}.{key} is not a supported assertion")
    return normalized, issues


def _normalize_method_args(value: Any) -> Tuple[List[Any], List[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["method_args must be a list"]
    args: List[Any] = []
    issues: List[str] = []
    for index, item in enumerate(value):
        if item is None or isinstance(item, _SUPPORTED_ARG_TYPES):
            args.append(item)
        else:
            issues.append(f"method_args[{index}] must be a string, number, boolean, or null")
    return args, issues


def _normalize_fixtures(value: Any) -> Tuple[List[Dict[str, str]], List[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["fixtures must be a list"]
    fixtures: List[Dict[str, str]] = []
    issues: List[str] = []
    for index, item in enumerate(value):
        path = f"fixtures[{index}]"
        if not isinstance(item, dict):
            issues.append(f"{path} must be an object")
            continue
        fixture_path = item.get("path")
        content = item.get("content")
        if not isinstance(fixture_path, str) or not fixture_path.strip():
            issues.append(f"{path}.path must be a non-empty string")
            continue
        if not isinstance(content, str):
            issues.append(f"{path}.content must be a string")
            continue
        fixtures.append({"path": fixture_path.strip(), "content": content})
        unknown = sorted(k for k in item if k not in {"path", "content"})
        for key in unknown:
            issues.append(f"{path}.{key} is not supported")
    return fixtures, issues


def _normalize_http_requests(value: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["http_requests must be a list"]
    normalized: List[Dict[str, Any]] = []
    issues: List[str] = []
    for index, item in enumerate(value):
        path = f"http_requests[{index}]"
        if not isinstance(item, dict):
            issues.append(f"{path} must be an object")
            continue
        request: Dict[str, Any] = {}
        for key in ("method", "url"):
            value_at_key = item.get(key)
            if isinstance(value_at_key, str) and value_at_key.strip():
                request[key] = value_at_key.strip()
        if not request:
            issues.append(f"{path} must include method or url")
            continue
        normalized.append(request)
        unknown = sorted(k for k in item if k not in {"method", "url"})
        for key in unknown:
            issues.append(f"{path}.{key} is not a supported assertion")
    return normalized, issues


def _normalize_http_responses(value: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["http_responses must be a list"]
    normalized: List[Dict[str, Any]] = []
    issues: List[str] = []
    for index, item in enumerate(value):
        path = f"http_responses[{index}]"
        if not isinstance(item, dict):
            issues.append(f"{path} must be an object")
            continue
        body = item.get("body")
        if not isinstance(body, str):
            issues.append(f"{path}.body must be a string")
            continue
        status_code = item.get("status_code", 200)
        if isinstance(status_code, bool) or not isinstance(status_code, int):
            issues.append(f"{path}.status_code must be an integer")
            continue
        response = {
            "status_code": status_code,
            "body": body,
        }
        content_type = item.get("content_type")
        if isinstance(content_type, str) and content_type.strip():
            response["content_type"] = content_type.strip()
        normalized.append(response)
        unknown = sorted(k for k in item if k not in {"status_code", "body", "content_type"})
        for key in unknown:
            issues.append(f"{path}.{key} is not supported")
    return normalized, issues


def _normalize_sqlite(value: Any) -> Tuple[Dict[str, Any], List[str]]:
    if value is None:
        return {}, []
    if not isinstance(value, dict):
        return {}, ["sqlite must be an object"]
    normalized: Dict[str, Any] = {}
    issues: List[str] = []
    for key in ("schema", "seed"):
        statements = value.get(key)
        if statements is None:
            continue
        if not isinstance(statements, list):
            issues.append(f"sqlite.{key} must be a list")
            continue
        normalized_statements: List[str] = []
        for index, statement in enumerate(statements):
            if isinstance(statement, str) and statement.strip():
                normalized_statements.append(statement)
            else:
                issues.append(f"sqlite.{key}[{index}] must be a non-empty string")
        if normalized_statements:
            normalized[key] = normalized_statements
    unknown = sorted(k for k in value if k not in {"schema", "seed"})
    for key in unknown:
        issues.append(f"sqlite.{key} is not supported")
    if not normalized and not issues:
        issues.append("sqlite must include schema or seed statements")
    return normalized, issues


def _normalize_db_assertions(value: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["db_assertions must be a list"]
    assertions: List[Dict[str, Any]] = []
    issues: List[str] = []
    for index, item in enumerate(value):
        path = f"db_assertions[{index}]"
        if not isinstance(item, dict):
            issues.append(f"{path} must be an object")
            continue
        query = item.get("query")
        if not isinstance(query, str) or not query.strip():
            issues.append(f"{path}.query must be a non-empty string")
            continue
        assertion: Dict[str, Any] = {"query": query.strip()}
        if "equals" in item:
            if item["equals"] is None or isinstance(item["equals"], _SUPPORTED_ARG_TYPES):
                assertion["equals"] = item["equals"]
            else:
                issues.append(f"{path}.equals must be a string, number, boolean, or null")
        if "not_null" in item:
            if isinstance(item["not_null"], bool):
                assertion["not_null"] = item["not_null"]
            else:
                issues.append(f"{path}.not_null must be a boolean")
        if "contains" in item:
            if isinstance(item["contains"], str):
                assertion["contains"] = item["contains"]
            else:
                issues.append(f"{path}.contains must be a string")
        if len(assertion) == 1:
            issues.append(f"{path} must include equals, not_null, or contains")
            continue
        assertions.append(assertion)
        unknown = sorted(k for k in item if k not in {"query", "equals", "not_null", "contains"})
        for key in unknown:
            issues.append(f"{path}.{key} is not supported")
    return assertions, issues


def normalize_runtime_oracle_contract(value: Any) -> Tuple[Dict[str, Any], List[str]]:
    if not isinstance(value, dict):
        return {}, ["runtime_oracle must be an object"]

    issues: List[str] = []
    contract: Dict[str, Any] = {}

    if "await" in value:
        if isinstance(value["await"], bool):
            contract["await"] = value["await"]
        else:
            issues.append("await must be a boolean")
    method_args, method_arg_issues = _normalize_method_args(value.get("method_args"))
    fixtures, fixture_issues = _normalize_fixtures(value.get("fixtures"))
    if "return" in value:
        contract["return"] = value["return"]

    stdout, stdout_issues = _normalize_text_assertion(value.get("stdout"), "stdout")
    stderr, stderr_issues = _normalize_text_assertion(value.get("stderr"), "stderr")
    files, file_issues = _normalize_files(value.get("files"))
    http_responses, http_response_issues = _normalize_http_responses(value.get("http_responses"))
    http_requests, http_issues = _normalize_http_requests(value.get("http_requests"))
    sqlite, sqlite_issues = _normalize_sqlite(value.get("sqlite"))
    db_assertions, db_assertion_issues = _normalize_db_assertions(value.get("db_assertions"))

    if method_args:
        contract["method_args"] = method_args
    if fixtures:
        contract["fixtures"] = fixtures
    if http_responses:
        contract["http_responses"] = http_responses
    if sqlite:
        contract["sqlite"] = sqlite
    if db_assertions:
        contract["db_assertions"] = db_assertions
    if stdout:
        contract["stdout"] = stdout
    if stderr:
        contract["stderr"] = stderr
    if files:
        contract["files"] = files
    if http_requests:
        contract["http_requests"] = http_requests

    issues.extend(method_arg_issues)
    issues.extend(fixture_issues)
    issues.extend(http_response_issues)
    issues.extend(sqlite_issues)
    issues.extend(db_assertion_issues)
    issues.extend(stdout_issues)
    issues.extend(stderr_issues)
    issues.extend(file_issues)
    issues.extend(http_issues)

    unknown = sorted(k for k in value if k not in _ASSERTION_KEYS)
    for key in unknown:
        issues.append(f"{key} is not a supported runtime_oracle assertion")
    if not contract and not issues:
        issues.append("runtime_oracle has no assertions")
    return contract, issues


def _csharp_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _csharp_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return _csharp_string_literal(value)
    raise TypeError(f"Unsupported oracle literal type: {type(value).__name__}")


def _render_text_assertions(expression: str, assertion: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for expected in assertion.get("contains", []) or []:
        lines.append(f"        Assert.Contains({_csharp_string_literal(expected)}, {expression});")
    for expected in assertion.get("not_contains", []) or []:
        lines.append(f"        Assert.DoesNotContain({_csharp_string_literal(expected)}, {expression});")
    return lines


def _render_http_handler(responses: List[Dict[str, Any]]) -> List[str]:
    if not responses:
        return []
    response_items = []
    for response in responses:
        response_items.append(
            "        new RuntimeOracleHttpResponse("
            f"{int(response['status_code'])}, "
            f"{_csharp_string_literal(response['body'])}, "
            f"{_csharp_string_literal(response.get('content_type', 'application/json'))})"
        )
    return [
        "public sealed record RuntimeOracleHttpResponse(int StatusCode, string Body, string ContentType);",
        "",
        "public sealed class RuntimeOracleHttpHandler : HttpMessageHandler",
        "{",
        "    private readonly Queue<RuntimeOracleHttpResponse> _responses;",
        "    public RuntimeOracleHttpHandler(IEnumerable<RuntimeOracleHttpResponse> responses)",
        "    {",
        "        _responses = new Queue<RuntimeOracleHttpResponse>(responses);",
        "    }",
        "",
        "    public List<HttpRequestMessage> Requests { get; } = new List<HttpRequestMessage>();",
        "",
        "    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)",
        "    {",
        "        Requests.Add(request);",
        '        var responseSpec = _responses.Count > 0 ? _responses.Dequeue() : new RuntimeOracleHttpResponse(500, "No runtime oracle response configured.", "text/plain");',
        "        var response = new HttpResponseMessage((HttpStatusCode)responseSpec.StatusCode)",
        "        {",
        "            Content = new StringContent(responseSpec.Body)",
        "        };",
        "        response.Content.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue(responseSpec.ContentType);",
        "        return Task.FromResult(response);",
        "    }",
        "}",
        "",
        "public static class RuntimeOracleHttpFixtures",
        "{",
        "    public static IReadOnlyList<RuntimeOracleHttpResponse> Responses { get; } = new List<RuntimeOracleHttpResponse>",
        "    {",
        ",\n".join(response_items),
        "    };",
        "}",
        "",
    ]


def _render_sqlite_setup(sqlite: Dict[str, Any]) -> List[str]:
    if not sqlite:
        return []
    lines = [
        '        await using var connection = new SqliteConnection("Data Source=:memory:");',
        "        await connection.OpenAsync();",
    ]
    for statement in sqlite.get("schema", []) or []:
        lines.append(f"        await connection.ExecuteAsync({_csharp_string_literal(statement)});")
    for statement in sqlite.get("seed", []) or []:
        lines.append(f"        await connection.ExecuteAsync({_csharp_string_literal(statement)});")
    return lines


def _render_db_assertions(assertions: List[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    for index, assertion in enumerate(assertions):
        value_var = f"dbValue{index}"
        query_literal = _csharp_string_literal(assertion["query"])
        lines.append(f"            var {value_var} = await connection.QuerySingleOrDefaultAsync<object>({query_literal});")
        if assertion.get("not_null"):
            lines.append(f"            Assert.NotNull({value_var});")
        if "equals" in assertion:
            lines.append(f"            Assert.Equal({_csharp_literal(assertion['equals'])}, {value_var});")
        if "contains" in assertion:
            lines.append(f"            Assert.Contains({_csharp_string_literal(assertion['contains'])}, {value_var}?.ToString());")
    return lines


def build_runtime_oracle_test_code(module_name: str, contract: Dict[str, Any]) -> str:
    method_args = ", ".join(_csharp_literal(arg) for arg in contract.get("method_args", []) or [])
    fixtures = contract.get("fixtures", []) or []
    http_responses = contract.get("http_responses", []) or []
    http_requests = contract.get("http_requests", []) or []
    uses_http = bool(http_responses or http_requests)
    sqlite = contract.get("sqlite", {}) or {}
    db_assertions = contract.get("db_assertions", []) or []
    uses_sqlite = bool(sqlite or db_assertions)
    file_assertions = contract.get("files", []) or []
    has_stdout = bool(contract.get("stdout"))
    awaits_call = bool(contract.get("await"))
    call_prefix = "var result = " if "return" in contract else ""
    test_signature = "public async Task ExplicitRuntimeOraclePasses()" if awaits_call or uses_sqlite else "public void ExplicitRuntimeOraclePasses()"
    await_prefix = "await " if awaits_call else ""
    if uses_sqlite and uses_http:
        processor_expr = "new GeneratedProcessor(connection, httpClient)"
    elif uses_sqlite:
        processor_expr = "new GeneratedProcessor(connection)"
    elif uses_http:
        processor_expr = "new GeneratedProcessor(httpClient)"
    else:
        processor_expr = "new GeneratedProcessor()"
    lines: List[str] = [
        "using System;",
        "using System.Collections.Generic;",
        "using System.Globalization;",
        "using System.IO;",
        "using System.Net;",
        "using System.Net.Http;",
        "using System.Threading;",
        "using System.Threading.Tasks;",
        "using Xunit;",
        "",
    ]
    if uses_sqlite:
        lines.insert(-2, "using Dapper;")
        lines.insert(-2, "using Microsoft.Data.Sqlite;")
    lines.extend(_render_http_handler(http_responses if http_responses else [{"status_code": 500, "body": ""}] if uses_http else []))
    lines.extend([
        "public class RuntimeOracleTest",
        "{",
        "    [Fact]",
        f"    {test_signature}",
        "    {",
        '        var root = Path.Combine(Path.GetTempPath(), "runtime-oracle-" + Guid.NewGuid().ToString("N"));',
        "        Directory.CreateDirectory(root);",
        "        var previousDirectory = Directory.GetCurrentDirectory();",
        "        var originalOut = Console.Out;",
        "        using var capturedOut = new StringWriter(CultureInfo.InvariantCulture);",
    ])
    if uses_http:
        lines.extend([
            "        var handler = new RuntimeOracleHttpHandler(RuntimeOracleHttpFixtures.Responses);",
            "        using var httpClient = new HttpClient(handler);",
        ])
    lines.extend(_render_sqlite_setup(sqlite))
    lines.extend([
        "        try",
        "        {",
        "            Directory.SetCurrentDirectory(root);",
    ])
    for fixture in fixtures:
        lines.append(
            f"            File.WriteAllText({_csharp_string_literal(fixture['path'])}, {_csharp_string_literal(fixture['content'])});"
        )
    if has_stdout:
        lines.append("            Console.SetOut(capturedOut);")
    lines.extend([
        "",
        f"            {call_prefix}{await_prefix}{processor_expr}.{module_name}({method_args});",
    ])
    if "return" in contract:
        lines.append(f"            Assert.Equal({_csharp_literal(contract['return'])}, result);")
    if has_stdout:
        lines.append("            var stdout = capturedOut.ToString();")
        lines.extend(_render_text_assertions("stdout", contract["stdout"]))
    for file_assertion in file_assertions:
        file_path = _csharp_string_literal(file_assertion["path"])
        lines.append(f"            Assert.True(File.Exists({file_path}), \"Expected output file to exist: {file_assertion['path']}\");")
        if file_assertion.get("contains") or file_assertion.get("not_contains"):
            file_var = f"fileText{len(lines)}"
            lines.append(f"            var {file_var} = File.ReadAllText({file_path});")
            lines.extend(_render_text_assertions(file_var, file_assertion))
    if http_requests:
        lines.append(f"            Assert.Equal({len(http_requests)}, handler.Requests.Count);")
        for index, request in enumerate(http_requests):
            if request.get("method"):
                lines.append(
                    f"            Assert.Equal({_csharp_string_literal(request['method'].upper())}, handler.Requests[{index}].Method.Method);"
                )
            if request.get("url"):
                lines.append(
                    f"            Assert.Equal({_csharp_string_literal(request['url'])}, handler.Requests[{index}].RequestUri?.ToString());"
                )
    if db_assertions:
        lines.extend(_render_db_assertions(db_assertions))
    lines.extend([
        "        }",
        "        finally",
        "        {",
        "            Console.SetOut(originalOut);",
        "            Directory.SetCurrentDirectory(previousDirectory);",
        "            if (Directory.Exists(root))",
        "                Directory.Delete(root, recursive: true);",
        "        }",
        "    }",
        "}",
    ])
    return "\n".join(lines)


def execute_runtime_oracles(
    *,
    source_code: str,
    module_name: str,
    oracle_summary: Dict[str, Any],
    verifier: Any,
    dependencies: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    cases = oracle_summary.get("cases", []) if isinstance(oracle_summary, dict) else []
    results: List[Dict[str, Any]] = []
    ready_cases = [case for case in cases if isinstance(case, dict) and case.get("status") == "ready"]
    for case in ready_cases:
        contract = case.get("contract") if isinstance(case.get("contract"), dict) else {}
        test_code = build_runtime_oracle_test_code(module_name, contract)
        runtime_result = verifier.verify_runtime(
            source_code,
            test_code,
            dependencies=_merge_runtime_oracle_dependencies(dependencies or [], contract),
        )
        results.append({
            "id": case.get("id"),
            "scenario": case.get("scenario"),
            "success": bool(runtime_result.get("success")),
            "summary": runtime_result.get("summary", {}),
            "failures": runtime_result.get("failures", []),
            "error_type": runtime_result.get("error_type"),
            "message": runtime_result.get("message") or runtime_result.get("error"),
        })

    failed = [result for result in results if not result.get("success")]
    return {
        "requested": True,
        "case_count": len(ready_cases),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "valid": not failed,
        "results": results,
    }


def _merge_runtime_oracle_dependencies(
    dependencies: List[Dict[str, str]],
    contract: Dict[str, Any],
) -> List[Dict[str, str]]:
    merged = list(dependencies)
    existing = {str(dep.get("name") or "") for dep in merged if isinstance(dep, dict)}
    if contract.get("sqlite") or contract.get("db_assertions"):
        if "Dapper" not in existing:
            merged.append({"name": "Dapper", "version": "2.1.35"})
            existing.add("Dapper")
        if "Microsoft.Data.Sqlite" not in existing:
            merged.append({"name": "Microsoft.Data.Sqlite", "version": "10.0.0"})
    return merged


def summarize_runtime_oracles(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize explicit runtime oracle coverage from StructuredSpec test cases.

    The extractor intentionally accepts only explicit JSON contracts. Natural
    language expectations remain visible as unverified cases instead of being
    guessed through keyword matching.
    """
    test_cases = spec.get("test_cases", []) if isinstance(spec, dict) else []
    cases: List[Dict[str, Any]] = []
    issues: List[str] = []

    for index, test_case in enumerate(test_cases):
        if not isinstance(test_case, dict):
            issues.append(f"test_cases[{index}] must be an object")
            continue
        case_id = str(test_case.get("id") or f"tc_{index + 1}")
        scenario = str(test_case.get("scenario") or "")
        parsed, parse_issue = _parse_json_object(test_case.get("expected"))
        if parsed is None:
            status = "invalid" if parse_issue else "unverified"
            reason = parse_issue or "expected is not an explicit JSON runtime_oracle contract"
            case_summary = {
                "id": case_id,
                "scenario": scenario,
                "status": status,
                "reason": reason,
            }
            cases.append(case_summary)
            if status == "invalid":
                issues.append(f"{case_id}: {reason}")
            continue

        oracle = parsed.get("runtime_oracle")
        if oracle is None:
            cases.append({
                "id": case_id,
                "scenario": scenario,
                "status": "unverified",
                "reason": "expected JSON does not include runtime_oracle",
            })
            continue

        contract, contract_issues = normalize_runtime_oracle_contract(oracle)
        if contract_issues:
            cases.append({
                "id": case_id,
                "scenario": scenario,
                "status": "invalid",
                "contract": contract,
                "issues": contract_issues,
            })
            issues.extend(f"{case_id}: {issue}" for issue in contract_issues)
            continue

        cases.append({
            "id": case_id,
            "scenario": scenario,
            "status": "ready",
            "contract": contract,
        })

    ready_count = sum(1 for case in cases if case.get("status") == "ready")
    invalid_count = sum(1 for case in cases if case.get("status") == "invalid")
    unverified_count = sum(1 for case in cases if case.get("status") == "unverified")
    return {
        "case_count": len(test_cases),
        "ready_count": ready_count,
        "invalid_count": invalid_count,
        "unverified_count": unverified_count,
        "has_explicit_oracles": ready_count > 0,
        "valid": invalid_count == 0,
        "issues": issues,
        "cases": cases,
    }
