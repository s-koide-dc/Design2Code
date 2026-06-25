# -*- coding: utf-8 -*-
"""Run snapshot-based design-to-code regression checks for multiple scenarios."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.review_design_generation_snapshot import build_review_snapshot
from src.utils.cli_output import emit_error, emit_json_stdout

DEFAULT_DESIGNS = [
    "scenarios/ComplexLinqSearch.design.md",
    "scenarios/CsvSalesAggregation.design.md",
    "scenarios/DailyInventorySync.design.md",
    "scenarios/SecureOrderProcessing.design.md",
    "scenarios/AppModeEchoMinimal.design.md",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run design generation regression checks across one or more .design.md scenarios."
    )
    parser.add_argument(
        "--design",
        action="append",
        dest="designs",
        help="Input .design.md path. Can be specified multiple times. Defaults to curated regression scenarios.",
    )
    parser.add_argument("--output-dir", help="Optional root output directory for per-scenario snapshots")
    parser.add_argument("--retry", action="store_true", help="Enable replanner retry loop")
    parser.add_argument("--allow-fallback", action="store_true", help="Allow fallback synthesis pass")
    parser.add_argument("--assist-endpoint-url", help="Optional OpenAI-compatible /v1/chat/completions endpoint")
    parser.add_argument("--assist-model-id", default="local-assist", help="Model id for optional literal assistance")
    parser.add_argument("--assist-timeout-seconds", type=int, default=60, help="Timeout in seconds for optional literal assistance")
    parser.add_argument("--assist-max-new-tokens", type=int, default=384, help="Generation cap for optional literal assistance")
    parser.add_argument(
        "--assist-policy",
        choices=["on_blocked_only", "always"],
        default="on_blocked_only",
        help="When to invoke optional literal assistance",
    )
    return parser.parse_args()


def _resolve_designs(args: argparse.Namespace) -> List[Path]:
    raw_designs = args.designs or DEFAULT_DESIGNS
    return [Path(item) for item in raw_designs]


def _build_snapshot_args(args: argparse.Namespace, design_path: Path, output_dir: Path | None) -> SimpleNamespace:
    return SimpleNamespace(
        design=str(design_path),
        output_dir=str(output_dir) if output_dir else None,
        retry=args.retry,
        allow_fallback=args.allow_fallback,
        assist_endpoint_url=args.assist_endpoint_url,
        assist_model_id=args.assist_model_id,
        assist_timeout_seconds=args.assist_timeout_seconds,
        assist_max_new_tokens=args.assist_max_new_tokens,
        assist_policy=args.assist_policy,
    )


def main() -> int:
    args = _parse_args()
    design_paths = _resolve_designs(args)
    missing = [str(path) for path in design_paths if not path.is_file()]
    if missing:
        emit_error(f"design file not found: {missing[0]}")
        return 1

    root_output_dir = Path(args.output_dir) if args.output_dir else None
    results: List[Dict[str, Any]] = []
    failed = 0

    for design_path in design_paths:
        scenario_output_dir = None
        if root_output_dir:
            scenario_output_dir = root_output_dir / design_path.stem
        snapshot = build_review_snapshot(_build_snapshot_args(args, design_path, scenario_output_dir))
        payload = snapshot["payload"]
        success = int(snapshot["exit_code"]) == 0
        if not success:
            failed += 1
        results.append(
            {
                "design": payload.get("design"),
                "success": success,
                "module_name": payload.get("module_name"),
                "inference_status": (payload.get("inference") or {}).get("status"),
                "verification_valid": bool((payload.get("verification") or {}).get("valid")),
                "spec_issue_count": len(payload.get("spec_issues", [])),
                "generated_code_path": payload.get("generated_code_path"),
                "payload": payload,
            }
        )

    emit_json_stdout(
        {
            "scenario_count": len(design_paths),
            "passed": len(design_paths) - failed,
            "failed": failed,
            "results": results,
        }
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
