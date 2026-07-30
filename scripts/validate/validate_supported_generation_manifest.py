"""Validate the canonical supported design-to-code scope."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "resources" / "supported_generation_designs.json"
DEFAULT_VERIFIED_REGISTRY = ROOT / "resources" / "verified_generation_cases.json"
DEFAULT_FAILURE_REGISTRY = ROOT / "resources" / "generation_failure_cases.json"


def load_supported_designs(profile: str = "quality", manifest_path: Path = DEFAULT_MANIFEST) -> list[str]:
    """Return the canonical verified design paths after structural validation."""
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    designs = payload["designs"]
    if profile == "quality":
        return [entry["design_path"] for entry in designs if entry["status"] == "verified"]
    if profile == "smoke":
        return [entry["design_path"] for entry in designs if entry["status"] == "verified" and entry.get("smoke") is True]
    raise ValueError(f"unknown regression profile: {profile}")


def _load_cases(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], [f"cannot read {path.name}: {exc}"]
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        return [], [f"{path.name} cases must be a list"]
    return [case for case in cases if isinstance(case, dict)], []


def validate_manifest(
    manifest_path: Path = DEFAULT_MANIFEST,
    verified_registry_path: Path = DEFAULT_VERIFIED_REGISTRY,
    failure_registry_path: Path = DEFAULT_FAILURE_REGISTRY,
) -> list[str]:
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read manifest: {exc}"]
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return ["manifest schema_version must be 1"]
    entries = manifest.get("designs")
    if not isinstance(entries, list) or not entries:
        return ["manifest designs must be a non-empty list"]

    verified_cases, verified_errors = _load_cases(verified_registry_path)
    failure_cases, failure_errors = _load_cases(failure_registry_path)
    errors.extend(verified_errors)
    errors.extend(failure_errors)
    verified_by_id = {case.get("case_id"): case for case in verified_cases}
    failure_by_id = {case.get("case_id"): case for case in failure_cases}
    registered_verified_paths = {case.get("design_path") for case in verified_cases}
    seen_paths: set[str] = set()

    for index, entry in enumerate(entries, start=1):
        prefix = f"designs[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        design_path = entry.get("design_path")
        if not isinstance(design_path, str) or not design_path.startswith("scenarios/"):
            errors.append(f"{prefix}.design_path must be under scenarios/")
            continue
        design = (ROOT / design_path).resolve()
        if ROOT not in design.parents or not design.is_file():
            errors.append(f"{prefix}.design_path does not exist: {design_path}")
        if design_path in seen_paths:
            errors.append(f"duplicate supported design_path: {design_path}")
        seen_paths.add(design_path)

        status = entry.get("status")
        smoke = entry.get("smoke", False)
        if not isinstance(smoke, bool):
            errors.append(f"{prefix}.smoke must be a boolean when provided")
        if status == "verified":
            case_id = entry.get("verified_case_id")
            case = verified_by_id.get(case_id)
            if not isinstance(case_id, str) or case is None:
                errors.append(f"{prefix}.verified_case_id must reference a verified generation case")
            elif case.get("design_path") != design_path:
                errors.append(f"{prefix}.verified_case_id must reference the same design_path")
            if "failure_case_id" in entry:
                errors.append(f"{prefix} must not contain failure_case_id when verified")
        elif status == "known_failure":
            case_id = entry.get("failure_case_id")
            case = failure_by_id.get(case_id)
            if not isinstance(case_id, str) or case is None:
                errors.append(f"{prefix}.failure_case_id must reference a generation failure case")
            elif case.get("design_path") != design_path:
                errors.append(f"{prefix}.failure_case_id must reference the same design_path")
            elif case.get("status") != "open":
                errors.append(f"{prefix}.failure_case_id must reference an open failure case")
            if "verified_case_id" in entry:
                errors.append(f"{prefix} must not contain verified_case_id when known_failure")
            if smoke:
                errors.append(f"{prefix}.smoke is allowed only for verified designs")
        else:
            errors.append(f"{prefix}.status must be verified or known_failure")

    unmanifested_verified = sorted(
        path for path in registered_verified_paths if isinstance(path, str) and path not in seen_paths
    )
    for path in unmanifested_verified:
        errors.append(f"verified registry design is missing from manifest: {path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the supported generation design manifest.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--verified-registry", type=Path, default=DEFAULT_VERIFIED_REGISTRY)
    parser.add_argument("--failure-registry", type=Path, default=DEFAULT_FAILURE_REGISTRY)
    args = parser.parse_args()
    errors = validate_manifest(args.manifest, args.verified_registry, args.failure_registry)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: supported generation design manifest is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
