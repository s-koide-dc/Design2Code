# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.strip_design_tags import strip_design_tags
from scripts.suggest_design_tags import (
    DEFAULT_MODEL_ID,
    _build_candidates,
    _build_messages,
    _request_http,
    _sanitize_response,
)
from src.utils.cli_output import emit_error, emit_json_stdout


DEFAULT_CASES = [
    {
        "id": "complex_linq_path",
        "design": "scenarios/ComplexLinqSearch.design.md",
        "variant": "strip_tags",
        "expected_accepts": [
            {
                "step_number": 1,
                "semantic_roles": {"path": "users.json"},
            }
        ],
    },
    {
        "id": "sync_http_and_sql",
        "design": "scenarios/SyncExternalData.design.md",
        "variant": "strip_tags",
        "expected_accepts": [
            {
                "step_number": 1,
                "semantic_roles": {"url": "https://api.example.com/products"},
            },
            {
                "step_number": 3,
                "semantic_roles": {"sql": "INSERT INTO Products (Name, Price) VALUES (@Name, @Price)"},
            },
        ],
    },
    {
        "id": "daily_inventory_sync",
        "design": "scenarios/DailyInventorySync.design.md",
        "variant": "strip_tags",
        "expected_accepts": [
            {
                "step_number": 3,
                "semantic_roles": {"url": "https://inventory.example.com/api/current"},
            },
            {
                "step_number": 5,
                "semantic_roles": {"sql": "UPDATE Inventory SET Stock = @Stock WHERE Id = @Id"},
            },
        ],
    },
    {
        "id": "user_report_sql_and_path",
        "design": "scenarios/UserReportGenerator.design.md",
        "variant": "strip_tags",
        "expected_accepts": [
            {
                "step_number": 3,
                "semantic_roles": {"sql": "SELECT * FROM Users"},
            },
            {
                "step_number": 6,
                "semantic_roles": {"path": "report.txt"},
            },
        ],
    },
    {
        "id": "fetch_product_inventory_sql",
        "design": "scenarios/FetchProductInventory.design.md",
        "variant": "strip_tags",
        "expected_accepts": [
            {
                "step_number": 2,
                "semantic_roles": {"sql": "SELECT * FROM Inventory"},
            }
        ],
    },
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect LLM-based design-tag suggestion quality on fixed cases."
    )
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
        default="literal_roles_only",
        help="Suggestion mode used for the quality probe.",
    )
    return parser.parse_args()


def _prepare_variant(case: dict, cache_root: Path) -> Path:
    source_path = WORKSPACE_ROOT / str(case["design"])
    if not source_path.is_file():
        raise FileNotFoundError(f"design file not found: {source_path}")
    content = source_path.read_text(encoding="utf-8")
    if case.get("variant") == "strip_tags":
        content = strip_design_tags(content)
    case_dir = cache_root / str(case["id"])
    case_dir.mkdir(parents=True, exist_ok=True)
    out_path = case_dir / source_path.name
    out_path.write_text(content, encoding="utf-8")
    return out_path


def _matches_expected(suggestion: dict, expected: dict) -> bool:
    if suggestion.get("step_number") != expected.get("step_number"):
        return False
    expected_step_meta = expected.get("step_meta")
    if expected_step_meta is not None and suggestion.get("step_meta") != expected_step_meta:
        return False
    expected_roles = expected.get("semantic_roles", {})
    actual_roles = suggestion.get("semantic_roles", {}) or {}
    for key, value in expected_roles.items():
        if actual_roles.get(key) != value:
            return False
    return True


def _evaluate_case(args: argparse.Namespace, case: dict, cache_root: Path) -> dict:
    design_path = _prepare_variant(case, cache_root)
    parsed, candidates = _build_candidates(design_path)
    if not candidates:
        return {
            "id": case["id"],
            "design": str(design_path),
            "candidate_count": 0,
            "accepted_suggestions": [],
            "rejected_suggestions": [],
            "expected_accepts": case.get("expected_accepts", []),
            "matched_expected": [],
            "missing_expected": case.get("expected_accepts", []),
        }
    messages = _build_messages(parsed, candidates, args.mode)
    response_payload = _request_http(args, messages)
    sanitized = _sanitize_response(parsed, candidates, response_payload, args.mode)
    accepted = sanitized.get("accepted_suggestions", [])
    matched_expected = []
    missing_expected = []
    for expected in case.get("expected_accepts", []):
        if any(_matches_expected(item, expected) for item in accepted):
            matched_expected.append(expected)
        else:
            missing_expected.append(expected)
    return {
        "id": case["id"],
        "design": str(design_path),
        "candidate_count": sanitized.get("candidate_count", 0),
        "accepted_suggestions": accepted,
        "rejected_suggestions": sanitized.get("rejected_suggestions", []),
        "expected_accepts": case.get("expected_accepts", []),
        "matched_expected": matched_expected,
        "missing_expected": missing_expected,
    }


def _count_expected_roles(items: list[dict]) -> dict[str, int]:
    counts = {"path": 0, "url": 0, "sql": 0}
    for item in items:
        roles = item.get("semantic_roles", {}) or {}
        for key in counts:
            if key in roles:
                counts[key] += 1
    return counts


def main() -> int:
    args = _parse_args()
    cache_root = WORKSPACE_ROOT / "cache" / "design_tag_suggestion_quality"
    if cache_root.exists():
        shutil.rmtree(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)
    try:
        results = [_evaluate_case(args, case, cache_root) for case in DEFAULT_CASES]
    except (FileNotFoundError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        emit_error(str(exc))
        return 1

    summary = {
        "total_cases": len(results),
        "all_expected_found": sum(1 for item in results if not item["missing_expected"]),
        "cases_with_missing_expected": sum(1 for item in results if item["missing_expected"]),
        "total_accepted_suggestions": sum(len(item["accepted_suggestions"]) for item in results),
        "total_rejected_suggestions": sum(len(item["rejected_suggestions"]) for item in results),
        "expected_role_totals": {
            key: sum(_count_expected_roles(item["expected_accepts"])[key] for item in results)
            for key in ["path", "url", "sql"]
        },
        "matched_role_totals": {
            key: sum(_count_expected_roles(item["matched_expected"])[key] for item in results)
            for key in ["path", "url", "sql"]
        },
    }
    emit_json_stdout(
        {
            "provider": args.provider,
            "model_id": args.model_id,
            "endpoint_url": args.endpoint_url,
            "mode": args.mode,
            "summary": summary,
            "results": results,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
