"""Run a design through the full gate and register only a verified success."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.design.review_design_generation_snapshot import build_review_snapshot
from scripts.validate.validate_verified_generation_cases import DEFAULT_REGISTRY, validate_registry
from scripts.validate.fingerprint_scopes import compilation_fingerprint, generation_fingerprint, generation_quality_fingerprint, runtime_oracle_fingerprint


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case_id(design: Path) -> str:
    name = design.name.removesuffix(".design.md")
    return "".join(f"_{char.lower()}" if char.isupper() else char for char in name).lstrip("_")


def _git_commit() -> str:
    completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a fully verified generation success.")
    parser.add_argument("--design", required=True, type=Path)
    parser.add_argument("--case-id")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args()
    design = args.design.resolve()
    if ROOT not in design.parents or not design.is_file():
        parser.error("--design must be an existing file inside this workspace")
    snapshot = build_review_snapshot(SimpleNamespace(
        design=str(design), output_dir=None, retry=False, allow_fallback=False,
        assist_endpoint_url=None, assist_model_id="local-assist", assist_timeout_seconds=60,
        assist_max_new_tokens=384, fail_on_maintainability=True,
        run_runtime_oracles=True, assist_policy="on_blocked_only",
    ))
    payload = snapshot["payload"]
    execution = payload.get("runtime_oracle_execution") or {}
    oracle = payload.get("runtime_oracle") or {}
    if (
        snapshot["exit_code"] != 0
        or not execution.get("valid")
        or execution.get("failed", 0) != 0
        or oracle.get("ready_count", 0) == 0
        or execution.get("passed", 0) != oracle.get("ready_count", 0)
    ):
        print("Registration refused: generation, quality, compilation, or runtime oracle did not pass.")
        return 1
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    case_id = args.case_id or _case_id(design)
    entry = {
        "case_id": case_id,
        "design_path": design.relative_to(ROOT).as_posix(),
        "design_sha256": _sha256(design),
        "generator_commit": _git_commit(),
        "generation_fingerprint": generation_fingerprint(),
        "compilation_fingerprint": compilation_fingerprint(),
        "generation_quality_fingerprint": generation_quality_fingerprint(),
        "runtime_oracle_fingerprint": runtime_oracle_fingerprint(),
        "verified_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "evidence": {"compilation": "passed", "generation_quality": "passed", "runtime_oracle": "passed"},
    }
    cases = [case for case in registry["cases"] if case.get("case_id") != case_id]
    cases.append(entry)
    registry["cases"] = sorted(cases, key=lambda case: case["case_id"])
    args.registry.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = validate_registry(args.registry)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Registered verified case: {case_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
