import tempfile
import unittest
from pathlib import Path

from scripts.validate.fingerprint_scopes import _source_files


class TestFingerprintScopes(unittest.TestCase):
    def test_source_files_excludes_compiler_output_directories(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "Program.cs").write_text("class Program {}", encoding="utf-8")
            (root / "obj").mkdir()
            (root / "obj" / "Generated.cs").write_text("class Generated {}", encoding="utf-8")
            (root / "bin").mkdir()
            (root / "bin" / "Copied.cs").write_text("class Copied {}", encoding="utf-8")

            files = _source_files(root, "*.cs")

        self.assertEqual([root / "Program.cs"], files)
