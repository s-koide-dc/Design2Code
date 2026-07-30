"""Validate and replay verified multi-file project generation cases."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate.fingerprint_scopes import project_generation_fingerprint

DEFAULT_REGISTRY = ROOT / "resources" / "verified_project_generation_cases.json"
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_EVIDENCE = {
    "project_build",
    "generated_wiring_tests",
    "generated_endpoint_tests",
    "generated_sqlite_tests",
    "generated_sqlserver_tests",
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_registry(registry_path: Path = DEFAULT_REGISTRY) -> list[str]:
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read registry: {exc}"]
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return ["schema_version must be 1"]
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        return ["cases must be a non-empty list"]
    errors: list[str] = []
    case_ids: set[str] = set()
    paths: set[str] = set()
    current_fingerprint = project_generation_fingerprint()
    for index, case in enumerate(cases, start=1):
        prefix = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not _CASE_ID.fullmatch(case_id) or case_id in case_ids:
            errors.append(f"{prefix}.case_id must be unique lower_snake_case")
        else:
            case_ids.add(case_id)
        design_path = case.get("design_path")
        if not isinstance(design_path, str) or not design_path.startswith("scenarios/"):
            errors.append(f"{prefix}.design_path must be under scenarios/")
            continue
        design = (ROOT / design_path).resolve()
        if ROOT not in design.parents or not design.is_file():
            errors.append(f"{prefix}.design_path does not exist: {design_path}")
        elif case.get("design_sha256") != _sha256_file(design):
            errors.append(f"{prefix}.design_sha256 does not match {design_path}")
        if design_path in paths:
            errors.append(f"duplicate project design_path: {design_path}")
        paths.add(design_path)
        if not isinstance(case.get("project_name"), str) or not case["project_name"]:
            errors.append(f"{prefix}.project_name is required")
        if not isinstance(case.get("generator_commit"), str) or not re.fullmatch(r"[0-9a-f]{40}", case["generator_commit"]):
            errors.append(f"{prefix}.generator_commit must be a full git SHA")
        if case.get("project_generation_fingerprint") != current_fingerprint:
            errors.append(f"{prefix}.project_generation_fingerprint does not match the current project generator")
        if not isinstance(case.get("verified_at"), str) or not case["verified_at"].endswith("Z"):
            errors.append(f"{prefix}.verified_at must be an ISO-8601 UTC timestamp")
        evidence = case.get("evidence")
        if not isinstance(evidence, dict) or set(evidence) != _EVIDENCE or any(evidence.get(key) != "passed" for key in _EVIDENCE):
            errors.append(f"{prefix}.evidence must record every generated project test family as passed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate verified multi-file project generation cases.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--execute", action="store_true", help="Generate and run every registered project case.")
    args = parser.parse_args()
    errors = validate_registry(args.registry)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: verified project generation-case registry is valid.")
    if args.execute:
        payload = json.loads(args.registry.read_text(encoding="utf-8"))
        for case in payload["cases"]:
            completed = subprocess.run(
                [sys.executable, "scripts/validate/validate_generated_sqlserver.py", "--design", case["design_path"]],
                cwd=ROOT,
                check=False,
            )
            if completed.returncode != 0:
                return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
