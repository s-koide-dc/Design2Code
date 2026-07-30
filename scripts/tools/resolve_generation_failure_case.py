"""Link an open generation failure to a verified success that resolves it."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate.validate_generation_failure_cases import DEFAULT_REGISTRY, validate_registry
from scripts.validate.validate_verified_generation_cases import DEFAULT_REGISTRY as DEFAULT_VERIFIED_REGISTRY


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve an open generation failure using a verified success case.")
    parser.add_argument("--failure-case-id", required=True)
    parser.add_argument("--verified-case-id", required=True)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--verified-registry", type=Path, default=DEFAULT_VERIFIED_REGISTRY)
    args = parser.parse_args()

    errors = validate_registry(args.registry, args.verified_registry)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    verified = json.loads(args.verified_registry.read_text(encoding="utf-8"))
    verified_ids = {case["case_id"] for case in verified["cases"]}
    if args.verified_case_id not in verified_ids:
        parser.error("--verified-case-id is not registered in the verified generation-case registry")

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    target = next((case for case in registry["cases"] if case.get("case_id") == args.failure_case_id), None)
    if target is None:
        parser.error("--failure-case-id is not registered in the generation failure-case registry")
    if target.get("status") != "open":
        parser.error("only open failure cases can be resolved")
    target["status"] = "resolved"
    target["resolution"] = {
        "verified_case_id": args.verified_case_id,
        "resolved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    args.registry.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = validate_registry(args.registry, args.verified_registry)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Resolved failure case: {args.failure_case_id} -> {args.verified_case_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
