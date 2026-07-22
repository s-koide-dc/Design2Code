# -*- coding: utf-8 -*-
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.generate.demo_synthesis import run_demo


class TestDemoSynthesis(unittest.TestCase):
    def test_all_demo_scenarios_satisfy_their_declared_contracts(self):
        with tempfile.TemporaryDirectory() as output_dir, contextlib.redirect_stdout(io.StringIO()) as captured:
            run_demo(output_dir=output_dir)

            output = captured.getvalue()
            generated_files = list(Path(output_dir).glob("demo_gen_*.cs"))

        self.assertNotIn(">> Status: FAILED", output)
        self.assertEqual(7, output.count(">> Status: FULLY SYNTHESIZED"), output)
        self.assertEqual(7, len(generated_files))


if __name__ == "__main__":
    unittest.main()
