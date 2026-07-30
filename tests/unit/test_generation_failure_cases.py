from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.validate.validate_generation_failure_cases import (
    DEFAULT_REGISTRY,
    classify_failure_payload,
    replay_open_failures,
    validate_registry,
)
from scripts.validate.fingerprint_scopes import generation_fingerprint
from scripts.validate.validate_verified_generation_cases import ROOT


class TestGenerationFailureCases(unittest.TestCase):
    def test_committed_registry_is_valid(self):
        self.assertEqual([], validate_registry(DEFAULT_REGISTRY))

    def test_classifies_explicit_inference_issue_without_log_matching(self):
        result = classify_failure_payload({
            "inference": {
                "status": "blocked",
                "issues": [{"reason": "MISSING_EXPLICIT_STEP_METADATA"}],
            },
        })

        self.assertEqual("design_inference", result["stage"])
        self.assertEqual("MISSING_EXPLICIT_STEP_METADATA", result["reason"])
        self.assertIn("[KIND|INTENT|TARGET|OUTPUT|EFFECT]", result["guidance"])

    def test_does_not_classify_unstructured_logs(self):
        self.assertIsNone(classify_failure_payload({"stderr": "something failed"}))

    def test_resolved_case_requires_a_verified_case_reference(self):
        design = ROOT / "tests" / "fixtures" / "designs" / "MissingStepMetadata.design.md"
        verified = {"schema_version": 1, "cases": [{"case_id": "fixed_missing_metadata"}]}
        failure = {
            "schema_version": 1,
            "cases": [{
                "case_id": "missing_metadata_fixed",
                "design_path": "tests/fixtures/designs/MissingStepMetadata.design.md",
                "design_sha256": hashlib.sha256(design.read_bytes()).hexdigest(),
                "generation_fingerprint": generation_fingerprint(),
                "stage": "design_inference",
                "reason": "MISSING_EXPLICIT_STEP_METADATA",
                "guidance": "Add explicit metadata.",
                "status": "resolved",
                "resolution": {
                    "verified_case_id": "fixed_missing_metadata",
                    "resolved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                },
            }],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            verified_path = root / "verified.json"
            failure_path = root / "failure.json"
            verified_path.write_text(json.dumps(verified), encoding="utf-8")
            failure_path.write_text(json.dumps(failure), encoding="utf-8")
            errors = validate_registry(failure_path, verified_path)

        self.assertEqual([], errors)

    def test_resolved_case_rejects_unknown_verified_reference(self):
        payload = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        payload["cases"][0]["status"] = "resolved"
        payload["cases"][0]["resolution"] = {
            "verified_case_id": "not_registered",
            "resolved_at": "2026-07-28T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            failure_path = Path(temp_dir) / "failure.json"
            failure_path.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_registry(failure_path)

        self.assertTrue(any("verified_case_id" in error for error in errors))

    def test_replay_requires_registered_structured_failure(self):
        def expected_failure(_args):
            return {
                "exit_code": 1,
                "payload": {
                    "inference": {
                        "status": "blocked",
                        "issues": [{"reason": "MISSING_EXPLICIT_STEP_METADATA"}],
                    },
                },
            }

        self.assertEqual([], replay_open_failures(DEFAULT_REGISTRY, expected_failure))

    def test_replay_rejects_failure_that_now_passes(self):
        self.assertTrue(any(
            "expected failure now passes" in error
            for error in replay_open_failures(DEFAULT_REGISTRY, lambda _args: {"exit_code": 0, "payload": {}})
        ))
