# -*- coding: utf-8 -*-
"""Compare authoring-reduction stages for a .design.md file."""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.append(str(WORKSPACE_ROOT))

from scripts.strip_design_tags import strip_design_tags
from scripts.suggest_design_tags import _build_candidates, _build_messages, _request_http, _sanitize_response
from src.config.config_manager import ConfigManager
from src.design_parser import infer_then_freeze_if_needed
from src.utils.cli_output import emit_error, emit_json_stdout

logging.getLogger("SemanticSearch.structural_memory").setLevel(logging.ERROR)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare authoring-reduction stages for a .design.md file and report deterministic/assisted outcomes as JSON."
    )
    parser.add_argument("--design", required=True, help="Input .design.md path")
    parser.add_argument("--output-dir", help="Output directory for generated probe variants")
    parser.add_argument("--skip-generate", action="store_true", help="Only evaluate inference, not end-to-end generation")
    parser.add_argument("--assist-endpoint-url", help="Optional OpenAI-compatible /v1/chat/completions endpoint")
    parser.add_argument("--assist-model-id", default="qwen2.5-3b-instruct", help="Model id for optional literal assistance")
    parser.add_argument("--assist-timeout-seconds", type=int, default=60, help="Timeout in seconds for optional literal assistance")
    parser.add_argument("--assist-max-new-tokens", type=int, default=384, help="Generation cap for optional literal assistance")
    parser.add_argument(
        "--assist-policy",
        choices=["on_blocked_only", "always"],
        default="on_blocked_only",
        help="When to invoke optional literal assistance during the comparison",
    )
    return parser.parse_args()


def _find_core_logic_range(lines: List[str]) -> Tuple[int, int]:
    start = -1
    end = len(lines)
    for idx, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped.startswith("### core logic"):
            start = idx + 1
            continue
        if start != -1 and idx >= start and (stripped.startswith("## ") or stripped.startswith("### ")):
            end = idx
            break
    return start, end


def _split_line_prefix(line: str) -> Tuple[str, str]:
    value = line.rstrip("\n")
    stripped = value.lstrip()
    prefix_len = len(value) - len(stripped)
    prefix = value[:prefix_len]
    if stripped.startswith("- "):
        return prefix + "- ", stripped[2:].strip()
    i = 0
    while i < len(stripped) and stripped[i].isdigit():
        i += 1
    if i > 0 and i < len(stripped) and stripped[i] == ".":
        if i + 1 < len(stripped) and stripped[i + 1] == " ":
            return prefix + stripped[: i + 2], stripped[i + 2 :].strip()
    return prefix, stripped.strip()


def _find_bracket_end(text: str) -> int:
    in_string = False
    escape = False
    nested_square = 0
    for idx in range(1, len(text)):
        ch = text[idx]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            nested_square += 1
            continue
        if ch == "]":
            if nested_square == 0:
                return idx
            nested_square -= 1
    return -1


def _extract_bracket_prefix(text: str) -> Tuple[str, str]:
    stripped = str(text).lstrip()
    if not stripped.startswith("["):
        return "", text
    end = _find_bracket_end(stripped)
    if end == -1:
        return "", text
    meta = stripped[1:end].strip()
    remainder = stripped[end + 1 :].strip()
    return meta, remainder


def _looks_like_step_meta(meta: str) -> bool:
    if not meta:
        return False
    head = meta.split("|", 1)[0].strip().upper()
    return head in {"ACTION", "CONDITION", "LOOP", "ELSE", "END"}


def _classify_tag(meta: str) -> str:
    lowered = str(meta).lower()
    if lowered.startswith("refs:") or lowered.startswith("depends:"):
        return "refs"
    if lowered.startswith("ops:"):
        return "ops"
    if lowered.startswith("semantic_roles:"):
        return "semantic_roles"
    if lowered.startswith("data_source|"):
        return "data_source"
    if _looks_like_step_meta(meta):
        return "step_meta"
    return ""


def _rewrite_core_logic_line(line: str, removable_tags: set[str]) -> str:
    prefix, remainder = _split_line_prefix(line)
    text = remainder
    while True:
        meta, updated = _extract_bracket_prefix(text)
        if not meta:
            break
        tag_kind = _classify_tag(meta)
        if tag_kind not in removable_tags:
            break
        text = updated
    text = text.strip()
    if not text:
        return ""
    return f"{prefix}{text}"


def _transform_core_logic(content: str, transformer: Callable[[str], str], *, drop_empty: bool = False) -> str:
    lines = content.splitlines()
    start, end = _find_core_logic_range(lines)
    if start == -1:
        return content
    updated: List[str] = []
    for idx, line in enumerate(lines):
        if idx < start or idx >= end:
            updated.append(line)
            continue
        new_line = transformer(line)
        if drop_empty and not new_line.strip():
            continue
        updated.append(new_line)
    return "\n".join(updated) + ("\n" if content.endswith("\n") else "")


def _remove_quoted_literals_from_text(text: str) -> str:
    out: List[str] = []
    in_quote = False
    quote_char = ""
    for ch in str(text):
        if in_quote:
            if ch == quote_char:
                in_quote = False
                quote_char = ""
            continue
        if ch in ["'", '"']:
            in_quote = True
            quote_char = ch
            continue
        out.append(ch)
    return " ".join("".join(out).split())


def _selective_strip(content: str, removable_tags: set[str]) -> str:
    return _transform_core_logic(
        content,
        lambda line: _rewrite_core_logic_line(line, removable_tags),
        drop_empty=True,
    )


def _variant_original(content: str) -> str:
    return content


def _variant_drop_step_meta(content: str) -> str:
    return _selective_strip(content, {"step_meta"})


def _variant_drop_step_meta_refs(content: str) -> str:
    return _selective_strip(content, {"step_meta", "refs"})


def _variant_drop_step_meta_refs_ops(content: str) -> str:
    return _selective_strip(content, {"step_meta", "refs", "ops"})


def _variant_strip_tags_keep_literals(content: str) -> str:
    return strip_design_tags(content)


def _variant_strip_tags_drop_literals(content: str) -> str:
    stripped = strip_design_tags(content)
    return _transform_core_logic(
        stripped,
        lambda line: (_split_line_prefix(line)[0] + _remove_quoted_literals_from_text(_split_line_prefix(line)[1])).rstrip(),
        drop_empty=True,
    )


VARIANTS: List[Dict[str, object]] = [
    {
        "name": "original",
        "description": "Explicit authoring baseline with full tags",
        "expectation": "deterministic_baseline",
        "transform": _variant_original,
    },
    {
        "name": "drop_step_meta",
        "description": "Remove step_meta first while keeping refs/ops/literal roles",
        "expectation": "should_usually_remain_deterministic",
        "transform": _variant_drop_step_meta,
    },
    {
        "name": "drop_step_meta_refs",
        "description": "Remove step_meta and refs while keeping ops/literal roles",
        "expectation": "deterministic_if_dependency_meaning_is_still_clear",
        "transform": _variant_drop_step_meta_refs,
    },
    {
        "name": "drop_step_meta_refs_ops",
        "description": "Remove step_meta, refs, and ops while keeping explicit literal roles",
        "expectation": "last_preferred_deterministic_reduction_stage",
        "transform": _variant_drop_step_meta_refs_ops,
    },
    {
        "name": "strip_tags_keep_literals",
        "description": "Remove explicit tags and rely on natural language plus surviving literals",
        "expectation": "literal_boundary_candidate",
        "transform": _variant_strip_tags_keep_literals,
    },
    {
        "name": "strip_tags_drop_literals",
        "description": "Remove explicit tags and also remove quoted literal anchors",
        "expectation": "expected_blocked_boundary",
        "transform": _variant_strip_tags_drop_literals,
    },
]


def _module_basename(design_path: Path) -> str:
    name = design_path.name
    if name.endswith(".design.md"):
        return name[:-10]
    return design_path.stem


def _run_generation(design_path: Path, output_path: Path, assist_args: Optional[List[str]]) -> Dict[str, object]:
    command = [
        sys.executable,
        "scripts/generate/generate_from_design.py",
        "--design",
        str(design_path),
        "--output",
        str(output_path),
    ]
    if assist_args:
        command.extend(assist_args)
    completed = subprocess.run(
        command,
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "generated": completed.returncode == 0 and output_path.exists(),
        "clean_generate": completed.returncode == 0 and output_path.exists() and not completed.stderr.strip(),
    }


def _is_no_candidate_blocked(result: Dict[str, object]) -> bool:
    if result.get("status") != "blocked":
        return False
    issues = result.get("issues", [])
    if not isinstance(issues, list):
        return False
    for item in issues:
        if isinstance(item, dict) and str(item.get("reason") or "").strip().upper() == "NO_CANDIDATE":
            return True
    return False


def _build_assist_payload(design_path: Path, args: argparse.Namespace) -> Optional[Dict[str, object]]:
    parsed, candidates = _build_candidates(design_path)
    if not candidates:
        return None
    request_args = argparse.Namespace(
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


def _evaluate_inference(
    design_path: Path,
    *,
    config_manager: ConfigManager,
    assist_payload: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    result = infer_then_freeze_if_needed(
        str(design_path),
        config_manager=config_manager,
        suggestion_payload=assist_payload,
    )
    inferred_path = str(result.get("output_path") or "")
    return {
        "status": result.get("status"),
        "message": result.get("message"),
        "issues": result.get("issues", []),
        "output_path": inferred_path,
        "output_exists": bool(inferred_path) and Path(inferred_path).exists(),
    }


def _build_assist_args(args: argparse.Namespace) -> Optional[List[str]]:
    if not args.assist_endpoint_url:
        return None
    return [
        "--assist-literal-tags-http",
        "--assist-endpoint-url",
        args.assist_endpoint_url,
        "--assist-model-id",
        args.assist_model_id,
        "--assist-timeout-seconds",
        str(args.assist_timeout_seconds),
        "--assist-max-new-tokens",
        str(args.assist_max_new_tokens),
        "--assist-policy",
        args.assist_policy,
    ]


def _assisted_inference(
    design_path: Path,
    args: argparse.Namespace,
    *,
    config_manager: ConfigManager,
) -> Dict[str, object]:
    if not args.assist_endpoint_url:
        return {}
    payload = None
    deterministic = _evaluate_inference(design_path, config_manager=config_manager)
    if args.assist_policy == "always":
        payload = _build_assist_payload(design_path, args)
        assisted = _evaluate_inference(design_path, config_manager=config_manager, assist_payload=payload)
    elif _is_no_candidate_blocked(deterministic):
        payload = _build_assist_payload(design_path, args)
        assisted = _evaluate_inference(design_path, config_manager=config_manager, assist_payload=payload)
    else:
        assisted = deterministic
    accepted = 0
    rejected = 0
    if payload:
        result = payload.get("result", {}) if isinstance(payload, dict) else {}
        accepted = len(result.get("accepted_suggestions", [])) if isinstance(result, dict) else 0
        rejected = len(result.get("rejected_suggestions", [])) if isinstance(result, dict) else 0
    return {
        "policy": args.assist_policy,
        "accepted_suggestions": accepted,
        "rejected_suggestions": rejected,
        "inference": assisted,
    }


def collect_probe_payload(args: argparse.Namespace) -> Dict[str, object]:
    design_path = Path(args.design)
    config_manager = ConfigManager()
    assist_args = _build_assist_args(args)
    results: List[Dict[str, object]] = []
    content = design_path.read_text(encoding="utf-8")
    probe_root = Path(args.output_dir) if args.output_dir else WORKSPACE_ROOT / "cache" / f"{design_path.stem}.authoring_reduction_probe"
    if probe_root.exists():
        shutil.rmtree(probe_root)
    probe_root.mkdir(parents=True, exist_ok=True)

    for variant in VARIANTS:
        variant_name = str(variant["name"])
        variant_dir = probe_root / variant_name
        variant_dir.mkdir(parents=True, exist_ok=True)
        variant_design = variant_dir / design_path.name
        variant_output = variant_dir / f"{_module_basename(design_path)}.cs"
        transformed = variant["transform"](content)
        variant_design.write_text(transformed, encoding="utf-8")

        deterministic_inference = _evaluate_inference(variant_design, config_manager=config_manager)
        deterministic_generation: Dict[str, object] = {}
        if not args.skip_generate:
            deterministic_generation = _run_generation(variant_design, variant_output, assist_args=None)

        assisted: Dict[str, object] = {}
        assisted_generation: Dict[str, object] = {}
        if args.assist_endpoint_url:
            assisted = _assisted_inference(variant_design, args, config_manager=config_manager)
            if not args.skip_generate:
                assisted_output = variant_dir / f"{_module_basename(design_path)}.assist.cs"
                assisted_generation = _run_generation(variant_design, assisted_output, assist_args=assist_args)

        results.append(
            {
                "variant": variant_name,
                "description": variant["description"],
                "expectation": variant["expectation"],
                "design_path": str(variant_design),
                "deterministic": {
                    "inference": deterministic_inference,
                    "generation": deterministic_generation,
                },
                "assisted": {
                    **assisted,
                    "generation": assisted_generation,
                } if args.assist_endpoint_url else None,
            }
        )

    return {
        "design": str(design_path),
        "probe_root": str(probe_root),
        "skip_generate": args.skip_generate,
        "assist_configured": bool(args.assist_endpoint_url),
        "assist_policy": args.assist_policy if args.assist_endpoint_url else None,
        "variants": results,
    }


def main() -> int:
    args = _parse_args()
    design_path = Path(args.design)
    if not design_path.is_file():
        emit_error(f"design file not found: {design_path}")
        return 1

    emit_json_stdout(collect_probe_payload(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
