# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.design_parser.design_inference import DesignInferenceEngine
from src.utils.cli_output import emit_error, emit_json_stdout
from src.utils.design_doc_parser import DesignDocParser
from src.utils.text_parser import extract_first_quoted_literal, extract_urls

DEFAULT_MODEL_ID = "qwen2.5-3b-instruct"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ask a local LLM for design-tag suggestions and return stdout-only JSON."
    )
    parser.add_argument("--design", required=True, help="Input .design.md path")
    parser.add_argument(
        "--provider",
        choices=["openai_compatible_http"],
        default="openai_compatible_http",
        help="Backend provider for tag suggestion.",
    )
    parser.add_argument(
        "--endpoint-url",
        help="OpenAI compatible /v1/chat/completions endpoint.",
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help="Model id for the selected backend.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=20,
        help="Backend timeout in seconds.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=512,
        help="Generation cap for the backend.",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "literal_roles_only"],
        default="full",
        help="Suggestion mode. literal_roles_only limits output to explicit path/url/sql semantic_roles.",
    )
    return parser.parse_args()


def _has_refs(line: str) -> bool:
    return "[refs:" in str(line) or "[depends:" in str(line)


def _has_semantic_roles(line: str) -> bool:
    return "[semantic_roles:" in str(line)


def _likely_filename_literal(line: str) -> str:
    literal = extract_first_quoted_literal(line)
    if not literal:
        return ""
    value = str(literal).strip()
    if not value:
        return ""
    if "." not in value and "/" not in value and "\\" not in value:
        return ""
    return value


def _strip_visible_list_prefix(line: str) -> str:
    value = str(line).lstrip()
    head, sep, tail = value.partition(". ")
    if sep and head.isdigit() and tail.strip():
        return tail.strip()
    return value


def _build_candidates(design_path: Path) -> tuple[dict, list[dict]]:
    parser = DesignDocParser()
    engine = DesignInferenceEngine()
    content = design_path.read_text(encoding="utf-8")
    parsed = parser.parse_content(content)
    spec = parsed.get("specification", {}) if isinstance(parsed, dict) else {}
    core_logic = spec.get("core_logic", []) if isinstance(spec, dict) else []
    candidates = []
    step_idx = 0
    for raw in core_logic:
        line = str(raw)
        if engine._resolve_data_source_tag(line):
            continue
        step_idx += 1
        missing_components = []
        if not engine._has_explicit_step_meta(line):
            missing_components.append("step_meta")
        if step_idx > 1 and not _has_refs(line):
            missing_components.append("refs")
        if not _has_semantic_roles(line):
            if extract_urls(line) or engine._extract_sql_literal(line) or _likely_filename_literal(line):
                missing_components.append("semantic_roles")
        if not missing_components:
            continue
        candidates.append(
            {
                "step_number": step_idx,
                "original_line": line,
                "missing_components": missing_components,
                "has_explicit_literal_signal": bool(
                    extract_urls(line) or engine._extract_sql_literal(line) or _likely_filename_literal(line)
                ),
            }
        )
    priority_candidates = [item for item in candidates if item.get("has_explicit_literal_signal")]
    if priority_candidates:
        return parsed, priority_candidates
    return parsed, candidates


def _build_messages(parsed: dict, candidates: list[dict], mode: str) -> list[dict]:
    compact_candidates = [
        {
            "step_number": item["step_number"],
            "line_text": _strip_visible_list_prefix(item["original_line"]),
            "missing_components": item["missing_components"],
        }
        for item in candidates
    ]
    if mode == "literal_roles_only":
        prompt = {
            "module_name": parsed.get("module_name"),
            "purpose": parsed.get("purpose"),
            "mode": mode,
            "candidates": compact_candidates,
            "rules": [
                "Return JSON only.",
                "Return exactly one top-level object: {\"suggestions\": [...]}",
                "Do not repeat the input payload.",
                "Do not invent path/url/sql literals.",
                "Use the provided step_number exactly as-is. Do not renumber candidates from the visible list text.",
                "Only return suggestions when a literal path/url/sql is explicit in the original line.",
                "When the original line contains SQL '...', copy that exact SQL string into semantic_roles.sql.",
                "When the original line contains URL '...' or https://..., copy that exact URL into semantic_roles.url.",
                "When the original line contains a quoted filename like 'users.json', copy that exact filename into semantic_roles.path.",
                "If a step has no confident literal tag improvement, omit it from suggestions.",
                "semantic_roles must be a JSON object.",
                "Only use semantic_roles keys from: path, url, sql.",
            ],
            "allowed_fields": ["step_number", "semantic_roles", "notes"],
            "example": {
                "suggestions": [
                    {
                        "step_number": 1,
                        "semantic_roles": {"path": "users.json"}
                    },
                    {
                        "step_number": 2,
                        "semantic_roles": {"url": "https://api.example.com/products"}
                    },
                    {
                        "step_number": 3,
                        "semantic_roles": {"sql": "INSERT INTO Products (Name, Price) VALUES (@Name, @Price)"}
                    }
                ]
            },
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are assisting with deterministic .design.md tagging. "
                    "Return JSON only. Never invent path/url/sql literals that do not already appear in the original line. "
                    "Use the provided step_number exactly as given, even when the visible source line starts with a different number. "
                    "Only suggest semantic_roles for explicit literal-bearing candidates. "
                    "If the line says SQL '...', return that exact SQL in semantic_roles.sql. "
                    "If the line says URL '...' or contains https://..., return that exact URL in semantic_roles.url. "
                    "If the line says a quoted filename like 'users.json', return that exact filename in semantic_roles.path. "
                    "Do not output step_meta or refs in this mode. "
                    "If a candidate has no confident literal tag improvement, omit it entirely."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt, ensure_ascii=False, indent=2),
            },
        ]
    prompt = {
        "module_name": parsed.get("module_name"),
        "purpose": parsed.get("purpose"),
        "mode": mode,
        "candidates": compact_candidates,
        "rules": [
            "Return JSON only.",
            "Return exactly one top-level object: {\"suggestions\": [...]}",
            "Do not repeat the input payload.",
            "Do not invent path/url/sql literals.",
            "If a step has no confident improvement, omit it from suggestions.",
            "refs must be a JSON string array.",
            "semantic_roles must be a JSON object.",
        ],
        "allowed_fields": ["step_number", "step_meta", "refs", "semantic_roles", "notes"],
        "example": {
            "suggestions": [
                {
                    "step_number": 1,
                    "step_meta": "ACTION|FETCH|string|string|IO",
                    "refs": [],
                    "semantic_roles": {"path": "users.json"},
                    "notes": "optional"
                }
            ]
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "You are assisting with deterministic .design.md tagging. "
                "Return JSON only. Never invent path/url/sql literals that do not already appear in the original line. "
                "Do not add prose outside JSON."
                " Prioritize explicit literal-bearing candidates only."
                " If a candidate has no confident tag improvement, omit it entirely."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(prompt, ensure_ascii=False, indent=2),
        },
    ]


def _request_http(args: argparse.Namespace, messages: list[dict]) -> dict:
    if not args.endpoint_url:
        raise ValueError("--endpoint-url is required for openai_compatible_http")
    body = {
        "model": args.model_id,
        "messages": messages,
        "temperature": 0,
        "max_tokens": args.max_new_tokens,
        "stream": False,
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request_obj = urllib_request.Request(
        args.endpoint_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request_obj, timeout=args.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except (urllib_error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(str(exc)) from exc
    response_json = json.loads(raw)
    choices = response_json.get("choices", [])
    if not choices:
        raise RuntimeError("backend returned no choices")
    message = choices[0].get("message", {})
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("backend returned empty content")
    return json.loads(content)


def _validate_literal_fields(
    engine: DesignInferenceEngine, candidate_map: dict[int, dict], suggestion: dict, mode: str
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    step_number = suggestion.get("step_number")
    candidate = candidate_map.get(step_number)
    if not candidate:
        return False, ["unknown_step_number"]
    original_line = str(candidate.get("original_line") or "")
    missing_components = candidate.get("missing_components") or []
    has_explicit_literal_signal = bool(candidate.get("has_explicit_literal_signal"))
    semantic_roles = suggestion.get("semantic_roles")
    if semantic_roles is not None and not isinstance(semantic_roles, dict):
        reasons.append("semantic_roles_must_be_object")
        return False, reasons
    semantic_roles = semantic_roles or {}

    path_val = semantic_roles.get("path")
    if path_val is not None:
        literal_path = _likely_filename_literal(original_line)
        if not isinstance(path_val, str) or path_val.strip() != literal_path:
            reasons.append("path_literal_not_explicit_in_original_line")

    url_val = semantic_roles.get("url")
    if url_val is not None:
        urls = extract_urls(original_line)
        if not isinstance(url_val, str) or url_val.strip() not in urls:
            reasons.append("url_literal_not_explicit_in_original_line")

    sql_val = semantic_roles.get("sql")
    if sql_val is not None:
        sql_literal = engine._extract_sql_literal(original_line)
        if not isinstance(sql_val, str) or sql_val.strip() != sql_literal:
            reasons.append("sql_literal_not_explicit_in_original_line")

    refs = suggestion.get("refs")
    step_meta = suggestion.get("step_meta")
    if mode == "literal_roles_only":
        if refs is not None:
            reasons.append("refs_not_allowed_in_literal_roles_only")
        if step_meta is not None:
            reasons.append("step_meta_not_allowed_in_literal_roles_only")
    else:
        if refs is not None:
            if not isinstance(refs, list) or any(not isinstance(item, str) for item in refs):
                reasons.append("refs_must_be_string_list")
            elif any(not str(item).startswith("step_") for item in refs):
                reasons.append("refs_must_use_step_ids")

        if step_meta is not None and not isinstance(step_meta, str):
            reasons.append("step_meta_must_be_string")
        elif isinstance(step_meta, str) and step_meta.strip():
            parts = [part.strip() for part in step_meta.split("|")]
            if len(parts) < 5:
                reasons.append("step_meta_must_have_at_least_5_pipe_fields")

    has_step_meta = isinstance(step_meta, str) and bool(step_meta.strip())
    has_refs = isinstance(refs, list) and len(refs) > 0
    has_roles = isinstance(semantic_roles, dict) and len(semantic_roles) > 0
    if not has_step_meta and not has_refs and not has_roles:
        reasons.append("noop_suggestion")
    if "semantic_roles" in missing_components and has_explicit_literal_signal:
        if not any(key in semantic_roles for key in ["path", "url", "sql"]):
            reasons.append("literal_candidate_requires_path_or_url_or_sql")

    return len(reasons) == 0, reasons


def _sanitize_response(parsed: dict, candidates: list[dict], response_payload: dict, mode: str) -> dict:
    engine = DesignInferenceEngine()
    candidate_map = {int(item["step_number"]): item for item in candidates}
    raw_suggestions = response_payload.get("suggestions", [])
    if not isinstance(raw_suggestions, list):
        raise ValueError("backend response must contain suggestions[]")

    accepted = []
    rejected = []
    for item in raw_suggestions:
        if not isinstance(item, dict):
            rejected.append({"raw": item, "reasons": ["suggestion_must_be_object"]})
            continue
        accepted_flag, reasons = _validate_literal_fields(engine, candidate_map, item, mode)
        normalized = {
            "step_number": item.get("step_number"),
            "step_meta": item.get("step_meta"),
            "refs": item.get("refs", []),
            "semantic_roles": item.get("semantic_roles", {}),
            "notes": item.get("notes", ""),
        }
        if accepted_flag:
            accepted.append(normalized)
        else:
            rejected.append({"suggestion": normalized, "reasons": reasons})

    return {
        "module_name": parsed.get("module_name"),
        "purpose": parsed.get("purpose"),
        "mode": mode,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "accepted_suggestions": accepted,
        "rejected_suggestions": rejected,
    }


def main() -> int:
    args = _parse_args()
    design_path = Path(args.design)
    if not design_path.is_file():
        emit_error(f"design file not found: {design_path}")
        return 1
    try:
        parsed, candidates = _build_candidates(design_path)
        if candidates:
            messages = _build_messages(parsed, candidates, args.mode)
            backend_payload = _request_http(args, messages)
            payload = _sanitize_response(parsed, candidates, backend_payload, args.mode)
        else:
            payload = {
                "module_name": parsed.get("module_name"),
                "purpose": parsed.get("purpose"),
                "mode": args.mode,
                "candidate_count": 0,
                "candidates": [],
                "accepted_suggestions": [],
                "rejected_suggestions": [],
            }
    except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
        emit_error(str(exc))
        return 1

    emit_json_stdout(
        {
            "provider": args.provider,
            "model_id": args.model_id,
            "endpoint_url": args.endpoint_url,
            "mode": args.mode,
            "design": str(design_path),
            "result": payload,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
