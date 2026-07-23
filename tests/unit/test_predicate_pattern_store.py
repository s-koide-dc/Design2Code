# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path

from src.config.config_manager import ConfigManager
from src.design_parser.predicate_pattern_store import PredicatePatternStore


class TestPredicatePatternStore(unittest.TestCase):
    def test_loads_only_traceable_verified_patterns_without_vector_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "config").mkdir()
            (root / "resources").mkdir()
            (root / "config" / "config.json").write_text("{}", encoding="utf-8")
            (root / "resources" / "predicate_patterns.json").write_text(json.dumps({
                "patterns": [
                    {"id": "valid", "utterances": ["数値条件"], "goal": {"type": "numeric", "operator": "Greater"}},
                    {"id": "invalid", "utterances": ["broken"]},
                ]
            }, ensure_ascii=False), encoding="utf-8")

            store = PredicatePatternStore(ConfigManager(workspace_root=str(root)))

        self.assertEqual(["valid"], [pattern["id"] for pattern in store.patterns])
        self.assertEqual([], store.retrieve("数値が大きい"))
