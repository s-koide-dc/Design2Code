# -*- coding: utf-8 -*-
import unittest

from src.code_verification.runtime_oracle import (
    build_runtime_oracle_test_code,
    normalize_runtime_oracle_contract,
    summarize_runtime_oracles,
)
from src.design_parser.structured_parser import StructuredDesignParser


class TestRuntimeOracle(unittest.TestCase):
    def test_summarizes_explicit_runtime_oracle_from_expected_json(self):
        spec = {
            "test_cases": [
                {
                    "id": "tc_1",
                    "scenario": "filters output",
                    "expected": (
                        '{"runtime_oracle":{'
                        '"method_args":["sales.csv","totals.csv"],'
                        '"fixtures":[{"path":"sales.csv","content":"A,10\\nA,20"}],'
                        '"http_responses":[{"status_code":200,"body":"[]"}],'
                        '"return":true,'
                        '"environment":{"APP_MODE":"runtime-test"},'
                        '"stdout":{"contains":["Alice"],"not_contains":["Bob"]},'
                        '"files":[{"path":"totals.csv","contains":["A,30"]}],'
                        '"http_requests":[{"method":"GET","url":"https://example.test/items",'
                        '"headers":{"X-API-Key":"secret"},'
                        '"body":{"contains":["payload"],"not_contains":["ignored"]}}]'
                        "}}"
                    ),
                }
            ]
        }

        summary = summarize_runtime_oracles(spec)

        self.assertTrue(summary["valid"], summary)
        self.assertEqual(1, summary["ready_count"])
        self.assertEqual(0, summary["invalid_count"])
        self.assertEqual(0, summary["unverified_count"])
        contract = summary["cases"][0]["contract"]
        self.assertEqual(["sales.csv", "totals.csv"], contract["method_args"])
        self.assertEqual("sales.csv", contract["fixtures"][0]["path"])
        self.assertTrue(contract["return"])
        self.assertEqual(["Alice"], contract["stdout"]["contains"])
        self.assertEqual(["Bob"], contract["stdout"]["not_contains"])
        self.assertEqual("totals.csv", contract["files"][0]["path"])
        self.assertEqual("runtime-test", contract["environment"]["APP_MODE"])
        self.assertEqual("GET", contract["http_requests"][0]["method"])
        self.assertEqual("secret", contract["http_requests"][0]["headers"]["X-API-Key"])
        self.assertEqual(["payload"], contract["http_requests"][0]["body"]["contains"])
        self.assertEqual(200, contract["http_responses"][0]["status_code"])

    def test_natural_language_expected_is_visible_as_unverified(self):
        spec = {
            "test_cases": [
                {
                    "id": "tc_1",
                    "scenario": "happy path",
                    "expected": "true",
                }
            ]
        }

        summary = summarize_runtime_oracles(spec)

        self.assertTrue(summary["valid"], summary)
        self.assertEqual(0, summary["ready_count"])
        self.assertEqual(1, summary["unverified_count"])
        self.assertEqual(
            "expected is not an explicit JSON runtime_oracle contract",
            summary["cases"][0]["reason"],
        )

    def test_invalid_expected_json_is_reported(self):
        spec = {
            "test_cases": [
                {
                    "id": "tc_1",
                    "scenario": "bad JSON",
                    "expected": '{"runtime_oracle":',
                }
            ]
        }

        summary = summarize_runtime_oracles(spec)

        self.assertFalse(summary["valid"], summary)
        self.assertEqual(1, summary["invalid_count"])
        self.assertTrue(summary["issues"])

    def test_invalid_sqlite_contract_is_reported(self):
        spec = {
            "test_cases": [{
                "id": "tc_1",
                "scenario": "invalid sqlite",
                "expected": '{"runtime_oracle":{"sqlite":{"schema":"CREATE TABLE X(Id INT)"}}}',
            }]
        }

        summary = summarize_runtime_oracles(spec)

        self.assertFalse(summary["valid"], summary)
        self.assertEqual(1, summary["invalid_count"])
        self.assertIn("tc_1: sqlite.schema must be a list", summary["issues"])

    def test_invalid_db_assertion_contract_is_reported(self):
        spec = {
            "test_cases": [{
                "id": "tc_1",
                "scenario": "invalid db assertion",
                "expected": '{"runtime_oracle":{"db_assertions":[{"not_null":true}]}}',
            }]
        }

        summary = summarize_runtime_oracles(spec)

        self.assertFalse(summary["valid"], summary)
        self.assertEqual(1, summary["invalid_count"])
        self.assertIn("tc_1: db_assertions[0].query must be a non-empty string", summary["issues"])

    def test_typed_db_assertion_rejects_mismatched_expected_value(self):
        contract, issues = normalize_runtime_oracle_contract({
            "db_assertions": [{
                "query": "SELECT COUNT(*) FROM Products",
                "scalar_type": "long",
                "equals": "1",
            }],
        })

        self.assertEqual("long", contract["db_assertions"][0]["scalar_type"])
        self.assertIn("db_assertions[0].equals must match scalar_type=long", issues)

    def test_invalid_http_response_contract_is_reported(self):
        spec = {
            "test_cases": [{
                "id": "tc_1",
                "scenario": "invalid http response",
                "expected": '{"runtime_oracle":{"http_responses":[{"status_code":"200","body":[]}]}}',
            }]
        }

        summary = summarize_runtime_oracles(spec)

        self.assertFalse(summary["valid"], summary)
        self.assertEqual(1, summary["invalid_count"])
        self.assertIn("tc_1: http_responses[0].body must be a string", summary["issues"])
        self.assertIn("tc_1: http_responses[0].status_code must be an integer", summary["issues"])

    def test_rejects_unsupported_contract_keys(self):
        contract, issues = normalize_runtime_oracle_contract(
            {
                "return": True,
                "stdout": {"contains": ["ok"], "count": 1},
                "database": {"rows": 1},
            }
        )

        self.assertEqual({"return": True, "stdout": {"contains": ["ok"]}}, contract)
        self.assertIn("stdout.count is not a supported assertion", issues)
        self.assertIn("database is not a supported runtime_oracle assertion", issues)

    def test_normalizes_expected_exception_contract(self):
        contract, issues = normalize_runtime_oracle_contract({
            "exception": {
                "type": "InvalidOperationException",
                "message": {"contains": ["upstream"], "not_contains": ["secret"]},
            },
        })

        self.assertEqual([], issues)
        self.assertEqual("InvalidOperationException", contract["exception"]["type"])
        self.assertEqual(["upstream"], contract["exception"]["message"]["contains"])

    def test_rejects_invalid_expected_exception_contract(self):
        _, issues = normalize_runtime_oracle_contract({"exception": {"type": ""}})

        self.assertIn("exception.type must be a non-empty string", issues)

    def test_rejects_ambiguous_return_and_expected_exception(self):
        _, issues = normalize_runtime_oracle_contract({
            "return": True,
            "exception": {"type": "InvalidOperationException"},
        })

        self.assertIn("exception cannot be combined with return", issues)

    def test_build_runtime_oracle_test_code_renders_explicit_contract(self):
        test_code = build_runtime_oracle_test_code(
            "CsvSalesAggregation",
            {
                "method_args": ["sales.csv", "totals.csv"],
                "fixtures": [{"path": "sales.csv", "content": "A,10\nA,20"}],
                "return": "totals.csv",
                "files": [{"path": "totals.csv", "contains": ["A,30"]}],
            },
        )

        self.assertIn('File.WriteAllText("sales.csv", "A,10\\nA,20")', test_code)
        self.assertIn('new GeneratedProcessor().CsvSalesAggregation("sales.csv", "totals.csv")', test_code)
        self.assertIn('Assert.Equal("totals.csv", result)', test_code)
        self.assertIn('Assert.Contains("A,30"', test_code)

    def test_build_runtime_oracle_test_code_renders_http_contract(self):
        test_code = build_runtime_oracle_test_code(
            "ProductApiFilteredCatalog",
            {
                "await": True,
                "http_responses": [{
                    "status_code": 200,
                    "body": '[{"Name":"Alpha","Stock":3}]',
                }],
                "return": True,
                "stdout": {"contains": ["Alpha"]},
                "http_requests": [{
                    "method": "GET",
                    "url": "https://api.example.com/products",
                    "headers": {"X-API-Key": "secret"},
                }],
            },
        )

        self.assertIn("public async Task ExplicitRuntimeOraclePasses()", test_code)
        self.assertIn("public sealed class RuntimeOracleHttpHandler : HttpMessageHandler", test_code)
        self.assertIn("using var httpClient = new HttpClient(handler);", test_code)
        self.assertIn("await new GeneratedProcessor(httpClient).ProductApiFilteredCatalog()", test_code)
        self.assertIn('Assert.Equal("GET", handler.Requests[0].Method.Method)', test_code)
        self.assertIn('Assert.Equal("https://api.example.com/products", handler.Requests[0].RequestUri?.ToString())', test_code)
        self.assertIn('Headers.TryGetValues("X-API-Key", out var headerValues0_0)', test_code)
        self.assertIn('Assert.Contains("secret", headerValues0_0)', test_code)

    def test_build_runtime_oracle_test_code_renders_expected_exception(self):
        test_code = build_runtime_oracle_test_code(
            "FailingOperation",
            {
                "exception": {
                    "type": "InvalidOperationException",
                    "message": {"contains": ["upstream"]},
                },
                "sqlite": {"schema": ["CREATE TABLE Events (Id INTEGER PRIMARY KEY)"]},
                "db_assertions": [{"query": "SELECT COUNT(*) FROM Events", "scalar_type": "long", "equals": 0}],
            },
        )

        self.assertIn("Exception? capturedException = null", test_code)
        self.assertIn('Assert.Equal("InvalidOperationException", capturedException!.GetType().Name)', test_code)
        self.assertIn('Assert.Contains("upstream", exceptionMessage)', test_code)
        self.assertIn("QuerySingleOrDefaultAsync<long>", test_code)

    def test_build_runtime_oracle_test_code_renders_environment_contract(self):
        test_code = build_runtime_oracle_test_code(
            "AppModeEchoMinimal",
            {
                "environment": {"APP_MODE": "runtime-test"},
                "return": True,
                "stdout": {"contains": ["runtime-test"]},
            },
        )

        self.assertIn('previousEnvironment["APP_MODE"] = Environment.GetEnvironmentVariable("APP_MODE")', test_code)
        self.assertIn('Environment.SetEnvironmentVariable("APP_MODE", "runtime-test")', test_code)
        self.assertIn("new GeneratedProcessor().AppModeEchoMinimal()", test_code)
        self.assertIn('Assert.Contains("runtime-test", stdout)', test_code)
        self.assertIn('Environment.SetEnvironmentVariable("APP_MODE", previousEnvironment["APP_MODE"])', test_code)

    def test_build_runtime_oracle_test_code_renders_stdin_contract(self):
        test_code = build_runtime_oracle_test_code(
            "StdinToStdoutTransform",
            {
                "stdin": " hello \\n",
                "stdout": {"contains": ["HELLO"]},
            },
        )

        self.assertIn('var originalIn = Console.In;', test_code)
        self.assertIn('Console.SetIn(new StringReader(" hello \\\\n"));', test_code)
        self.assertIn('Console.SetIn(originalIn);', test_code)

    def test_build_runtime_oracle_test_code_renders_sqlite_contract(self):
        test_code = build_runtime_oracle_test_code(
            "StateUpdatePersist",
            {
                "await": True,
                "method_args": [1],
                "sqlite": {
                    "schema": ["CREATE TABLE Users (Id INTEGER PRIMARY KEY, LastLoginAt TEXT)"],
                    "seed": ["INSERT INTO Users (Id, LastLoginAt) VALUES (1, NULL)"],
                },
                "return": True,
                "db_assertions": [{
                    "query": "SELECT LastLoginAt FROM Users WHERE Id = 1",
                    "not_null": True,
                    "not_equals": "2020-01-01T00:00:00",
                }],
            },
        )

        self.assertIn("using Dapper;", test_code)
        self.assertIn("using Microsoft.Data.Sqlite;", test_code)
        self.assertIn('await using var connection = new SqliteConnection("Data Source=:memory:")', test_code)
        self.assertIn("await connection.ExecuteAsync", test_code)
        self.assertIn("await new GeneratedProcessor(connection).StateUpdatePersist(1)", test_code)
        self.assertIn("await connection.QuerySingleOrDefaultAsync<object>", test_code)
        self.assertIn("Assert.NotNull(dbValue0)", test_code)
        self.assertIn('Assert.NotEqual("2020-01-01T00:00:00", dbValue0?.ToString())', test_code)

    def test_build_runtime_oracle_test_code_renders_typed_db_scalar_assertions(self):
        test_code = build_runtime_oracle_test_code(
            "LongProductSynchronization",
            {
                "await": True,
                "sqlite": {"schema": ["CREATE TABLE Products (Name TEXT)"]},
                "db_assertions": [
                    {
                        "query": "SELECT COUNT(*) FROM Products",
                        "scalar_type": "long",
                        "equals": 1,
                    },
                    {
                        "query": "SELECT Name FROM Products",
                        "scalar_type": "string",
                        "equals": "Alpha",
                    },
                ],
            },
        )

        self.assertIn("QuerySingleOrDefaultAsync<long>", test_code)
        self.assertIn("Assert.Equal(1L, dbValue0)", test_code)
        self.assertIn("QuerySingleOrDefaultAsync<string>", test_code)
        self.assertIn('Assert.Equal("Alpha", dbValue1)', test_code)

    def test_build_runtime_oracle_test_code_renders_typed_db_rows(self):
        test_code = build_runtime_oracle_test_code("Rows", {"sqlite": {"schema": ["CREATE TABLE Products (Name TEXT, Price INTEGER)"]}, "db_rows": [{"query": "SELECT Name, Price FROM Products ORDER BY Price", "columns": [{"name": "Name", "scalar_type": "string"}, {"name": "Price", "scalar_type": "int"}], "rows": [["Alpha", 120]]}]})
        self.assertIn("QueryAsync", test_code)
        self.assertIn("Assert.Equal(1, dbRows0.Count)", test_code)
        self.assertIn('Convert.ToInt32(dbRow0_0["Price"]', test_code)

    def test_build_runtime_oracle_test_code_renders_null_db_row_cell(self):
        test_code = build_runtime_oracle_test_code("Rows", {"sqlite": {"schema": ["CREATE TABLE Products (Name TEXT)"]}, "db_rows": [{"query": "SELECT Name FROM Products", "columns": [{"name": "Name", "scalar_type": "string"}], "rows": [[None]]}]})
        self.assertIn('Assert.Null(dbRow0_0["Name"])', test_code)

    def test_build_runtime_oracle_test_code_matches_unordered_db_rows_once(self):
        contract, issues = normalize_runtime_oracle_contract({"db_rows": [{"query": "SELECT Name FROM Products", "order": "any", "columns": [{"name": "Name", "scalar_type": "string"}], "rows": [["Alpha"], ["Alpha"]]}]})
        self.assertEqual([], issues)
        test_code = build_runtime_oracle_test_code("Rows", contract)
        self.assertIn("var dbMatched0 = new bool[dbRows0.Count]", test_code)
        self.assertIn("if (dbMatched0[dbActual0_0Index]) continue", test_code)
        self.assertIn("dbMatched0[dbActual0_0Index] = true", test_code)

    def test_structured_parser_preserves_explicit_oracle_json(self):
        markdown = """
# OracleModule
## 1. Purpose
Validate explicit runtime oracle.
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
1. [ACTION|DISPLAY|string|void|NONE] 値を表示する
### Test Cases
- **Scenario**: explicit oracle
- **Expected**: {"runtime_oracle":{"return":true,"stdout":{"contains":["done"]}}}
"""

        spec = StructuredDesignParser().parse_markdown(markdown)
        summary = summarize_runtime_oracles(spec)

        self.assertEqual(1, summary["ready_count"])
        self.assertTrue(summary["cases"][0]["contract"]["return"])


if __name__ == "__main__":
    unittest.main()
