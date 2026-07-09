import json
import unittest

from src.code_verification.execution_verifier import ExecutionVerifier


class TestExecutionVerifier(unittest.TestCase):
    def test_source_inspection_uses_roslyn_structure(self):
        source = """
using System.Threading.Tasks;

namespace Sample.App;

public class Worker
{
    public Worker(IDependency dependency) {}

    public async Task<string> RunAsync(int count, string name)
    {
        await Task.Delay(1);
        return name + count;
    }
}

public interface IDependency {}
"""

        result = ExecutionVerifier()._inspect_source_structure(source, "RunAsync")

        self.assertEqual("success", result["status"])
        inspection = result["inspection"]
        self.assertEqual("Sample.App", inspection["namespace"])
        self.assertEqual("Worker", inspection["class_name"])
        self.assertEqual("Sample.App.Worker", inspection["qualified_name"])
        self.assertEqual(
            [{"name": "dependency", "type": "IDependency"}],
            inspection["constructor_parameters"],
        )
        self.assertEqual("Task<string>", inspection["method"]["return_type"])
        self.assertTrue(inspection["method"]["is_async"])
        self.assertEqual(
            [
                {"name": "count", "type": "int"},
                {"name": "name", "type": "string"},
            ],
            inspection["method"]["parameters"],
        )

    def test_runtime_exception_uses_structured_json_diagnostic(self):
        payload = {
            "type": "System.InvalidOperationException",
            "message": "invalid state",
            "stackTrace": "at GeneratedProcessor.Run()",
        }
        output = "__RUNTIME_JSON__" + json.dumps(payload)

        parsed = ExecutionVerifier()._parse_runtime_exception(output)

        self.assertEqual(payload["type"], parsed["type"])
        self.assertEqual(payload["message"], parsed["message"])
        self.assertEqual(payload["stackTrace"], parsed["stack_trace"])

    def test_runtime_exception_does_not_infer_from_unstructured_text(self):
        parsed = ExecutionVerifier()._parse_runtime_exception(
            "Unhandled exception. System.Exception: guessed"
        )

        self.assertEqual("UnknownException", parsed["type"])


if __name__ == "__main__":
    unittest.main()
