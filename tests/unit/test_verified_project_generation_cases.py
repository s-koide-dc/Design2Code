from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.code_generation.project_generator import ProjectGenerator
from src.design_parser import ProjectSpecParser
from scripts.validate.validate_generated_sqlserver import REQUIRED_GENERATED_TEST_FILES
from scripts.validate.validate_verified_project_generation_cases import DEFAULT_REGISTRY, validate_registry


class TestVerifiedProjectGenerationCases(unittest.TestCase):
    def test_project_replay_requires_every_generated_test_family(self):
        self.assertEqual(
            (
                "ProjectWiringTests.cs",
                "ProjectEndpointTests.cs",
                "ProjectSqliteEndpointTests.cs",
                "ProjectSqlServerEndpointTests.cs",
            ),
            REQUIRED_GENERATED_TEST_FILES,
        )

    def test_committed_registry_is_valid(self):
        self.assertEqual([], validate_registry())

    def test_rejects_changed_project_design_hash(self):
        payload = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        payload["cases"][0]["design_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "cases.json"
            registry.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_registry(registry)
        self.assertTrue(any("design_sha256" in error for error in errors))

    def test_rejects_stale_project_generation_fingerprint(self):
        payload = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        payload["cases"][0]["project_generation_fingerprint"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "cases.json"
            registry.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_registry(registry)

        self.assertTrue(any("project_generation_fingerprint" in error for error in errors))

    def test_rejects_incomplete_project_evidence(self):
        payload = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        del payload["cases"][0]["evidence"]["generated_sqlite_tests"]
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "cases.json"
            registry.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_registry(registry)
        self.assertTrue(any("evidence" in error for error in errors))

    def test_minimal_crud_inherits_declared_routes_for_generated_endpoint_tests(self):
        spec = ProjectSpecParser().parse_file("scenarios/MinimalCrudProject.design.md")
        with tempfile.TemporaryDirectory() as temp_dir:
            ProjectGenerator().generate(spec, temp_dir)
            test_root = Path(temp_dir) / "Tests"
            endpoint_tests = (test_root / "ProjectEndpointTests.cs").read_text(encoding="utf-8")
            create_dto = (Path(temp_dir) / "DTO" / "TaskItemCreateRequest.cs").read_text(encoding="utf-8")

        self.assertIn('client.GetAsync("/tasks")', endpoint_tests)
        self.assertIn('client.PostAsync("/tasks", content)', endpoint_tests)
        self.assertIn("CreatedAt = DateTime.UtcNow", create_dto)
