"""Review whether a design is ready for supported generation without mutating it."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.design_parser import StructuredDesignParser, validate_structured_spec
from src.utils.design_doc_parser import DesignDocParser
from src.design_parser.inference_line_syntax import strip_leading_numbering
from src.design_parser.compact_step_expander import expand_compact_steps
from src.utils.cli_output import emit_json_stdout
from scripts.validate.validate_generation_failure_cases import DEFAULT_REGISTRY as DEFAULT_FAILURE_REGISTRY

_KINDS = {"ACTION", "CONDITION", "LOOP", "ELSE", "END"}


def _has_explicit_step_metadata(line: str) -> bool:
    text = strip_leading_numbering(line)
    if not text.startswith("["):
        return False
    closing = text.find("]")
    if closing < 0:
        return False
    fields = [field.strip() for field in text[1:closing].split("|")]
    if not fields or fields[0] not in _KINDS:
        return False
    if fields[0] in {"ELSE", "END"}:
        return len(fields) >= 1
    return len(fields) >= 5 and all(fields[index] for index in range(5))


def _load_open_failure_guidance() -> dict[str, list[dict[str, str]]]:
    try:
        payload = json.loads(DEFAULT_FAILURE_REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    guidance: dict[str, list[dict[str, str]]] = {}
    for case in payload.get("cases", []):
        if not isinstance(case, dict) or case.get("status") != "open":
            continue
        reason = case.get("reason")
        if not isinstance(reason, str):
            continue
        guidance.setdefault(reason, []).append({
            "case_id": str(case.get("case_id") or ""),
            "guidance": str(case.get("guidance") or ""),
        })
    return guidance


def review_design(design_path: Path) -> dict[str, Any]:
    path = design_path.resolve()
    if ROOT not in path.parents or not path.is_file():
        return {"status": "error", "message": "design path must be an existing file inside this workspace"}
    content = path.read_text(encoding="utf-8")
    content, compact_errors = expand_compact_steps(content)
    if compact_errors:
        return {
            "status": "blocked",
            "design": path.relative_to(ROOT).as_posix(),
            "issues": [
                {
                    "step_index": error.line_number,
                    "reason": "COMPACT_STEP_INVALID",
                    "detail": error.detail,
                    "known_failure_cases": [],
                }
                for error in compact_errors
            ],
        }
    parsed = DesignDocParser().parse_content(content)
    specification = parsed.get("specification") if isinstance(parsed, dict) else {}
    core_logic = specification.get("core_logic") if isinstance(specification, dict) else []
    issues: list[dict[str, Any]] = []
    for step_index, line in enumerate(core_logic if isinstance(core_logic, list) else [], start=1):
        text = str(line)
        if text.strip().startswith("[data_source|") or "[data_source|" in text:
            continue
        if not _has_explicit_step_metadata(text):
            issues.append({
                "step_index": step_index,
                "reason": "MISSING_EXPLICIT_STEP_METADATA",
                "detail": "Supported generation requires [KIND|INTENT|TARGET|OUTPUT|EFFECT].",
            })
    if not issues:
        try:
            spec = StructuredDesignParser().parse_markdown(content)
            for detail in validate_structured_spec(spec):
                issues.append({"step_index": None, "reason": "SPECIFICATION_VALIDATION_FAILED", "detail": detail})
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append({"step_index": None, "reason": "SPECIFICATION_VALIDATION_FAILED", "detail": str(exc)})
    guidance = _load_open_failure_guidance()
    for issue in issues:
        issue["known_failure_cases"] = guidance.get(issue["reason"], [])
    return {
        "status": "ready" if not issues else "blocked",
        "design": path.relative_to(ROOT).as_posix(),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review supported-generation readiness for a design document.")
    parser.add_argument("--design", required=True, type=Path)
    args = parser.parse_args()
    result = review_design(args.design)
    emit_json_stdout(result)
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
