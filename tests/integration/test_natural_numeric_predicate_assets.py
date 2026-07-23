# -*- coding: utf-8 -*-
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.design_parser.design_inference import DesignInferenceEngine


class TestNaturalNumericPredicateAssets(unittest.TestCase):
    def test_real_chive_infers_price_comparison_logic(self):
        root = Path(os.getcwd())
        if not (root / "resources" / "vectors" / "chive-1.3-mc90.txt.v0.matrix.npy").is_file():
            self.skipTest("real chiVe cache is not available")
        with tempfile.TemporaryDirectory() as temp_dir:
            design = Path(temp_dir) / "NaturalNumericPredicate.design.md"
            shutil.copy2(root / "scenarios" / "NaturalNumericPredicate.design.md", design)
            result = DesignInferenceEngine().infer_then_freeze(str(design))
            text = Path(result["output_path"]).read_text(encoding="utf-8")
        self.assertIn('"variable_hint":"Price"', text)
        self.assertIn('"operator":"Greater"', text)
        self.assertIn('"expected_value":500', text)

    def test_real_chive_infers_string_negation_and_conjunction_logic(self):
        root = Path(os.getcwd())
        if not (root / "resources" / "vectors" / "chive-1.3-mc90.txt.v0.matrix.npy").is_file():
            self.skipTest("real chiVe cache is not available")
        cases = {
            "NaturalStringPrefixPredicate": '"operator":"StartsWith"',
            "NaturalNegatedPrefixPredicate": '"negated":true',
            "NaturalConjunctivePredicate": '"value":"AND"',
            "NaturalDisjunctivePredicate": '"value":"OR"',
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            for name, expected in cases.items():
                design = Path(temp_dir) / f"{name}.design.md"
                shutil.copy2(root / "scenarios" / f"{name}.design.md", design)
                result = DesignInferenceEngine().infer_then_freeze(str(design))
                text = Path(result["output_path"]).read_text(encoding="utf-8")
                self.assertIn(expected, text, name)

    def test_real_chive_or_predicate_is_preserved_in_generated_csharp(self):
        root = Path(os.getcwd())
        if not (root / "resources" / "vectors" / "chive-1.3-mc90.txt.v0.matrix.npy").is_file():
            self.skipTest("real chiVe cache is not available")
        with tempfile.TemporaryDirectory() as temp_dir:
            work = Path(temp_dir)
            source = root / "scenarios" / "NaturalDisjunctivePredicate.design.md"
            design = work / "NaturalDisjunctivePredicate.design.md"
            shutil.copy2(source, design)
            inferred = Path(DesignInferenceEngine().infer_then_freeze(str(design))["output_path"])
            runtime_design = work / "runtime" / "NaturalDisjunctivePredicate.design.md"
            runtime_design.parent.mkdir()
            shutil.copy2(inferred, runtime_design)
            output = work / "Generated"
            completed = subprocess.run([sys.executable, "scripts/generate/generate_from_design.py", "--design", str(runtime_design), "--output", str(output), "--post-exec-verify"], cwd=root, capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            code_path = output if output.is_file() else next(output.rglob("*.cs"))
            code = code_path.read_text(encoding="utf-8")
        self.assertIn('item.Name.StartsWith("A") || item.Price > 500m', code)

    def test_real_chive_and_predicate_is_preserved_in_generated_csharp(self):
        root = Path(os.getcwd())
        if not (root / "resources" / "vectors" / "chive-1.3-mc90.txt.v0.matrix.npy").is_file():
            self.skipTest("real chiVe cache is not available")
        with tempfile.TemporaryDirectory() as temp_dir:
            work = Path(temp_dir)
            design = work / "NaturalConjunctivePredicate.design.md"
            shutil.copy2(root / "scenarios" / design.name, design)
            inferred = Path(DesignInferenceEngine().infer_then_freeze(str(design))["output_path"])
            runtime_design = work / "runtime" / design.name
            runtime_design.parent.mkdir()
            shutil.copy2(inferred, runtime_design)
            output = work / "Generated"
            completed = subprocess.run([sys.executable, "scripts/generate/generate_from_design.py", "--design", str(runtime_design), "--output", str(output), "--post-exec-verify"], cwd=root, capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            code_path = output if output.is_file() else next(output.rglob("*.cs"))
            code = code_path.read_text(encoding="utf-8")
        self.assertIn('item.Name.StartsWith("A") && item.Price > 500m', code)

    def test_real_chive_negated_prefix_is_preserved_in_generated_csharp(self):
        root = Path(os.getcwd())
        if not (root / "resources" / "vectors" / "chive-1.3-mc90.txt.v0.matrix.npy").is_file():
            self.skipTest("real chiVe cache is not available")
        with tempfile.TemporaryDirectory() as temp_dir:
            work = Path(temp_dir)
            design = work / "NaturalNegatedPrefixPredicate.design.md"
            shutil.copy2(root / "scenarios" / design.name, design)
            inferred = Path(DesignInferenceEngine().infer_then_freeze(str(design))["output_path"])
            runtime_design = work / "runtime" / design.name
            runtime_design.parent.mkdir()
            shutil.copy2(inferred, runtime_design)
            output = work / "Generated"
            completed = subprocess.run([sys.executable, "scripts/generate/generate_from_design.py", "--design", str(runtime_design), "--output", str(output), "--post-exec-verify"], cwd=root, capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            code_path = output if output.is_file() else next(output.rglob("*.cs"))
            code = code_path.read_text(encoding="utf-8")
        self.assertIn('!(item.Name != null && item.Name.StartsWith("A"))', code)
