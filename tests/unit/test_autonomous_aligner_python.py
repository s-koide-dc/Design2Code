import unittest
from pathlib import Path
import os
import sys
from unittest.mock import MagicMock

# Add project root to sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.autonomous_aligner.autonomous_aligner import AutonomousAligner

class TestAutonomousAlignerPython(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/temp_align_test_py")
        self.test_dir.mkdir(exist_ok=True)
        self.aligner = AutonomousAligner(str(project_root))

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_align_module_logic_gap_python(self):
        # 1. Arrange
        design_content = """# PyMock Module Design Document
## 1. Purpose
Test logic gap alignment for Python.
## 2. Structured Specification
### Core Logic
1. Validate input.
2. Calculate score.
"""
        source_content = """
def process_data(data):
    # Step 1
    if not data:
        return
    print("Processing...")
"""
        design_path = self.test_dir / "pymock_mod.design.md"
        source_path = self.test_dir / "pymock_mod.py"

        with open(design_path, "w", encoding="utf-8") as f: f.write(design_content)
        with open(source_path, "w", encoding="utf-8") as f: f.write(source_content)

        self.aligner.auditor.audit = MagicMock(return_value={
            "status": "inconsistent",
            "consistency_score": 0.5,
            "findings": [{"type": "logic_gap"}],
        })
        suggestion = MagicMock(
            description="Implement score calculation",
            current_code="",
            suggested_code="# TODO: Implement Logic: Calculate score",
            line_number=5,
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
        self.assertIn(
            "Implement score calculation",
            str(result.get("pending_suggestions")),
        )

        with open(source_path, "r", encoding="utf-8") as f:
            updated_code = f.read()

        self.assertEqual(updated_code, source_content)

if __name__ == "__main__":
    unittest.main()
