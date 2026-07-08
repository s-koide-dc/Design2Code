import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.autonomous_learning.compliance_auditor import ComplianceAuditor


class TestComplianceAuditorStructural(unittest.TestCase):
    def _workspace(self, root: Path):
        (root / "config").mkdir()
        (root / "src" / "sample").mkdir(parents=True)
        rules = {
            "document_contract": {
                "minimum_level_2_sections": 2,
                "require_section_body": True,
            },
            "structural_rules": [{
                "type": "dependency_constraint",
                "source": "src/sample",
                "cannot_depend_on": ["src/pipeline_core"],
                "description": "sample must not depend on pipeline",
            }],
        }
        (root / "config" / "project_rules.json").write_text(
            json.dumps(rules),
            encoding="utf-8",
        )

    def test_loads_authoritative_config_rules(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._workspace(root)

            auditor = ComplianceAuditor(root)

            self.assertIn("document_contract", auditor.rules)
            self.assertEqual([], auditor.configuration_diagnostics)

    def test_document_quality_uses_heading_structure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._workspace(root)
            design = root / "src" / "sample" / "sample.design.md"
            design.write_text(
                "# Sample\n"
                "## 1. Purpose\n"
                "Concrete purpose.\n"
                "## 2. Structured Specification\n",
                encoding="utf-8",
            )
            auditor = ComplianceAuditor(root)
            auditor.findings = []

            auditor._audit_document_quality()

            finding = auditor.findings[0]
            self.assertEqual("DOCUMENT_INCOMPLETE", finding["type"])
            self.assertEqual(
                ["2. Structured Specification"],
                finding["details"]["empty_sections"],
            )

    def test_dependency_audit_uses_python_ast(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._workspace(root)
            source = root / "src" / "sample" / "module.py"
            source.write_text(
                'description = "from src.pipeline_core import Pipeline"\n'
                "from src.pipeline_core.pipeline_core import Pipeline\n",
                encoding="utf-8",
            )
            auditor = ComplianceAuditor(root)
            auditor.findings = []

            auditor._audit_dependencies()

            violations = [
                finding for finding in auditor.findings
                if finding["type"] == "DEPENDENCY_VIOLATION"
            ]
            self.assertEqual(1, len(violations))
            self.assertEqual(
                Path("src/sample/module.py"),
                Path(violations[0]["file"]),
            )

    def test_invalid_rule_json_is_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "config").mkdir()
            (root / "config" / "project_rules.json").write_text(
                "{invalid",
                encoding="utf-8",
            )

            auditor = ComplianceAuditor(root)
            findings = auditor.run_full_audit()

            self.assertEqual("AUDIT_CONFIGURATION_ERROR", findings[0]["type"])
            self.assertIn("JSONDecodeError", findings[0]["message"])

    def test_duplicate_audit_requires_declared_group(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._workspace(root)
            memory = SimpleNamespace(components=[{
                "name": "First",
                "file": "src/first.py",
                "duplicate_group_id": "duplicate.customer_lookup",
            }, {
                "name": "Second",
                "file": "src/second.py",
                "duplicate_group_id": "duplicate.customer_lookup",
            }, {
                "name": "SimilarButUndeclared",
                "file": "src/third.py",
            }])
            auditor = ComplianceAuditor(root, structural_memory=memory)
            auditor.findings = []

            auditor._audit_semantic_overlaps()

            self.assertEqual(1, len(auditor.findings))
            details = auditor.findings[0]["details"]
            self.assertEqual(
                "duplicate.customer_lookup",
                details["duplicate_group_id"],
            )
            self.assertNotIn("similarity", details)

    def test_duplicate_audit_does_not_infer_from_vectors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._workspace(root)
            memory = SimpleNamespace(
                components=[{
                    "name": "First",
                    "file": "src/first.py",
                }, {
                    "name": "Second",
                    "file": "src/second.py",
                }],
                collection=SimpleNamespace(
                    vectors=[[1.0, 0.0], [1.0, 0.0]],
                ),
            )
            auditor = ComplianceAuditor(root, structural_memory=memory)
            auditor.findings = []

            auditor._audit_semantic_overlaps()

            self.assertEqual([], auditor.findings)
