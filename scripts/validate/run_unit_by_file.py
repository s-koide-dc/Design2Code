# -*- coding: utf-8 -*-
"""Run unit tests file by file while reporting failing modules explicitly.

The default unittest discovery command returns a single process exit code. On
GitHub Actions the raw log is not always available from unauthenticated
inspection, so CI needs the failing module names in the terminal output. This
runner keeps unittest's normal loading semantics, treats files with zero tests
as non-failures just like broad discovery effectively does, and fails only when
loaded tests fail or error.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.cli_output import emit_error, emit_progress


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run tests/unit test files individually.")
    parser.add_argument(
        "--start-directory",
        default=str(ROOT / "tests" / "unit"),
        help="Directory containing unit test files.",
    )
    parser.add_argument(
        "--pattern",
        default="test_*.py",
        help="Unit test filename glob pattern.",
    )
    parser.add_argument(
        "--verbosity",
        type=int,
        default=2,
        help="unittest verbosity level.",
    )
    return parser.parse_args()


def module_name_for(test_file: Path) -> str:
    relative = test_file.with_suffix("").relative_to(ROOT)
    return ".".join(relative.parts)


def run_module(module_name: str, verbosity: int) -> tuple[bool, int, str]:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(module_name)
    test_count = suite.countTestCases()
    if test_count == 0:
        return True, test_count, f"{module_name}: no tests loaded; skipped"

    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=verbosity)
    result = runner.run(suite)
    return result.wasSuccessful(), test_count, stream.getvalue().strip()


def emit_github_failure_summary(failed_modules: list[str]) -> None:
    message = "Unit failures: " + ", ".join(failed_modules)
    print(f"::error title=Unit failures::{message}")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    with open(summary_path, "a", encoding="utf-8") as summary:
        summary.write("## Unit failures\n\n")
        for module_name in failed_modules:
            summary.write(f"- `{module_name}`\n")


def main() -> int:
    args = parse_args()
    start_directory = Path(args.start_directory)
    failed_modules: list[str] = []

    for test_file in sorted(start_directory.glob(args.pattern)):
        module_name = module_name_for(test_file)
        ok, test_count, output = run_module(module_name, args.verbosity)
        header = f"=== {module_name} ({test_count} tests) ==="
        if ok:
            emit_progress(header)
            if output:
                emit_progress(output)
        else:
            failed_modules.append(module_name)
            emit_error(header)
            if output:
                emit_error(output)

    if failed_modules:
        emit_github_failure_summary(failed_modules)
        emit_error("Unit failures: " + ", ".join(failed_modules))
        return 1

    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    sys.exit(main())
