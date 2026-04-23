# -*- coding: utf-8 -*-
import os
import sys
import unittest


def main() -> int:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root not in sys.path:
        sys.path.insert(0, root)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    targets = [
        "tests.unit.test_method_store",
        "tests.unit.test_code_synthesizer_integration",
        "tests.unit.test_vector_cache_required",
    ]
    for name in targets:
        suite.addTests(loader.loadTestsFromName(name))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
