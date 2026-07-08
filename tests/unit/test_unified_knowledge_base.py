# -*- coding: utf-8 -*-
import tempfile
import unittest
from unittest.mock import MagicMock

from src.code_synthesis.unified_knowledge_base import (
    AmbiguousMethodCandidatesError,
    UnifiedKnowledgeBase,
)


class TestUnifiedKnowledgeBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config = MagicMock()
        self.config.workspace_root = self.temp_dir.name
        self.method_store = MagicMock()
        self.structural_memory = MagicMock()
        self.structural_memory.search_component.return_value = []
        self.ukb = UnifiedKnowledgeBase(
            self.config,
            self.method_store,
            self.structural_memory,
        )
        self.ukb.canonical_data = {}
        self.ukb.patterns = []

    def test_vector_score_does_not_select_single_method_when_structure_is_ambiguous(self):
        self.method_store.search.return_value = [
            {
                "id": "file_read_text",
                "name": "ReadAllText",
                "role": "FETCH",
                "intent": "FETCH",
                "source_kind": "file",
                "return_type": "string",
                "score": 0.99,
            },
            {
                "id": "file_read_lines",
                "name": "ReadAllLines",
                "role": "FETCH",
                "intent": "FETCH",
                "source_kind": "file",
                "return_type": "string",
                "score": 0.10,
            },
        ]

        with self.assertRaises(AmbiguousMethodCandidatesError) as raised:
            self.ukb.search(
                "ファイルを読む",
                intent="FETCH",
                requested_role="FETCH",
                source_kind="file",
                return_type="string",
            )

        self.assertEqual(
            ["file_read_text", "file_read_lines"],
            raised.exception.candidate_ids,
        )

    def test_single_structural_candidate_is_returned_with_score_as_metadata(self):
        self.method_store.search.return_value = [
            {
                "id": "file_exists",
                "name": "Exists",
                "role": "FETCH",
                "intent": "FETCH",
                "source_kind": "file",
                "return_type": "bool",
                "score": 0.42,
            },
            {
                "id": "file_read_text",
                "name": "ReadAllText",
                "role": "FETCH",
                "intent": "FETCH",
                "source_kind": "file",
                "return_type": "string",
                "score": 0.99,
            },
        ]

        results = self.ukb.search(
            "ファイルの存在を確認する",
            intent="FETCH",
            requested_role="FETCH",
            source_kind="file",
            return_type="bool",
        )

        self.assertEqual(["file_exists"], [item["id"] for item in results])
        self.assertEqual(0.42, results[0]["score"])

    def test_transform_target_entity_uses_declared_class_structure(self):
        self.method_store.search.return_value = [
            {
                "id": "business_process",
                "name": "ProcessInstance",
                "class": "App.Services.BusinessLogic",
                "role": "TRANSFORM",
                "intent": "TRANSFORM",
                "return_type": "void",
                "score": 0.20,
            },
            {
                "id": "generic_transform",
                "name": "ToResponse",
                "role": "TRANSFORM",
                "intent": "TRANSFORM",
                "return_type": "void",
                "score": 0.99,
            },
        ]

        results = self.ukb.search(
            "ProcessInstance",
            intent="TRANSFORM",
            requested_role="TRANSFORM",
            target_entity="BusinessLogic",
        )

        self.assertEqual(["business_process"], [item["id"] for item in results])

    def test_internal_search_receives_structural_constraints(self):
        self.method_store.search.return_value = []
        self.structural_memory.search_component.return_value = [
            {
                "id": "internal_fetch",
                "symbol_id": "src/a.py::A.fetch",
                "name": "A.fetch",
                "role": "FETCH",
                "intent": "FETCH",
                "capabilities": ["FETCH"],
                "return_type": "string",
                "similarity": 0.31,
            }
        ]

        results = self.ukb.search(
            "内部データを取得する",
            intent="FETCH",
            requested_role="FETCH",
            return_type="string",
        )

        self.assertEqual(["internal_fetch"], [item["id"] for item in results])
        self.structural_memory.search_component.assert_called_once_with(
            "内部データを取得する",
            top_k=20,
            role="FETCH",
            capabilities=None,
            return_type="string",
        )


if __name__ == "__main__":
    unittest.main()
