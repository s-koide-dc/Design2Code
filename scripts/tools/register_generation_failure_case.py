"""Record a reproducible failing design only when the full review snapshot fails."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.design.review_design_generation_snapshot import build_review_snapshot
from scripts.validate.validate_generation_failure_cases import DEFAULT_REGISTRY, classify_failure_payload, validate_registry
from scripts.validate.fingerprint_scopes import generation_fingerprint


def _case_id(design: Path, reason: str) -> str:
    stem = design.name.removesuffix(".design.md")
    normalized = "".join(f"_{char.lower()}" if char.isupper() else char for char in stem).lstrip("_")
    return f"{normalized}_{reason.lower()}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a reproducible generation failure.")
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
    if snapshot["exit_code"] == 0:
        print("Registration refused: this design passed the full generation review.")
        return 1
    classification = classify_failure_payload(snapshot["payload"])
    if classification is None:
        print("Registration refused: failure did not expose a structured pipeline outcome.")
        return 1
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    reason = classification["reason"]
    case_id = args.case_id or _case_id(design, reason)
    entry = {
        "case_id": case_id,
        "design_path": design.relative_to(ROOT).as_posix(),
        "design_sha256": hashlib.sha256(design.read_bytes()).hexdigest(),
        "generation_fingerprint": generation_fingerprint(),
        "observed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "stage": classification["stage"],
        "reason": reason,
        "guidance": classification["guidance"],
        "status": "open",
    }
    registry["cases"] = sorted([case for case in registry["cases"] if case.get("case_id") != case_id] + [entry], key=lambda case: case["case_id"])
    args.registry.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = validate_registry(args.registry)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Registered failure case: {case_id} ({classification['stage']}/{reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
