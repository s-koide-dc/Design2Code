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
import time
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
    parser.add_argument(
        "--failure-report",
        help="Optional path to write failing module names, one per line.",
    )
    return parser.parse_args()


def module_name_for(test_file: Path) -> str:
    relative = test_file.with_suffix("").relative_to(ROOT)
    return ".".join(relative.parts)


def run_module(module_name: str, verbosity: int) -> tuple[bool, int, int, str, list[str]]:
    started = time.perf_counter()
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(module_name)
    test_count = suite.countTestCases()
    if test_count == 0:
        return True, test_count, 0, f"{module_name}: no tests loaded; skipped ({time.perf_counter() - started:.2f}s)", []

    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=verbosity)
    result = runner.run(suite)
    failed_test_ids = [
        test.id()
        for test, _traceback in [*result.failures, *result.errors]
    ]
    output = stream.getvalue().strip()
    output = f"{output}\nDuration: {time.perf_counter() - started:.2f}s"
    return result.wasSuccessful(), test_count, len(result.skipped), output, failed_test_ids


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
    failure_details: list[str] = []
    skipped_tests = 0
    loaded_tests = 0

    for test_file in sorted(start_directory.glob(args.pattern)):
        module_name = module_name_for(test_file)
        ok, test_count, module_skipped, output, failed_test_ids = run_module(module_name, args.verbosity)
        loaded_tests += test_count
        skipped_tests += module_skipped
        header = f"=== {module_name} ({test_count} tests) ==="
        if ok:
            emit_progress(header)
            if output:
                emit_progress(output)
        else:
            failed_modules.append(module_name)
            tail = "\n".join(output.splitlines()[-80:])
            detail = "\n".join(
                [
                    header,
                    "Failed tests:",
                    *(f"- {test_id}" for test_id in failed_test_ids),
                    "Output tail:",
                    tail,
                ]
            )
            failure_details.append(detail)
            emit_error(header)
            if output:
                emit_error(output)

    emit_progress(
        f"Unit test summary: {loaded_tests} tests loaded, {skipped_tests} skipped, "
        f"{len(failed_modules)} failed modules"
    )

    if failed_modules:
        if args.failure_report:
            with open(args.failure_report, "w", encoding="utf-8") as report:
                report.write("\n\n".join(failure_details))
                report.write("\n")
        emit_github_failure_summary(failed_modules)
        emit_error("Unit failures: " + ", ".join(failed_modules))
        return 1

    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    sys.exit(main())
