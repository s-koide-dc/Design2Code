"""Validate local semantic assets and their exercised design-generation paths."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.asset_manifest import AssetManifestError, load_requirements, validate_manifest


CAPABILITIES = ("semantic_method_search", "dictionary_search")
CI_TEST_MATRIX = ROOT / "tests" / "ci_test_matrix.json"
SEMANTIC_TEST_MODULES = (
    "tests.integration.test_vector_engine_real_model",
    "tests.integration.test_semantic_method_search",
    "tests.unit.test_semantic_analyzer_search",
    "tests.integration.test_natural_numeric_predicate_assets",
)


def asset_dependent_integration_modules(matrix_path: Path = CI_TEST_MATRIX) -> tuple[str, ...]:
    """Read the explicit CI exclusion boundary; do not discover tests heuristically."""
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    excluded = matrix["integration"]["ci_excluded"]
    modules = tuple(
        f"tests.integration.{Path(entry['file']).stem}"
        for entry in excluded
    )
    if len(modules) != len(set(modules)):
        raise ValueError("CI exclusion matrix contains duplicate asset-dependent integration modules")
    return modules


def test_modules(matrix_path: Path = CI_TEST_MATRIX) -> tuple[str, ...]:
    """Return the complete asset-dependent quality suite in stable order."""
    combined = (*SEMANTIC_TEST_MODULES, *asset_dependent_integration_modules(matrix_path))
    return tuple(dict.fromkeys(combined))


def _run_module(module: str, timeout_seconds: int) -> dict[str, Any]:
    env = os.environ.copy()
    env.pop("SKIP_VECTOR_MODEL", None)
    env["SUPPRESS_VECTOR_WARNINGS"] = "1"
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", module, "-v"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        return {
            "module": module,
            "status": "passed" if completed.returncode == 0 else "failed",
            "return_code": completed.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "output_tail": output[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return {
            "module": module,
            "status": "timeout",
            "return_code": None,
            "duration_seconds": round(time.monotonic() - started, 3),
            "output_tail": output[-4000:],
        }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local semantic-asset quality gate.")
    parser.add_argument("--workspace-root", type=Path, default=ROOT)
    parser.add_argument("--requirements", type=Path, default=ROOT / "config" / "asset_requirements.json")
    parser.add_argument("--manifest", type=Path, default=ROOT / "logs" / "local_asset_manifest.json")
    parser.add_argument("--output", type=Path, default=ROOT / "logs" / "local_semantic_quality_gate.json")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be greater than zero")

    report: dict[str, Any] = {
        "schema_version": 1,
        "executed_utc": datetime.now(UTC).isoformat(),
        "capabilities": list(CAPABILITIES),
        "asset_manifest": {"status": "blocked", "mismatches": []},
        "tests": [],
    }
    try:
        requirements = load_requirements(args.requirements)
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        mismatches = validate_manifest(args.workspace_root, requirements, manifest, list(CAPABILITIES))
        report["asset_manifest"] = {"status": "valid" if not mismatches else "mismatch", "mismatches": mismatches}
    except (AssetManifestError, OSError, json.JSONDecodeError) as exc:
        report["asset_manifest"] = {"status": "blocked", "mismatches": [str(exc)]}

    if report["asset_manifest"]["status"] != "valid":
        report["status"] = "blocked"
        _write_report(args.output, report)
        print(f"Local semantic quality gate: blocked ({args.output})", file=sys.stderr)
        return 2

    report["tests"] = [_run_module(module, args.timeout_seconds) for module in test_modules()]
    report["status"] = "passed" if all(test["status"] == "passed" for test in report["tests"]) else "failed"
    _write_report(args.output, report)
    print(f"Local semantic quality gate: {report['status']} ({args.output})")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
