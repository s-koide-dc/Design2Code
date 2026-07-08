import unittest
from pathlib import Path
import os
import sys
from unittest.mock import MagicMock

# Add project root to sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.autonomous_aligner.autonomous_aligner import AutonomousAligner

class TestAutonomousAligner(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/temp_align_test")
        self.test_dir.mkdir(exist_ok=True)
        self.aligner = AutonomousAligner(str(project_root))

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_align_module_logic_gap(self):
        # 1. Arrange: テスト用の設計書とソースファイルを作成
        design_content = """# Mock Module Design Document
## 1. Purpose
Test logic gap alignment.
## 2. Structured Specification
### Core Logic
1. Initialize system.
2. Perform complex calculation.
3. Save results.
"""
        source_content = """
public class MockModule {
    public void MockFunction() {
        Console.WriteLine("Initializing...");
        // missing step 2
        Console.WriteLine("Saving results...");
    }
}
"""
        design_path = self.test_dir / "mock_mod.design.md"
        source_path = self.test_dir / "mock_mod.cs"
        
        with open(design_path, "w", encoding="utf-8") as f: f.write(design_content)
        with open(source_path, "w", encoding="utf-8") as f: f.write(source_content)

        self.aligner.auditor.audit = MagicMock(return_value={
            "status": "inconsistent",
            "consistency_score": 0.5,
            "findings": [{"type": "logic_gap"}],
        })
        suggestion = MagicMock(
            description="Implement calculation",
            current_code="",
            suggested_code="// TODO: Implement Logic: Perform complex calculation",
            line_number=4,
        )
        self.aligner.fix_engine.generate_fix_suggestions = MagicMock(
            return_value=[suggestion]
        )

        # 2. Act
        result = self.aligner.align_module(design_path)

        # 3. Assert
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "inconsistent")
        self.assertEqual(result["fixes_applied"], [])
        self.assertEqual(result["initial_score"], 0.5)
        self.assertEqual(result["final_score"], 0.5)
        self.assertIn(
            "Implement calculation",
            str(result.get("pending_suggestions")),
        )
        
        # ファイルが更新されているか確認
        with open(source_path, "r", encoding="utf-8") as f:
            updated_code = f.read()
        
        self.assertEqual(updated_code, source_content)

    def test_fix_build_errors_does_not_mutate_without_validator(self):
        source_path = self.test_dir / "broken.cs"
        original = "public class Broken {"
        source_path.write_text(original, encoding="utf-8")
        self.aligner.fix_engine.generate_fix_suggestions = MagicMock()

        changed = self.aligner.fix_build_errors(
            source_path,
            {
                "valid": False,
                "errors": [{
                    "code": "CS1513",
                    "message": "} expected",
                    "line": 1,
                }],
            },
        )

        self.assertFalse(changed)
        self.assertEqual(source_path.read_text(encoding="utf-8"), original)
        (
            self.aligner.fix_engine.generate_fix_suggestions
            .assert_not_called()
        )

    def test_fix_build_errors_applies_validated_structural_patch(self):
        source_path = self.test_dir / "broken.cs"
        source_path.write_text("public class Broken {\n", encoding="utf-8")
        self.aligner.structural_patch_builder = MagicMock(return_value={
            "edits": [{
                "start_line": 1,
                "end_line": 1,
                "replacement": "public class Broken { }\n",
            }],
        })
        self.aligner.post_change_validator = MagicMock(
            return_value={"valid": True, "errors": []}
        )

        changed = self.aligner.fix_build_errors(
            source_path,
            {"valid": False, "errors": [{"code": "CS1513"}]},
        )

        self.assertTrue(changed)
        self.assertEqual(
            "public class Broken { }\n",
            source_path.read_text(encoding="utf-8"),
        )
        self.assertEqual(1, len(self.aligner.alignment_history))

    def test_fix_build_errors_rejects_unvalidated_candidate(self):
        source_path = self.test_dir / "broken.cs"
        original = "public class Broken {\n"
        source_path.write_text(original, encoding="utf-8")
        self.aligner.structural_patch_builder = MagicMock(return_value={
            "edits": [{
                "start_line": 1,
                "end_line": 1,
                "replacement": "public class StillBroken {\n",
            }],
        })
        self.aligner.post_change_validator = MagicMock(
            return_value={"valid": False, "errors": [{"code": "CS1513"}]}
        )

        changed = self.aligner.fix_build_errors(
            source_path,
            {"valid": False, "errors": [{"code": "CS1513"}]},
        )

        self.assertFalse(changed)
        self.assertEqual(original, source_path.read_text(encoding="utf-8"))

    def test_indeterminate_audit_does_not_generate_fix_suggestions(self):
        design_path = self.test_dir / "unknown.design.md"
        source_path = self.test_dir / "unknown.py"
        design_path.write_text("# Unknown\n", encoding="utf-8")
        source_path.write_text("def run(): pass\n", encoding="utf-8")
        self.aligner.auditor.audit = MagicMock(return_value={
            "status": "indeterminate",
            "consistency_score": None,
            "findings": [{"type": "insufficient_structural_data"}],
        })
        self.aligner.fix_engine.generate_fix_suggestions = MagicMock()

        result = self.aligner.align_module(design_path)

        self.assertEqual(result["status"], "indeterminate")
        self.assertEqual(result["pending_suggestions"], [])
        (
            self.aligner.fix_engine.generate_fix_suggestions
            .assert_not_called()
        )

if __name__ == "__main__":
    unittest.main()
