"""Run unit-test modules in isolated processes and report slow or stuck modules."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-module timeout in seconds.")
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--start-directory", default=str(ROOT / "tests" / "unit"))
    return parser.parse_args()


def module_name(test_file: Path) -> str:
    return ".".join(test_file.with_suffix("").relative_to(ROOT).parts)


def main() -> int:
    args = parse_args()
    failures: list[str] = []
    records: list[tuple[float, str, str]] = []

    for test_file in sorted(Path(args.start_directory).glob(args.pattern)):
        name = module_name(test_file)
        started = time.perf_counter()
        try:
            result = subprocess.run(
                [sys.executable, "-m", "unittest", name],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=args.timeout,
                check=False,
            )
            duration = time.perf_counter() - started
            no_tests = "Ran 0 tests" in (result.stdout + result.stderr)
            status = "PASS" if result.returncode == 0 or no_tests else "FAIL"
            if result.returncode != 0 and not no_tests:
                failures.append(name)
            detail = (result.stdout + result.stderr).splitlines()
            tail = " | ".join(detail[-2:]) if detail else ""
        except subprocess.TimeoutExpired:
            duration = time.perf_counter() - started
            status = "TIMEOUT"
            failures.append(name)
            tail = f"exceeded {args.timeout:.1f}s"

        records.append((duration, name, status))
        print(f"{status:7} {duration:7.2f}s {name} {tail}")

    print("\nSlowest modules:")
    for duration, name, status in sorted(records, reverse=True)[:10]:
        print(f"{duration:7.2f}s {status:7} {name}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
