import json
import unittest

from src.code_verification.execution_verifier import ExecutionVerifier


class TestExecutionVerifier(unittest.TestCase):
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
