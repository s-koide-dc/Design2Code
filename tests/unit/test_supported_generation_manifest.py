from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate.validate_supported_generation_manifest import (
    DEFAULT_MANIFEST,
    DEFAULT_VERIFIED_REGISTRY,
    load_supported_designs,
    validate_manifest,
)


class TestSupportedGenerationManifest(unittest.TestCase):
    def test_committed_manifest_is_valid(self):
        self.assertEqual([], validate_manifest())

    def test_quality_profile_is_the_complete_verified_scope(self):
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        expected = [entry["design_path"] for entry in manifest["designs"] if entry["status"] == "verified"]
        self.assertEqual(expected, load_supported_designs("quality"))
        self.assertEqual(4, len(load_supported_designs("smoke")))

    def test_rejects_verified_case_missing_from_manifest(self):
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        manifest["designs"] = manifest["designs"][1:]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = validate_manifest(path, DEFAULT_VERIFIED_REGISTRY)

        self.assertTrue(any("missing from manifest" in error for error in errors))

    def test_rejects_case_linked_to_a_different_design(self):
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        manifest["designs"][0]["verified_case_id"] = "app_mode_echo_minimal"
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = validate_manifest(path, DEFAULT_VERIFIED_REGISTRY)

        self.assertTrue(any("same design_path" in error for error in errors))
