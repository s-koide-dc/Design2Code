# -*- coding: utf-8 -*-
"""Validate whether a new .design.md stays within the current authoring boundary."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.probe_design_authoring_reduction import collect_probe_payload
from src.utils.cli_output import emit_error, emit_json_stdout


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that a .design.md draft stays within the current deterministic/assisted authoring boundary."
    )
    parser.add_argument("--design", required=True, help="Input .design.md path")
    parser.add_argument("--output-dir", help="Optional output directory for probe artifacts")
    parser.add_argument("--assist-endpoint-url", help="Optional OpenAI-compatible /v1/chat/completions endpoint")
    parser.add_argument("--assist-model-id", default="qwen2.5-3b-instruct", help="Model id for optional literal assistance")
    parser.add_argument("--assist-timeout-seconds", type=int, default=60, help="Timeout in seconds for optional literal assistance")
    parser.add_argument("--assist-max-new-tokens", type=int, default=384, help="Generation cap for optional literal assistance")
    parser.add_argument(
        "--assist-policy",
        choices=["on_blocked_only", "always"],
        default="on_blocked_only",
        help="When to invoke optional literal assistance during validation",
    )
    return parser.parse_args()


def _variant_map(payload: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    variants = payload.get("variants", [])
    result: Dict[str, Dict[str, object]] = {}
    if isinstance(variants, list):
        for item in variants:
            if isinstance(item, dict):
                result[str(item.get("variant"))] = item
    return result


def _inference_status(variant_payload: Dict[str, object], *, assisted: bool = False) -> str:
    section = variant_payload.get("assisted") if assisted else variant_payload.get("deterministic")
    if not isinstance(section, dict):
        return ""
    inference = section.get("inference")
    if isinstance(inference, dict):
        return str(inference.get("status") or "")
    return ""


def _is_no_candidate_block(variant_payload: Dict[str, object], *, assisted: bool = False) -> bool:
    section = variant_payload.get("assisted") if assisted else variant_payload.get("deterministic")
    if not isinstance(section, dict):
        return False
    inference = section.get("inference")
    if not isinstance(inference, dict):
        return False
    issues = inference.get("issues", [])
    if not isinstance(issues, list):
        return False
    for item in issues:
        if isinstance(item, dict) and str(item.get("reason") or "").strip().upper() == "NO_CANDIDATE":
            return True
    return False


def _validate(payload: Dict[str, object]) -> Dict[str, object]:
    variants = _variant_map(payload)
    failures: List[str] = []
    observations: List[str] = []

    required_deterministic = [
        "original",
        "drop_step_meta",
        "drop_step_meta_refs",
        "drop_step_meta_refs_ops",
    ]
    for name in required_deterministic:
        item = variants.get(name)
        if not item:
            failures.append(f"missing_variant:{name}")
            continue
        status = _inference_status(item)
        if status not in {"no_change", "updated"}:
            failures.append(f"deterministic_variant_failed:{name}:{status or 'unknown'}")

    forbidden_boundary = variants.get("strip_tags_drop_literals")
    if not forbidden_boundary:
        failures.append("missing_variant:strip_tags_drop_literals")
    else:
        if not _is_no_candidate_block(forbidden_boundary):
            status = _inference_status(forbidden_boundary)
            failures.append(f"forbidden_boundary_not_blocked:strip_tags_drop_literals:{status or 'unknown'}")

    assisted_boundary = variants.get("strip_tags_keep_literals")
    if assisted_boundary:
        status = _inference_status(assisted_boundary)
        if status in {"no_change", "updated"}:
            observations.append("strip_tags_keep_literals remained deterministic")
        elif _is_no_candidate_block(assisted_boundary):
            observations.append("strip_tags_keep_literals hit literal boundary under deterministic inference")
        else:
            failures.append(f"strip_tags_keep_literals_unexpected:{status or 'unknown'}")

        assisted_section = assisted_boundary.get("assisted")
        if isinstance(assisted_section, dict):
            assisted_status = _inference_status(assisted_boundary, assisted=True)
            accepted = assisted_section.get("accepted_suggestions", 0)
            if accepted:
                observations.append(f"strip_tags_keep_literals assist accepted={accepted}")
            if assisted_status in {"no_change", "updated"} and _is_no_candidate_block(assisted_boundary):
                observations.append("strip_tags_keep_literals recovered with assist")

    return {
        "ok": len(failures) == 0,
        "failures": failures,
        "observations": observations,
    }


def main() -> int:
    args = _parse_args()
    design_path = Path(args.design)
    if not design_path.is_file():
        emit_error(f"design file not found: {design_path}")
        return 1

    probe_args = argparse.Namespace(
        design=args.design,
        output_dir=args.output_dir,
        skip_generate=True,
        assist_endpoint_url=args.assist_endpoint_url,
        assist_model_id=args.assist_model_id,
        assist_timeout_seconds=args.assist_timeout_seconds,
        assist_max_new_tokens=args.assist_max_new_tokens,
        assist_policy=args.assist_policy,
    )
    payload = collect_probe_payload(probe_args)
    validation = _validate(payload)
    emit_json_stdout(
        {
            "design": payload.get("design"),
            "probe_root": payload.get("probe_root"),
            "assist_configured": payload.get("assist_configured"),
            "assist_policy": payload.get("assist_policy"),
            "validation": validation,
            "variants": payload.get("variants"),
        }
    )
    return 0 if validation.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
