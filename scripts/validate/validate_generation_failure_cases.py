"""Validate structured, reproducible generation-failure records."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate.validate_verified_generation_cases import (
    DEFAULT_REGISTRY as DEFAULT_VERIFIED_REGISTRY,
)
from scripts.validate.fingerprint_scopes import generation_fingerprint

DEFAULT_REGISTRY = ROOT / "resources" / "generation_failure_cases.json"
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_STAGES = {"design_inference", "specification", "compilation", "generation_quality", "runtime_oracle"}
_GUIDANCE = {
    "COMPACT_STEP_INVALID": "Use the exact [step|INTENT|TARGET|OUTPUT|source=...|source_kind=...] compact-step grammar, or use a complete explicit tag.",
    "MISSING_EXPLICIT_STEP_METADATA": "Add an explicit [KIND|INTENT|TARGET|OUTPUT|EFFECT] tag to the blocked Core Logic step.",
    "NO_CANDIDATE": "Add the required explicit source, type, reference, literal, or semantic role; supported generation does not infer missing semantics.",
    "MISSING_SQL": "Provide an explicit SQL literal and a db data source for the database operation.",
    "MISSING_COMMAND": "Provide an explicit command literal for CMD_RUN.",
    "UNSAFE_COMMAND": "Use a command allowed by the safety policy, or remove the CMD_RUN step.",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify_failure_payload(payload: dict[str, Any]) -> dict[str, str] | None:
    """Classify only explicit pipeline outcomes; never infer from free-form logs."""
    inference = payload.get("inference") if isinstance(payload.get("inference"), dict) else {}
    issues = inference.get("issues") if isinstance(inference.get("issues"), list) else []
    if inference.get("status") == "blocked" and issues:
        first = issues[0] if isinstance(issues[0], dict) else {}
        reason = str(first.get("reason") or "NO_CANDIDATE")
        return {
            "stage": "design_inference",
            "reason": reason,
            "guidance": _GUIDANCE.get(reason, "Inspect the structured inference issue and add the required explicit design information."),
        }
    if payload.get("spec_issues"):
        return {
            "stage": "specification",
            "reason": "SPECIFICATION_VALIDATION_FAILED",
            "guidance": "Resolve the reported StructuredSpec validation issues before generation.",
        }
    verification = payload.get("verification") if isinstance(payload.get("verification"), dict) else {}
    if verification and not verification.get("valid", True):
        return {
            "stage": "compilation",
            "reason": "COMPILATION_VERIFICATION_FAILED",
            "guidance": "Inspect the compiler diagnostics in the snapshot and correct the explicit IR or generator defect.",
        }
    quality = payload.get("quality") if isinstance(payload.get("quality"), dict) else {}
    if quality and not quality.get("valid", True):
        return {
            "stage": "generation_quality",
            "reason": "GENERATION_QUALITY_FAILED",
            "guidance": "Resolve the explicit generation-quality findings before accepting this design.",
        }
    runtime = payload.get("runtime_oracle_execution") if isinstance(payload.get("runtime_oracle_execution"), dict) else {}
    if runtime and (not runtime.get("valid", True) or runtime.get("failed", 0)):
        return {
            "stage": "runtime_oracle",
            "reason": "RUNTIME_ORACLE_FAILED",
            "guidance": "Compare the explicit runtime oracle with generated behavior and correct the design, oracle, or generator.",
        }
    return None


def _verified_case_ids(registry_path: Path) -> tuple[set[str], list[str]]:
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return set(), [f"cannot read verified registry: {exc}"]
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        return set(), ["verified registry cases must be a list"]
    return {
        str(case.get("case_id"))
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("case_id"), str)
    }, []


def validate_registry(
    registry_path: Path,
    verified_registry_path: Path = DEFAULT_VERIFIED_REGISTRY,
) -> list[str]:
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read registry: {exc}"]
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return ["schema_version must be 1"]
    cases = payload.get("cases")
    if not isinstance(cases, list):
        return ["cases must be a list"]
    errors: list[str] = []
    ids: set[str] = set()
    current_fingerprint = generation_fingerprint()
    verified_case_ids, verified_errors = _verified_case_ids(verified_registry_path)
    errors.extend(verified_errors)
    for index, case in enumerate(cases, start=1):
        prefix = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not _CASE_ID.fullmatch(case_id) or case_id in ids:
            errors.append(f"{prefix}.case_id must be unique lower_snake_case")
        else:
            ids.add(case_id)
        design_path = case.get("design_path")
        design = (ROOT / design_path).resolve() if isinstance(design_path, str) else None
        if not isinstance(design_path, str) or design is None or ROOT not in design.parents or not design.is_file():
            errors.append(f"{prefix}.design_path must name an existing workspace file")
        elif case.get("design_sha256") != sha256_file(design):
            errors.append(f"{prefix}.design_sha256 does not match {design_path}")
        if case.get("generation_fingerprint") != current_fingerprint:
            errors.append(f"{prefix}.generation_fingerprint does not match the current supported generator")
        if case.get("stage") not in _STAGES:
            errors.append(f"{prefix}.stage is invalid")
        if not isinstance(case.get("reason"), str) or not case["reason"]:
            errors.append(f"{prefix}.reason is required")
        if not isinstance(case.get("guidance"), str) or not case["guidance"]:
            errors.append(f"{prefix}.guidance is required")
        status = case.get("status")
        if status not in {"open", "resolved"}:
            errors.append(f"{prefix}.status must be open or resolved")
        resolution = case.get("resolution")
        if status == "open" and resolution is not None:
            errors.append(f"{prefix}.resolution is allowed only for resolved cases")
        if status == "resolved":
            if not isinstance(resolution, dict):
                errors.append(f"{prefix}.resolution is required for resolved cases")
            else:
                verified_case_id = resolution.get("verified_case_id")
                if verified_case_id not in verified_case_ids:
                    errors.append(f"{prefix}.resolution.verified_case_id must reference a verified generation case")
                resolved_at = resolution.get("resolved_at")
                if not isinstance(resolved_at, str) or not resolved_at.endswith("Z"):
                    errors.append(f"{prefix}.resolution.resolved_at must be an ISO-8601 UTC timestamp")
    return errors


def replay_open_failures(
    registry_path: Path,
    snapshot_builder: Any | None = None,
) -> list[str]:
    """Re-run open failures and require their structured cause to remain exact."""
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read registry: {exc}"]
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        return ["cases must be a list"]
    if snapshot_builder is None:
        from scripts.design.review_design_generation_snapshot import build_review_snapshot

        snapshot_builder = build_review_snapshot
    errors: list[str] = []
    for case in cases:
        if not isinstance(case, dict) or case.get("status") != "open":
            continue
        case_id = str(case.get("case_id") or "<unknown>")
        design_path = case.get("design_path")
        if not isinstance(design_path, str):
            errors.append(f"{case_id}: design_path is missing")
            continue
        snapshot = snapshot_builder(SimpleNamespace(
            design=str(ROOT / design_path), output_dir=None, retry=False, allow_fallback=False,
            assist_endpoint_url=None, assist_model_id="local-assist", assist_timeout_seconds=60,
            assist_max_new_tokens=384, fail_on_maintainability=True,
            run_runtime_oracles=True, assist_policy="on_blocked_only",
        ))
        if not isinstance(snapshot, dict) or snapshot.get("exit_code") == 0:
            errors.append(f"{case_id}: expected failure now passes")
            continue
        failure = classify_failure_payload(snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {})
        if failure is None:
            errors.append(f"{case_id}: failure no longer exposes a structured pipeline outcome")
            continue
        if failure["stage"] != case.get("stage") or failure["reason"] != case.get("reason"):
            errors.append(
                f"{case_id}: expected {case.get('stage')}/{case.get('reason')}, "
                f"observed {failure['stage']}/{failure['reason']}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generation failure-case registry.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--verified-registry", type=Path, default=DEFAULT_VERIFIED_REGISTRY)
    parser.add_argument("--execute", action="store_true", help="Re-run all open cases and verify their structured failure classification.")
    args = parser.parse_args()
    errors = validate_registry(args.registry, args.verified_registry)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: generation failure-case registry is valid.")
    if args.execute:
        replay_errors = replay_open_failures(args.registry)
        if replay_errors:
            for error in replay_errors:
                print(f"ERROR: {error}")
            return 1
        print("OK: all open generation failure cases reproduce their registered classification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
