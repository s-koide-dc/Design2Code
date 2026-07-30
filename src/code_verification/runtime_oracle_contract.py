# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple


ASSERTION_KEYS = {
    "await",
    "method_args",
    "stdin",
    "fixtures",
    "environment",
    "http_responses",
    "sqlite",
    "db_assertions",
    "db_rows",
    "return",
    "stdout",
    "stderr",
    "exception",
    "files",
    "http_requests",
}


SUPPORTED_LITERAL_TYPES = (str, int, float, bool)
SUPPORTED_DB_SCALAR_TYPES = {"string", "int", "long", "decimal", "bool"}


def _is_valid_db_scalar_value(value: Any, scalar_type: str) -> bool:
    if value is None:
        return True
    if scalar_type == "string":
        return isinstance(value, str)
    if scalar_type in {"int", "long"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if scalar_type == "decimal":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if scalar_type == "bool":
        return isinstance(value, bool)
    return False


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


def _normalize_exception(value: Any) -> Tuple[Dict[str, Any], List[str]]:
    if value is None:
        return {}, []
    if not isinstance(value, dict):
        return {}, ["exception must be an object"]
    type_name = value.get("type")
    if not isinstance(type_name, str) or not type_name.strip():
        return {}, ["exception.type must be a non-empty string"]
    normalized: Dict[str, Any] = {"type": type_name.strip()}
    message, message_issues = _normalize_text_assertion(value.get("message"), "exception.message")
    if message:
        normalized["message"] = message
    issues = list(message_issues)
    for key in sorted(key for key in value if key not in {"type", "message"}):
        issues.append(f"exception.{key} is not supported")
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
        if item is None or isinstance(item, SUPPORTED_LITERAL_TYPES):
            args.append(item)
        else:
            issues.append(f"method_args[{index}] must be a string, number, boolean, or null")
    return args, issues


def _normalize_stdin(value: Any) -> Tuple[str, List[str]]:
    if value is None:
        return "", []
    if not isinstance(value, str):
        return "", ["stdin must be a string"]
    return value, []


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


def _normalize_environment(value: Any) -> Tuple[Dict[str, str | None], List[str]]:
    if value is None:
        return {}, []
    if not isinstance(value, dict):
        return {}, ["environment must be an object"]
    normalized: Dict[str, str | None] = {}
    issues: List[str] = []
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            issues.append("environment keys must be non-empty strings")
            continue
        if item is None or isinstance(item, str):
            normalized[key.strip()] = item
        else:
            issues.append(f"environment.{key} must be a string or null")
    if not normalized and not issues:
        issues.append("environment must include at least one variable")
    return normalized, issues


def _normalize_string_map(value: Any, path: str) -> Tuple[Dict[str, str], List[str]]:
    if value is None:
        return {}, []
    if not isinstance(value, dict):
        return {}, [f"{path} must be an object"]
    normalized: Dict[str, str] = {}
    issues: List[str] = []
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            issues.append(f"{path} keys must be non-empty strings")
            continue
        if isinstance(item, str):
            normalized[key.strip()] = item
        else:
            issues.append(f"{path}.{key} must be a string")
    return normalized, issues


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
        headers, header_issues = _normalize_string_map(item.get("headers"), f"{path}.headers")
        if headers:
            request["headers"] = headers
        body, body_issues = _normalize_text_assertion(item.get("body"), f"{path}.body")
        if body:
            request["body"] = body
        if not request:
            issues.append(f"{path} must include method, url, headers, or body")
            continue
        normalized.append(request)
        issues.extend(header_issues)
        issues.extend(body_issues)
        unknown = sorted(k for k in item if k not in {"method", "url", "headers", "body"})
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
        item_valid = True
        if not isinstance(body, str):
            issues.append(f"{path}.body must be a string")
            item_valid = False
        status_code = item.get("status_code", 200)
        if isinstance(status_code, bool) or not isinstance(status_code, int):
            issues.append(f"{path}.status_code must be an integer")
            item_valid = False
        if not item_valid:
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
        scalar_type = item.get("scalar_type")
        if scalar_type is not None:
            if isinstance(scalar_type, str) and scalar_type in SUPPORTED_DB_SCALAR_TYPES:
                assertion["scalar_type"] = scalar_type
            else:
                issues.append(
                    f"{path}.scalar_type must be one of: "
                    + ", ".join(sorted(SUPPORTED_DB_SCALAR_TYPES))
                )
        if "equals" in item:
            if item["equals"] is None or isinstance(item["equals"], SUPPORTED_LITERAL_TYPES):
                assertion["equals"] = item["equals"]
                if "scalar_type" in assertion and not _is_valid_db_scalar_value(
                    item["equals"], assertion["scalar_type"]
                ):
                    issues.append(
                        f"{path}.equals must match scalar_type={assertion['scalar_type']}"
                    )
            else:
                issues.append(f"{path}.equals must be a string, number, boolean, or null")
        if "not_equals" in item:
            if item["not_equals"] is None or isinstance(item["not_equals"], SUPPORTED_LITERAL_TYPES):
                assertion["not_equals"] = item["not_equals"]
                if "scalar_type" in assertion and not _is_valid_db_scalar_value(
                    item["not_equals"], assertion["scalar_type"]
                ):
                    issues.append(
                        f"{path}.not_equals must match scalar_type={assertion['scalar_type']}"
                    )
            else:
                issues.append(f"{path}.not_equals must be a string, number, boolean, or null")
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
        if not any(key in assertion for key in {"equals", "not_equals", "not_null", "contains"}):
            issues.append(f"{path} must include equals, not_equals, not_null, or contains")
            continue
        assertions.append(assertion)
        unknown = sorted(
            k for k in item
            if k not in {"query", "scalar_type", "equals", "not_equals", "not_null", "contains"}
        )
        for key in unknown:
            issues.append(f"{path}.{key} is not supported")
    return assertions, issues


def _normalize_db_rows(value: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["db_rows must be a list"]
    normalized: List[Dict[str, Any]] = []
    issues: List[str] = []
    for index, item in enumerate(value):
        path = f"db_rows[{index}]"
        if not isinstance(item, dict):
            issues.append(f"{path} must be an object")
            continue
        query = item.get("query")
        columns = item.get("columns")
        rows = item.get("rows")
        order = item.get("order", "ordered")
        if not isinstance(query, str) or not query.strip():
            issues.append(f"{path}.query must be a non-empty string")
        if order not in {"ordered", "any"}:
            issues.append(f"{path}.order must be ordered or any")
        if not isinstance(columns, list) or not columns:
            issues.append(f"{path}.columns must be a non-empty list")
            continue
        parsed_columns = []
        for column_index, column in enumerate(columns):
            column_path = f"{path}.columns[{column_index}]"
            if not isinstance(column, dict) or not isinstance(column.get("name"), str) or not column["name"].strip():
                issues.append(f"{column_path}.name must be a non-empty string")
                continue
            scalar_type = column.get("scalar_type")
            if scalar_type not in SUPPORTED_DB_SCALAR_TYPES:
                issues.append(f"{column_path}.scalar_type must be one of: " + ", ".join(sorted(SUPPORTED_DB_SCALAR_TYPES)))
                continue
            parsed_columns.append({"name": column["name"].strip(), "scalar_type": scalar_type})
        if not isinstance(rows, list):
            issues.append(f"{path}.rows must be a list")
            continue
        parsed_rows = []
        for row_index, row in enumerate(rows):
            if not isinstance(row, list) or len(row) != len(parsed_columns):
                issues.append(f"{path}.rows[{row_index}] must match columns length")
                continue
            for value_index, cell in enumerate(row):
                if not _is_valid_db_scalar_value(cell, parsed_columns[value_index]["scalar_type"]):
                    issues.append(f"{path}.rows[{row_index}][{value_index}] must match column scalar_type")
            parsed_rows.append(row)
        if isinstance(query, str) and query.strip() and len(parsed_columns) == len(columns) and isinstance(rows, list):
            normalized.append({"query": query.strip(), "columns": parsed_columns, "rows": parsed_rows, "order": order})
    return normalized, issues


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
    stdin, stdin_issues = _normalize_stdin(value.get("stdin"))
    fixtures, fixture_issues = _normalize_fixtures(value.get("fixtures"))
    environment, environment_issues = _normalize_environment(value.get("environment"))
    if "return" in value:
        contract["return"] = value["return"]

    stdout, stdout_issues = _normalize_text_assertion(value.get("stdout"), "stdout")
    stderr, stderr_issues = _normalize_text_assertion(value.get("stderr"), "stderr")
    exception, exception_issues = _normalize_exception(value.get("exception"))
    files, file_issues = _normalize_files(value.get("files"))
    http_responses, http_response_issues = _normalize_http_responses(value.get("http_responses"))
    http_requests, http_issues = _normalize_http_requests(value.get("http_requests"))
    sqlite, sqlite_issues = _normalize_sqlite(value.get("sqlite"))
    db_assertions, db_assertion_issues = _normalize_db_assertions(value.get("db_assertions"))
    db_rows, db_row_issues = _normalize_db_rows(value.get("db_rows"))

    if method_args:
        contract["method_args"] = method_args
    if "stdin" in value and not stdin_issues:
        contract["stdin"] = stdin
    if fixtures:
        contract["fixtures"] = fixtures
    if environment:
        contract["environment"] = environment
    if http_responses:
        contract["http_responses"] = http_responses
    if sqlite:
        contract["sqlite"] = sqlite
    if db_assertions:
        contract["db_assertions"] = db_assertions
    if db_rows:
        contract["db_rows"] = db_rows
    if stdout:
        contract["stdout"] = stdout
    if stderr:
        contract["stderr"] = stderr
    if exception:
        contract["exception"] = exception
        if "return" in contract:
            issues.append("exception cannot be combined with return")
    if files:
        contract["files"] = files
    if http_requests:
        contract["http_requests"] = http_requests

    issues.extend(method_arg_issues)
    issues.extend(stdin_issues)
    issues.extend(fixture_issues)
    issues.extend(environment_issues)
    issues.extend(http_response_issues)
    issues.extend(sqlite_issues)
    issues.extend(db_assertion_issues)
    issues.extend(db_row_issues)
    issues.extend(stdout_issues)
    issues.extend(stderr_issues)
    issues.extend(exception_issues)
    issues.extend(file_issues)
    issues.extend(http_issues)

    unknown = sorted(k for k in value if k not in ASSERTION_KEYS)
    for key in unknown:
        issues.append(f"{key} is not a supported runtime_oracle assertion")
    if not contract and not issues:
        issues.append("runtime_oracle has no assertions")
    return contract, issues


def summarize_runtime_oracles(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize explicit runtime oracle coverage from StructuredSpec test cases."""
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
