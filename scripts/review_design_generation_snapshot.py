# -*- coding: utf-8 -*-
"""Review a design as original spec, inferred spec, and generated code in one snapshot."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.suggest_design_tags import _build_candidates, _build_messages, _request_http, _sanitize_response
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.code_synthesis.method_store import MethodStore
from src.code_synthesis.synthesis_pipeline import synthesize_structured_spec
from src.code_verification.compilation_verifier import CompilationVerifier
from src.config.config_manager import ConfigManager
from src.design_parser import StructuredDesignParser, infer_then_freeze_if_needed, validate_structured_spec_or_raise
from src.replanner.replanner import Replanner
from src.utils.cli_output import emit_error, emit_json_stdout
from src.utils.nuget_client import NuGetClient
from src.utils.spec_auditor import SpecAuditor
from src.vector_engine.vector_engine import VectorEngine


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emit a review snapshot containing original design, inferred design, generated code, and audit results."
    )
    parser.add_argument("--design", required=True, help="Input .design.md path")
    parser.add_argument("--output-dir", help="Optional output directory for inferred design and generated code snapshot")
    parser.add_argument("--retry", action="store_true", help="Enable replanner retry loop")
    parser.add_argument("--allow-fallback", action="store_true", help="Allow fallback synthesis pass")
    parser.add_argument("--assist-endpoint-url", help="Optional OpenAI-compatible /v1/chat/completions endpoint")
    parser.add_argument("--assist-model-id", default="qwen2.5-3b-instruct", help="Model id for optional literal assistance")
    parser.add_argument("--assist-timeout-seconds", type=int, default=60, help="Timeout in seconds for optional literal assistance")
    parser.add_argument("--assist-max-new-tokens", type=int, default=384, help="Generation cap for optional literal assistance")
    parser.add_argument(
        "--assist-policy",
        choices=["on_blocked_only", "always"],
        default="on_blocked_only",
        help="When to invoke optional literal assistance",
    )
    return parser.parse_args()


def _build_literal_assist_payload(design_path: Path, args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    if not args.assist_endpoint_url:
        return None
    parsed, candidates = _build_candidates(design_path)
    if not candidates:
        return None
    request_args = SimpleNamespace(
        endpoint_url=args.assist_endpoint_url,
        model_id=args.assist_model_id,
        timeout_seconds=args.assist_timeout_seconds,
        max_new_tokens=args.assist_max_new_tokens,
    )
    messages = _build_messages(parsed, candidates, "literal_roles_only")
    response_payload = _request_http(request_args, messages)
    sanitized = _sanitize_response(parsed, candidates, response_payload, "literal_roles_only")
    return {
        "provider": "openai_compatible_http",
        "model_id": args.assist_model_id,
        "endpoint_url": args.assist_endpoint_url,
        "mode": "literal_roles_only",
        "result": sanitized,
    }


def _is_no_candidate_blocked(inference_result: Dict[str, Any]) -> bool:
    if inference_result.get("status") != "blocked":
        return False
    issues = inference_result.get("issues", [])
    if not isinstance(issues, list):
        return False
    return any(
        isinstance(item, dict) and str(item.get("reason") or "").strip().upper() == "NO_CANDIDATE"
        for item in issues
    )


def _run_inference(design_path: Path, args: argparse.Namespace, config: ConfigManager, vector_engine) -> Dict[str, Any]:
    suggestion_payload = None
    if args.assist_endpoint_url and args.assist_policy == "always":
        suggestion_payload = _build_literal_assist_payload(design_path, args)
    inference_result = infer_then_freeze_if_needed(
        str(design_path),
        config_manager=config,
        vector_engine=vector_engine,
        suggestion_payload=suggestion_payload,
    )
    if args.assist_endpoint_url and args.assist_policy == "on_blocked_only" and _is_no_candidate_blocked(inference_result):
        suggestion_payload = _build_literal_assist_payload(design_path, args)
        inference_result = infer_then_freeze_if_needed(
            str(design_path),
            config_manager=config,
            vector_engine=vector_engine,
            suggestion_payload=suggestion_payload,
        )
    accepted = 0
    rejected = 0
    if suggestion_payload:
        result = suggestion_payload.get("result", {}) if isinstance(suggestion_payload, dict) else {}
        accepted = len(result.get("accepted_suggestions", [])) if isinstance(result, dict) else 0
        rejected = len(result.get("rejected_suggestions", [])) if isinstance(result, dict) else 0
    return {
        "inference_result": inference_result,
        "assist_summary": {
            "configured": bool(args.assist_endpoint_url),
            "policy": args.assist_policy if args.assist_endpoint_url else None,
            "accepted_suggestions": accepted,
            "rejected_suggestions": rejected,
        },
    }


def build_review_snapshot(args: argparse.Namespace) -> Dict[str, Any]:
    design_path = Path(args.design)
    config = ConfigManager()
    vector_engine = VectorEngine()
    method_store = MethodStore(config, vector_engine=vector_engine)
    synthesizer = CodeSynthesizer(config, method_store=method_store)
    parser = StructuredDesignParser(knowledge_base=synthesizer.ukb)
    verifier = CompilationVerifier(config)
    replanner = Replanner(config)
    nuget_client = NuGetClient(config)
    spec_auditor = SpecAuditor(knowledge_base=synthesizer.ukb)

    inference_bundle = _run_inference(design_path, args, config, vector_engine)
    inference_result = inference_bundle["inference_result"]
    if inference_result.get("status") == "blocked":
        return {
            "exit_code": 1,
            "payload": {
                "design": str(design_path),
                "original_design_text": design_path.read_text(encoding="utf-8"),
                "inference": inference_result,
                "assist": inference_bundle["assist_summary"],
                "generated": None,
            },
        }

    inferred_design_path = Path(str(inference_result.get("output_path") or design_path))
    spec = parser.parse_design_file(str(inferred_design_path))
    validate_structured_spec_or_raise(spec)
    module_name = spec.get("module_name", design_path.stem)
    result = synthesize_structured_spec(
        synthesizer,
        spec,
        module_name,
        return_trace=True,
        verifier=verifier,
        replanner=replanner,
        spec_auditor=spec_auditor,
        nuget_client=nuget_client,
        allow_retry=args.retry,
        allow_fallback=args.allow_fallback,
        max_retries=3,
    )
    if result.get("status") == "FAILED":
        return {
            "exit_code": 1,
            "payload": {
                "design": str(design_path),
                "original_design_text": design_path.read_text(encoding="utf-8"),
                "inference": inference_result,
                "assist": inference_bundle["assist_summary"],
                "synthesis": {"status": "FAILED", "code": result.get("code")},
                "generated": None,
            },
        }

    output_dir = Path(args.output_dir) if args.output_dir else (WORKSPACE_ROOT / "cache" / f"{module_name}.review_snapshot")
    output_dir.mkdir(parents=True, exist_ok=True)
    inferred_copy_path = output_dir / inferred_design_path.name
    generated_code_path = output_dir / f"{module_name}.cs"
    inferred_text = inferred_design_path.read_text(encoding="utf-8")
    generated_code = str(result.get("code") or "")
    inferred_copy_path.write_text(inferred_text, encoding="utf-8")
    generated_code_path.write_text(generated_code, encoding="utf-8")

    trace = result.get("trace", {}) if isinstance(result.get("trace"), dict) else {}
    return {
        "exit_code": 0,
        "payload": {
            "design": str(design_path),
            "module_name": module_name,
            "original_design_text": design_path.read_text(encoding="utf-8"),
            "inference": inference_result,
            "assist": inference_bundle["assist_summary"],
            "inferred_design_path": str(inferred_copy_path),
            "inferred_design_text": inferred_text,
            "generated_code_path": str(generated_code_path),
            "generated_code": generated_code,
            "spec_issues": result.get("spec_issues", []),
            "verification": result.get("verification", {}),
            "resolved_dependencies": result.get("resolved_dependencies", []),
            "trace_summary": {
                "has_ir_tree": isinstance(trace.get("ir_tree"), dict),
                "has_best_path": isinstance(trace.get("best_path"), dict),
                "has_blueprint": isinstance(trace.get("blueprint"), dict),
            },
        },
    }


def main() -> int:
    args = _parse_args()
    design_path = Path(args.design)
    if not design_path.is_file():
        emit_error(f"design file not found: {design_path}")
        return 1
    snapshot = build_review_snapshot(args)
    emit_json_stdout(snapshot["payload"])
    return int(snapshot["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
