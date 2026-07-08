import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.autonomous_learning.structural_memory import StructuralMemory


class TestStructuralMemorySearch(unittest.TestCase):
    def setUp(self):
        self.memory = StructuralMemory.__new__(StructuralMemory)
        self.memory.items = [
            {
                "symbol_id": "src/a.py::A.fetch",
                "type": "method",
                "name": "A.fetch",
                "role": "FETCH",
                "capabilities": ["FETCH", "HTTP_REQUEST"],
                "return_type": "str",
            },
            {
                "symbol_id": "src/b.py::B.save",
                "type": "method",
                "name": "B.save",
                "role": "PERSIST",
                "capabilities": ["PERSIST"],
                "return_type": "None",
            },
        ]
        self.memory.vector_engine = None

    def test_search_without_vector_requires_structural_constraints(self):
        self.assertEqual(self.memory.search_component("fetch"), [])

    def test_search_uses_exact_structural_constraints(self):
        results = self.memory.search_component(
            "ignored",
            role="FETCH",
            capabilities=["HTTP_REQUEST"],
            return_type="str",
        )

        self.assertEqual(
            [result["symbol_id"] for result in results],
            ["src/a.py::A.fetch"],
        )
        self.assertIsNone(results[0]["similarity"])

    def test_search_uses_compatible_role_constraints(self):
        self.memory.items[0]["role"] = "READ"

        results = self.memory.search_component("ignored", role="FETCH")

        self.assertEqual(
            [result["symbol_id"] for result in results],
            ["src/a.py::A.fetch"],
        )

    def test_semantic_ordering_cannot_reintroduce_filtered_items(self):
        self.memory.vector_engine = object()
        self.memory.hybrid_search = MagicMock(return_value=[
            (self.memory.items[1], 0.99),
            (self.memory.items[0], 0.25),
        ])

        results = self.memory.search_component("fetch", role="FETCH")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["symbol_id"], "src/a.py::A.fetch")
        self.assertEqual(results[0]["similarity"], 0.25)

    def test_duplicate_detection_requires_exact_fingerprint(self):
        self.memory.items[0]["structural_fingerprint"] = "sha256:abc"
        self.memory.items[1]["structural_fingerprint"] = "sha256:def"

        self.assertEqual(self.memory.find_duplicates(""), [])
        self.assertEqual(
            [
                item["symbol_id"]
                for item in self.memory.find_duplicates("sha256:abc")
            ],
            ["src/a.py::A.fetch"],
        )

    def test_get_method_code_uses_recorded_line_range(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.py"
            source.write_text(
                "before\n"
                "def target():\n"
                "    return 1\n"
                "after\n",
                encoding="utf-8",
            )
            self.memory.workspace_root = temp_dir

            code = self.memory.get_method_code({
                "name": "target",
                "file": "sample.py",
                "start_line": 2,
                "end_line": 3,
            })

        self.assertEqual(code, "def target():\n    return 1")


if __name__ == "__main__":
    unittest.main()
