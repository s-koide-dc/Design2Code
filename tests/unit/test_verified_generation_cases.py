from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate.validate_verified_generation_cases import DEFAULT_REGISTRY, validate_registry


class TestVerifiedGenerationCases(unittest.TestCase):
    def test_committed_registry_is_valid(self):
        self.assertEqual([], validate_registry(DEFAULT_REGISTRY))

    def test_rejects_changed_design_hash(self):
        payload = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        payload["cases"][0]["design_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "cases.json"
            registry.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_registry(registry)

        self.assertTrue(any("design_sha256" in error for error in errors))

    def test_rejects_stale_generation_fingerprint(self):
        payload = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        payload["cases"][0]["generation_fingerprint"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "cases.json"
            registry.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_registry(registry)

        self.assertTrue(any("generation_fingerprint" in error for error in errors))

    def test_rejects_stale_runtime_oracle_fingerprint(self):
        payload = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        payload["cases"][0]["runtime_oracle_fingerprint"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "cases.json"
            registry.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_registry(registry)

        self.assertTrue(any("runtime_oracle_fingerprint" in error for error in errors))

    def test_rejects_stale_generation_quality_fingerprint(self):
        payload = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        payload["cases"][0]["generation_quality_fingerprint"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "cases.json"
            registry.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_registry(registry)

        self.assertTrue(any("generation_quality_fingerprint" in error for error in errors))

    def test_rejects_stale_compilation_fingerprint(self):
        payload = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        payload["cases"][0]["compilation_fingerprint"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "cases.json"
            registry.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_registry(registry)

        self.assertTrue(any("compilation_fingerprint" in error for error in errors))
