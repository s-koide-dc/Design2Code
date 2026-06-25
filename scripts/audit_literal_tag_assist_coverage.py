# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.strip_design_tags import strip_design_tags
from scripts.suggest_design_tags import _build_candidates, _likely_filename_literal
from src.design_parser.design_inference import DesignInferenceEngine
from src.design_parser import infer_then_freeze_if_needed
from src.utils.cli_output import emit_error, emit_json_stdout
from src.utils.text_parser import extract_urls

logging.getLogger("SemanticSearch.structural_memory").setLevel(logging.ERROR)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit which stripped design scenarios are good candidates for literal tag assistance."
    )
    parser.add_argument(
        "--scenarios-dir",
        default=str(WORKSPACE_ROOT / "scenarios"),
        help="Directory containing .design.md scenarios.",
    )
    return parser.parse_args()


def _is_design_scenario(path: Path) -> bool:
    name = path.name
    return name.endswith(".design.md") and not name.endswith(".inferred.design.md")


def _audit_design(design_path: Path, cache_root: Path) -> dict:
    stripped_path = cache_root / design_path.name
    stripped_path.write_text(strip_design_tags(design_path.read_text(encoding="utf-8")), encoding="utf-8")
    inference_result = infer_then_freeze_if_needed(str(stripped_path))
    _, candidates = _build_candidates(stripped_path)
    candidate_steps = []
    role_candidate_totals = {"path": 0, "url": 0, "sql": 0}
    engine = DesignInferenceEngine()
    for item in candidates:
        line = str(item.get("original_line") or "")
        roles = []
        urls = extract_urls(line)
        if urls:
            roles.append("url")
        if engine._extract_sql_literal(line):
            roles.append("sql")
        if _likely_filename_literal(line) and not urls:
            roles.append("path")
        for role in roles:
            role_candidate_totals[role] += 1
        candidate_steps.append(
            {
                "step_number": item.get("step_number"),
                "missing_components": item.get("missing_components", []),
                "has_explicit_literal_signal": bool(item.get("has_explicit_literal_signal")),
                "line": line,
                "literal_role_hints": roles,
            }
        )
    issues = inference_result.get("issues", []) if isinstance(inference_result, dict) else []
    blocked_no_candidate = (
        inference_result.get("status") == "blocked"
        and any(str(issue.get("reason") or "").strip().upper() == "NO_CANDIDATE" for issue in issues if isinstance(issue, dict))
    )
    assist_recommended = blocked_no_candidate and any(bool(item.get("has_explicit_literal_signal")) for item in candidates)
    return {
        "design": str(design_path),
        "stripped_design": str(stripped_path),
        "inference_status": inference_result.get("status"),
        "issues": issues,
        "candidate_count": len(candidates),
        "candidate_steps": candidate_steps,
        "role_candidate_totals": role_candidate_totals,
        "blocked_no_candidate": blocked_no_candidate,
        "assist_recommended": assist_recommended,
    }


def main() -> int:
    args = _parse_args()
    scenarios_dir = Path(args.scenarios_dir)
    if not scenarios_dir.is_dir():
        emit_error(f"scenarios dir not found: {scenarios_dir}")
        return 1

    cache_root = WORKSPACE_ROOT / "cache" / "literal_tag_assist_coverage"
    if cache_root.exists():
        shutil.rmtree(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)

    try:
        designs = sorted(path for path in scenarios_dir.glob("*.design.md") if _is_design_scenario(path))
        results = [_audit_design(path, cache_root) for path in designs]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        emit_error(str(exc))
        return 1

    summary = {
        "total_designs": len(results),
        "blocked_no_candidate": sum(1 for item in results if item["blocked_no_candidate"]),
        "assist_recommended": sum(1 for item in results if item["assist_recommended"]),
        "role_candidate_totals": {
            key: sum(int(item["role_candidate_totals"].get(key, 0)) for item in results)
            for key in ["path", "url", "sql"]
        },
    }
    emit_json_stdout(
        {
            "scenarios_dir": str(scenarios_dir),
            "summary": summary,
            "results": results,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
