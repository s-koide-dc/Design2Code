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
from scripts.validate.validate_supported_generation_manifest import load_supported_designs
from src.utils.cli_output import emit_error, emit_json_stdout

QUALITY_DESIGNS = load_supported_designs("quality")
SMOKE_DESIGNS = load_supported_designs("smoke")

# Preserve the existing no-option behavior for local callers and CI integrations.
DEFAULT_DESIGNS = QUALITY_DESIGNS
PROFILE_DESIGNS = {
    "smoke": SMOKE_DESIGNS,
    "quality": QUALITY_DESIGNS,
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run design generation regression checks across one or more .design.md scenarios."
    )
    parser.add_argument(
        "--design",
        action="append",
        dest="designs",
        help="Input .design.md path. Can be specified multiple times and overrides --profile.",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_DESIGNS),
        default="quality",
        help="Curated regression profile used when --design is not specified (default: quality).",
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
        "--require-runtime-oracles",
        action="store_true",
        help="Require every design test case to have a valid explicit runtime_oracle and execute it.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Omit the detailed per-scenario payload from stdout.",
    )
    parser.add_argument(
        "--assist-policy",
        choices=["on_blocked_only", "always"],
        default="on_blocked_only",
        help="When to invoke optional literal assistance",
    )
    return parser.parse_args()


def _resolve_designs(args: argparse.Namespace) -> List[Path]:
    raw_designs = args.designs or PROFILE_DESIGNS[args.profile]
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


def _first_non_empty_line(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    for line in value.splitlines():
        text = line.strip()
        if text:
            return text
    return None


def summarize_runtime_oracle_failures(runtime_oracle_execution: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return compact oracle failure diagnostics suitable for regression summaries."""
    failures: List[Dict[str, Any]] = []
    results = runtime_oracle_execution.get("results") if isinstance(runtime_oracle_execution, dict) else []
    if not isinstance(results, list):
        results = []
    for result in results:
        if not isinstance(result, dict) or result.get("success", True):
            continue
        case_failures = result.get("failures") if isinstance(result.get("failures"), list) else []
        normalized_case_failures: List[Dict[str, Any]] = []
        for failure in case_failures:
            if not isinstance(failure, dict):
                continue
            normalized_case_failures.append({
                "test_name": failure.get("test_name"),
                "message": _first_non_empty_line(failure.get("message")),
                "stack_trace": _first_non_empty_line(failure.get("stack_trace")),
            })
        failures.append({
            "id": result.get("id"),
            "scenario": result.get("scenario"),
            "error_type": result.get("error_type"),
            "message": _first_non_empty_line(result.get("message")),
            "failures": normalized_case_failures,
        })
    issues = runtime_oracle_execution.get("issues") if isinstance(runtime_oracle_execution, dict) else None
    if isinstance(issues, list):
        for issue in issues:
            failures.append({
                "id": None,
                "scenario": None,
                "error_type": "RUNTIME_ORACLE_CONTRACT_INVALID",
                "message": str(issue),
                "failures": [],
            })
    return failures


def runtime_oracle_requirement_issues(
    runtime_oracle: Dict[str, Any],
    runtime_oracle_execution: Dict[str, Any],
) -> List[str]:
    """Return requirement violations for a fully executable runtime-oracle suite."""
    case_count = runtime_oracle.get("case_count", 0)
    ready_count = runtime_oracle.get("ready_count", 0)
    unverified_count = runtime_oracle.get("unverified_count", 0)
    invalid_count = runtime_oracle.get("invalid_count", 0)
    issues: List[str] = []

    if case_count == 0:
        issues.append("no design test cases define an explicit runtime_oracle")
    if unverified_count:
        issues.append(f"runtime_oracle has {unverified_count} unverified case(s)")
    if invalid_count:
        issues.append(f"runtime_oracle has {invalid_count} invalid case(s)")
    if ready_count != case_count:
        issues.append(f"runtime_oracle ready cases {ready_count} do not match test cases {case_count}")

    executed_count = runtime_oracle_execution.get("case_count", 0)
    passed_count = runtime_oracle_execution.get("passed", 0)
    failed_count = runtime_oracle_execution.get("failed", 0)
    if not runtime_oracle_execution.get("requested"):
        issues.append("runtime_oracle execution was not requested")
    elif not runtime_oracle_execution.get("valid", False):
        issues.append("runtime_oracle execution is invalid")
    if executed_count != ready_count:
        issues.append(f"runtime_oracle executed cases {executed_count} do not match ready cases {ready_count}")
    if passed_count != ready_count:
        issues.append(f"runtime_oracle passed cases {passed_count} do not match ready cases {ready_count}")
    if failed_count:
        issues.append(f"runtime_oracle execution has {failed_count} failed case(s)")
    return issues


def main() -> int:
    args = _parse_args()
    if args.require_runtime_oracles and not args.run_runtime_oracles:
        emit_error("--require-runtime-oracles requires --run-runtime-oracles")
        return 2
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
            quality = payload.get("quality") or {}
            maintainability = quality.get("maintainability") or {}
            runtime_oracle = payload.get("runtime_oracle") or {}
            runtime_oracle_execution = payload.get("runtime_oracle_execution") or {}
            runtime_oracle_failures = summarize_runtime_oracle_failures(runtime_oracle_execution)
            requirement_issues = (
                runtime_oracle_requirement_issues(runtime_oracle, runtime_oracle_execution)
                if args.require_runtime_oracles
                else []
            )
            success = int(snapshot["exit_code"]) == 0 and not requirement_issues
            if not success:
                failed += 1
            result_entry = {
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
                "runtime_oracle_failure_count": len(runtime_oracle_failures),
                "runtime_oracle_failures": runtime_oracle_failures,
                "runtime_oracle_requirement_issues": requirement_issues,
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
            }
            if not args.summary_only:
                result_entry["payload"] = payload
            results.append(result_entry)
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
