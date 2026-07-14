# -*- coding: utf-8 -*-
"""Run snapshot-based design-to-code regression checks for multiple scenarios."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.design.review_design_generation_snapshot import build_review_snapshot
from src.utils.cli_output import emit_error, emit_json_stdout

DEFAULT_DESIGNS = [
    "scenarios/ComplexLinqSearch.design.md",
    "scenarios/CsvSalesAggregation.design.md",
    "scenarios/ProductApiFilteredCatalog.design.md",
    "scenarios/CustomerApiWithEntitySpec.design.md",
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
        "--fail-on-maintainability",
        action="store_true",
        help="Fail scenarios when generated-code maintainability thresholds are exceeded.",
    )
    parser.add_argument(
        "--run-runtime-oracles",
        action="store_true",
        help="Execute explicit JSON runtime_oracle contracts from design test cases.",
    )
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
        fail_on_maintainability=args.fail_on_maintainability,
        run_runtime_oracles=args.run_runtime_oracles,
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

    previous_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        for design_path in design_paths:
            scenario_output_dir = None
            if root_output_dir:
                scenario_output_dir = root_output_dir / design_path.stem
            snapshot = build_review_snapshot(_build_snapshot_args(args, design_path, scenario_output_dir))
            payload = snapshot["payload"]
            success = int(snapshot["exit_code"]) == 0
            if not success:
                failed += 1
            quality = payload.get("quality") or {}
            maintainability = quality.get("maintainability") or {}
            runtime_oracle = payload.get("runtime_oracle") or {}
            runtime_oracle_execution = payload.get("runtime_oracle_execution") or {}
            results.append(
                {
                    "design": payload.get("design"),
                    "success": success,
                    "module_name": payload.get("module_name"),
                    "inference_status": (payload.get("inference") or {}).get("status"),
                    "verification_valid": bool((payload.get("verification") or {}).get("valid")),
                    "quality_valid": bool(quality.get("valid")),
                    "quality_issue_count": len(quality.get("issues") or []),
                    "runtime_oracle_ready_count": runtime_oracle.get("ready_count", 0),
                    "runtime_oracle_unverified_count": runtime_oracle.get("unverified_count", 0),
                    "runtime_oracle_invalid_count": runtime_oracle.get("invalid_count", 0),
                    "runtime_oracle_execution_valid": runtime_oracle_execution.get("valid", True),
                    "runtime_oracle_execution_passed": runtime_oracle_execution.get("passed", 0),
                    "runtime_oracle_execution_failed": runtime_oracle_execution.get("failed", 0),
                    "maintainability_finding_count": len(maintainability.get("findings") or []),
                    "maintainability": {
                        "method_count": maintainability.get("method_count", 0),
                        "class_count": maintainability.get("class_count", 0),
                        "constructor_count": maintainability.get("constructor_count", 0),
                        "helper_method_count": maintainability.get("helper_method_count", 0),
                        "operation_method_count": maintainability.get("operation_method_count", 0),
                        "total_line_count": maintainability.get("total_line_count", 0),
                        "max_method_line_count": maintainability.get("max_method_line_count", 0),
                        "max_method_try_count": maintainability.get("max_method_try_count", 0),
                        "max_method_catch_count": maintainability.get("max_method_catch_count", 0),
                        "max_operation_method_line_count": maintainability.get("max_operation_method_line_count", 0),
                        "max_operation_method_try_count": maintainability.get("max_operation_method_try_count", 0),
                        "max_operation_method_catch_count": maintainability.get("max_operation_method_catch_count", 0),
                        "blueprint_statement_count": maintainability.get("blueprint_statement_count", 0),
                        "analysis_source": maintainability.get("analysis_source"),
                        "findings": maintainability.get("findings") or [],
                    },
                    "spec_issue_count": len(payload.get("spec_issues", [])),
                    "generated_code_path": payload.get("generated_code_path"),
                    "payload": payload,
                }
            )
    finally:
        logging.disable(previous_disable)

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
