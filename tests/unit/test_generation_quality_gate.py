# -*- coding: utf-8 -*-
import unittest

from src.code_verification.generation_quality import evaluate_generation_quality


class TestGenerationQualityGate(unittest.TestCase):
    def test_quality_gate_fails_on_compiler_warning(self):
        quality = evaluate_generation_quality(
            code="public class A {}",
            verification={
                "valid": True,
                "errors": [],
                "warnings": [{"severity": "warning", "code": "CS8602"}],
            },
            blueprint={"methods": [{"body": []}]},
            spec_issues=[],
            fail_on_warnings=True,
        )

        self.assertFalse(quality["valid"])
        self.assertIn("compiler warnings present: 1 (CS8602)", quality["issues"])

    def test_quality_gate_accepts_clean_blueprint(self):
        quality = evaluate_generation_quality(
            code="""public class A
{
    public bool Run()
    {
        return true;
    }
}""",
            verification={"valid": True, "errors": [], "warnings": []},
            blueprint={"methods": [{"body": []}]},
            spec_issues=[],
            fail_on_warnings=True,
        )

        self.assertTrue(quality["valid"], quality)
        self.assertEqual(1, quality["maintainability"]["method_count"])
        self.assertEqual(1, quality["maintainability"]["class_count"])
        self.assertEqual(0, quality["maintainability"]["constructor_count"])
        self.assertEqual(1, quality["maintainability"]["operation_method_count"])
        self.assertEqual(0, quality["maintainability"]["max_operation_method_try_count"])
        self.assertEqual(0, quality["maintainability"]["max_method_catch_count"])
        self.assertEqual([], quality["maintainability"]["findings"])

    def test_quality_gate_reports_maintainability_observation_without_failing(self):
        code = """public class GeneratedProcessor
{
    public GeneratedProcessor()
    {
        try
        {
        }
        catch (Exception)
        {
        }
    }

    public bool Run()
    {
        try
        {
            return true;
        }
        catch (Exception)
        {
            return false;
        }
    }
}"""

        quality = evaluate_generation_quality(
            code=code,
            verification={"valid": True, "errors": [], "warnings": []},
            blueprint={"methods": [{"body": [{"type": "raw", "code": "return true;"}]}]},
            spec_issues=[],
            fail_on_warnings=True,
        )

        self.assertTrue(quality["valid"], quality)
        self.assertEqual(2, quality["maintainability"]["method_count"])
        self.assertEqual(1, quality["maintainability"]["constructor_count"])
        self.assertEqual(1, quality["maintainability"]["operation_method_count"])
        self.assertEqual(1, quality["maintainability"]["max_method_catch_count"])
        self.assertEqual(1, quality["maintainability"]["max_operation_method_try_count"])
        self.assertEqual(1, quality["maintainability"]["max_operation_method_catch_count"])
        self.assertGreaterEqual(quality["maintainability"]["max_method_line_count"], 10)

    def test_maintainability_threshold_findings_do_not_fail_by_default(self):
        code = """public class GeneratedProcessor
{
    public bool Run()
    {
        return true;
    }
}"""

        quality = evaluate_generation_quality(
            code=code,
            verification={"valid": True, "errors": [], "warnings": []},
            blueprint={"methods": [{"body": [{"type": "raw", "code": "return true;"}]}]},
            spec_issues=[],
            fail_on_warnings=True,
            maintainability_thresholds={"max_operation_method_line_count": 1},
        )

        self.assertTrue(quality["valid"], quality)
        self.assertEqual(1, len(quality["maintainability"]["findings"]))
        self.assertEqual(
            "max_operation_method_line_count",
            quality["maintainability"]["findings"][0]["metric"],
        )

    def test_maintainability_threshold_findings_can_fail_quality_gate(self):
        code = """public class GeneratedProcessor
{
    public bool Run()
    {
        return true;
    }
}"""

        quality = evaluate_generation_quality(
            code=code,
            verification={"valid": True, "errors": [], "warnings": []},
            blueprint={"methods": [{"body": [{"type": "raw", "code": "return true;"}]}]},
            spec_issues=[],
            fail_on_warnings=True,
            fail_on_maintainability=True,
            maintainability_thresholds={"max_operation_method_line_count": 1},
        )

        self.assertFalse(quality["valid"], quality)
        self.assertIn("maintainability findings present: 1", quality["issues"])

    def test_maintainability_reports_try_block_threshold_finding(self):
        code = """public class GeneratedProcessor
{
    public bool Run()
    {
        try
        {
            return true;
        }
        catch (Exception)
        {
            return false;
        }
    }
}"""

        quality = evaluate_generation_quality(
            code=code,
            verification={"valid": True, "errors": [], "warnings": []},
            blueprint={"methods": [{"body": [{"type": "raw", "code": "return true;"}]}]},
            spec_issues=[],
            fail_on_warnings=True,
            maintainability_thresholds={"max_operation_method_try_count": 0},
        )

        self.assertTrue(quality["valid"], quality)
        self.assertEqual(1, len(quality["maintainability"]["findings"]))
        self.assertEqual(
            "max_operation_method_try_count",
            quality["maintainability"]["findings"][0]["metric"],
        )

    def test_generated_error_log_helper_is_not_counted_as_operation_method(self):
        code = """namespace Generated
{
    public partial class GeneratedProcessor
    {
        public bool Run()
        {
            return true;
        }
    }
}

namespace Generated
{
    internal static class GeneratedErrorLog
    {
        public static void Write(string intent, string methodName, System.Exception ex)
        {
            System.Console.Error.WriteLine(intent + methodName + ex.Message);
        }
    }
}"""

        quality = evaluate_generation_quality(
            code=code,
            verification={"valid": True, "errors": [], "warnings": []},
            blueprint={"methods": [{"body": [{"type": "raw", "code": "return true;"}]}]},
            spec_issues=[],
            fail_on_warnings=True,
        )

        self.assertTrue(quality["valid"], quality)
        self.assertEqual(2, quality["maintainability"]["method_count"])
        self.assertEqual(1, quality["maintainability"]["operation_method_count"])
        self.assertEqual(1, quality["maintainability"]["helper_method_count"])
        helper = [m for m in quality["maintainability"]["methods"] if m["name"] == "Write"][0]
        self.assertEqual("helper", helper["kind"])

    def test_generated_private_helpers_and_result_struct_are_not_operation_methods(self):
        code = """namespace Generated
{
    public partial class GeneratedProcessor
    {
        public bool Run()
        {
            return ReadGeneratedTextFileOrDefault("input.txt", out var succeeded).Length > 0 && succeeded;
        }

        private static string ReadGeneratedTextFileOrDefault(string path, out bool succeeded)
        {
            succeeded = true;
            try
            {
                return System.IO.File.ReadAllText(path);
            }
            catch (System.Exception)
            {
                succeeded = false;
                return string.Empty;
            }
        }
    }

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
}"""

        quality = evaluate_generation_quality(
            code=code,
            verification={"valid": True, "errors": [], "warnings": []},
            blueprint={"methods": [{"body": [{"type": "raw", "code": "return true;"}]}]},
            spec_issues=[],
            fail_on_warnings=True,
        )

        self.assertTrue(quality["valid"], quality)
        self.assertEqual(3, quality["maintainability"]["method_count"])
        self.assertEqual(1, quality["maintainability"]["operation_method_count"])
        self.assertEqual(1, quality["maintainability"]["constructor_count"])
        self.assertEqual(1, quality["maintainability"]["helper_method_count"])
        run = [m for m in quality["maintainability"]["methods"] if m["name"] == "Run"][0]
        helper = [m for m in quality["maintainability"]["methods"] if m["name"] == "ReadGeneratedTextFileOrDefault"][0]
        constructor = [m for m in quality["maintainability"]["methods"] if m["name"] == "GeneratedOperationResult"][0]
        self.assertEqual("method", run["kind"])
        self.assertEqual("helper", helper["kind"])
        self.assertEqual("constructor", constructor["kind"])

    def test_roslyn_source_metrics_are_used_for_maintainability(self):
        quality = evaluate_generation_quality(
            code="public class GeneratedProcessor {}",
            verification={"valid": True, "errors": [], "warnings": []},
            blueprint={"methods": [{"body": [{"type": "raw", "code": "return true;"}]}]},
            spec_issues=[],
            source_metrics={
                "status": "success",
                "metrics": {
                    "class_count": 1,
                    "total_line_count": 25,
                    "members": [
                        {
                            "name": "Run",
                            "kind": "method",
                            "declaring_type": "GeneratedProcessor",
                            "declaring_type_kind": "class",
                            "accessibility": "public",
                            "start_line": 4,
                            "line_count": 6,
                            "try_count": 0,
                            "catch_count": 0,
                            "return_count": 1,
                        },
                        {
                            "name": "ReadGeneratedTextFileOrDefault",
                            "kind": "method",
                            "declaring_type": "GeneratedProcessor",
                            "declaring_type_kind": "class",
                            "accessibility": "private",
                            "start_line": 12,
                            "line_count": 10,
                            "try_count": 1,
                            "catch_count": 1,
                            "return_count": 2,
                        },
                    ],
                },
            },
            fail_on_warnings=True,
        )

        self.assertTrue(quality["valid"], quality)
        self.assertEqual("roslyn", quality["maintainability"]["analysis_source"])
        self.assertEqual(25, quality["maintainability"]["total_line_count"])
        self.assertEqual(1, quality["maintainability"]["operation_method_count"])
        self.assertEqual(1, quality["maintainability"]["helper_method_count"])
        self.assertEqual(0, quality["maintainability"]["max_operation_method_try_count"])


if __name__ == "__main__":
    unittest.main()
