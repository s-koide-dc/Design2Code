# -*- coding: utf-8 -*-
import json
import os
import shutil
import tempfile
import unittest

import numpy as np

from src.advanced_tdd.knowledge_base import RepairKnowledgeBase


class DummyVectorEngine:
    is_ready = True

    def get_sentence_vector(self, words):
        if not words:
            return None
        vec = np.zeros(300, dtype=np.float32)
        for token in words:
            text = str(token)
            for ch in text:
                vec[ord(ch) % 300] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec


class MockConfig:
    def __init__(self, workspace_root):
        self.workspace_root = workspace_root
        self.storage_dir = os.path.join(workspace_root, "resources", "vectors", "vector_db")
        self.repair_knowledge_path = os.path.join(workspace_root, "resources", "repair_knowledge.json")


class TestRepairKnowledgeBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.temp_dir, "resources"), exist_ok=True)
        self.config = MockConfig(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_repair_experience_persists_pattern_and_vectors(self):
        kb = RepairKnowledgeBase(config_manager=self.config, vector_engine=DummyVectorEngine())

        kb.add_repair_experience(
            {
                "root_cause": "logic_error",
                "error_type": "Expected 1 but got 0",
                "fix_type": "fix_logic",
                "success": True,
            }
        )

        self.assertEqual(len(kb.items), 1)
        self.assertEqual(kb.items[0]["error_signature"], "Expected 1 but got 0")
        self.assertEqual(kb.items[0]["error_message_regex"], "Expected 1 but got 0")
        self.assertTrue(kb.items[0]["id"].startswith("repair."))
        self.assertEqual(kb.fix_stats["logic_error"]["success"], 1)

        with open(self.config.repair_knowledge_path, "r", encoding="utf-8") as f:
            persisted = json.load(f)
        self.assertEqual(persisted["count"], 1)
        self.assertEqual(persisted["patterns"][0]["error_signature"], "Expected 1 but got 0")
        self.assertEqual(persisted["patterns"][0]["fix_direction"], "fix_logic")

        self.assertTrue(os.path.exists(os.path.join(self.config.storage_dir, "repair_knowledge_meta.json")))
        self.assertTrue(os.path.exists(os.path.join(self.config.storage_dir, "repair_knowledge_vectors.npy")))

    def test_load_restores_repair_experience_wrapper(self):
        kb = RepairKnowledgeBase(config_manager=self.config, vector_engine=DummyVectorEngine())
        kb.add_repair_experience(
            {
                "root_cause": "null_reference",
                "error_type": "NullReferenceException at Service.Run",
                "fix_type": "add_null_validation",
                "success": True,
            }
        )

        reloaded = RepairKnowledgeBase(config_manager=self.config, vector_engine=DummyVectorEngine())

        self.assertEqual(len(reloaded.items), 1)
        self.assertEqual(reloaded.items[0]["fix_direction"], "add_null_validation")
        self.assertEqual(reloaded.fix_stats["null_reference"]["fixes"]["add_null_validation"], 1)

    def test_legacy_error_message_regex_is_normalised_to_signature(self):
        os.makedirs(self.config.storage_dir, exist_ok=True)
        with open(self.config.repair_knowledge_path, "w", encoding="utf-8") as metadata:
            json.dump(
                {
                    "patterns": [{
                        "id": "legacy",
                        "root_cause": "logic_error",
                        "error_message_regex": "Expected legacy",
                        "fix_direction": "fix_logic",
                    }],
                    "fix_stats": {},
                    "type_mappings": {},
                    "negative_feedbacks": [],
                    "unresolved_symbols": [],
                },
                metadata,
            )

        kb = RepairKnowledgeBase(config_manager=self.config, vector_engine=DummyVectorEngine())

        self.assertEqual("Expected legacy", kb.items[0]["error_signature"])

    def test_best_fix_direction_uses_explicit_root_cause_stats_only(self):
        kb = RepairKnowledgeBase(config_manager=self.config, vector_engine=DummyVectorEngine())
        kb.fix_stats = {
            "logic_error": {
                "total": 3,
                "success": 3,
                "fixes": {
                    "self_healing_test": 1,
                    "implement_method_logic": 2,
                },
            },
            "null_reference": {
                "total": 1,
                "success": 1,
                "fixes": {
                    "add_null_validation": 1,
                },
            },
        }

        result = kb.get_best_fix_direction(
            "logic_error",
            "NullReferenceException text should not affect selection",
        )

        self.assertEqual("implement_method_logic", result)

    def test_best_fix_direction_does_not_use_vector_similarity(self):
        kb = RepairKnowledgeBase(config_manager=self.config, vector_engine=DummyVectorEngine())
        kb.add_repair_experience(
            {
                "root_cause": "null_reference",
                "error_type": "NullReferenceException at Service.Run",
                "fix_type": "add_null_validation",
                "success": True,
            }
        )

        result = kb.get_best_fix_direction(
            "logic_error",
            "NullReferenceException at Service.Run",
        )

        self.assertIsNone(result)

    def test_invalid_json_log_entry_is_reported_and_skipped(self):
        log_dir = os.path.join(self.temp_dir, "logs")
        os.makedirs(log_dir)
        with open(os.path.join(log_dir, "pipeline_invalid.json"), "w", encoding="utf-8") as log:
            log.write("{invalid json}\n")

        kb = RepairKnowledgeBase(config_manager=self.config, vector_engine=DummyVectorEngine())
        with self.assertLogs(kb.logger, level="WARNING") as captured:
            kb.learn_from_session_logs(log_dir)

        self.assertIn("pipeline_invalid.json:1", "\n".join(captured.output))

    def test_invalid_metadata_is_recorded_as_load_diagnostic(self):
        with open(
            self.config.repair_knowledge_path,
            "w",
            encoding="utf-8",
        ) as metadata:
            metadata.write("{invalid")

        kb = RepairKnowledgeBase(
            config_manager=self.config,
            vector_engine=DummyVectorEngine(),
        )

        self.assertEqual(
            "REPAIR_KNOWLEDGE_LOAD_ERROR",
            kb.load_diagnostics[0]["type"],
        )
        self.assertEqual(
            "JSONDecodeError",
            kb.load_diagnostics[0]["error_type"],
        )


if __name__ == "__main__":
    unittest.main()
