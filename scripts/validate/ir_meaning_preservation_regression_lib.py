from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = PROJECT_ROOT / "research" / "ir_meaning_preservation"
RESULTS_ROOT = RESEARCH_ROOT / "results"
TEMPLATES_ROOT = PROJECT_ROOT / "research" / "templates"
DOCS_ROOT = PROJECT_ROOT / "docs"

ADMISSION_STATE_NORMALIZATION = {
    "Admit Now": "admitted",
    "Hold For Evidence": "not admitted",
    "Reject": "not admitted",
}


def parse_markdown_table_rows(table_path: Path) -> list[dict[str, str]]:
    lines = table_path.read_text(encoding="utf-8").splitlines()
    table_lines = [line for line in lines if line.strip().startswith("|")]
    if len(table_lines) < 3:
        return []

    headers = [cell.strip() for cell in table_lines[0].strip().strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for raw_line in table_lines[2:]:
        cells = [cell.strip() for cell in raw_line.strip().strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def parse_sections(content: str) -> dict[str, str]:
    lines = content.splitlines()
    sections: dict[str, list[str]] = {}
    current_heading: str | None = None

    for line in lines:
        if line.startswith("## "):
            current_heading = line.strip()
            sections[current_heading] = []
            continue
        if current_heading is not None:
            sections[current_heading].append(line)

    return {heading: "\n".join(body).strip() for heading, body in sections.items()}


def collect_backtick_paths(text: str) -> list[str]:
    return re.findall(r"`([^`]+)`", text)


def extract_labeled_block(section_text: str, label: str) -> str:
    lines = section_text.splitlines()
    capture = False
    collected: list[str] = []

    for line in lines:
        if line.startswith(label):
            capture = True
            remainder = line[len(label):].strip()
            if remainder:
                collected.append(remainder)
            continue

        if capture and line.startswith("- **"):
            break

        if capture:
            collected.append(line)

    return "\n".join(collected).strip()


def parse_bulleted_backtick_values(block_text: str) -> list[str]:
    values: list[str] = []
    for line in block_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        values.extend(collect_backtick_paths(stripped))
    return values


def parse_bulleted_lines(block_text: str) -> list[str]:
    values: list[str] = []
    for line in block_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        values.append(stripped[1:].strip())
    return values


def normalize_admission_state(raw_state: str) -> str:
    return ADMISSION_STATE_NORMALIZATION.get(raw_state, raw_state)


def resolve_reference(raw_path: str, run_file: Path) -> Path:
    normalized = Path(raw_path.replace("/", "\\"))
    if normalized.is_absolute():
        return normalized

    project_candidate = PROJECT_ROOT / normalized
    if project_candidate.exists():
        return project_candidate

    theme_candidate = RESEARCH_ROOT / normalized
    if theme_candidate.exists():
        return theme_candidate

    return run_file.parent / normalized


def extract_run_record_targets(run_file: Path) -> tuple[list[str], tuple[str, str] | None]:
    sections = parse_sections(run_file.read_text(encoding="utf-8"))

    role_block = extract_labeled_block(
        sections.get("## 3. Role Weakening Check", ""),
        "- **Affected `spec_role` values**:",
    )
    roles = parse_bulleted_backtick_values(role_block)

    alias_section = sections.get("## 4. Alias Admission Check", "")
    timing_roots = parse_bulleted_backtick_values(
        extract_labeled_block(alias_section, "- **Timing root**:")
    )
    admission_states = parse_bulleted_backtick_values(
        extract_labeled_block(alias_section, "- **Admission state**:")
    )

    alias_target: tuple[str, str] | None = None
    if timing_roots and admission_states:
        alias_target = (timing_roots[0], normalize_admission_state(admission_states[0]))

    return roles, alias_target


def extract_run_record_draft_inputs(run_file: Path) -> dict[str, list[str] | str]:
    sections = parse_sections(run_file.read_text(encoding="utf-8"))

    change_summary = sections.get("## 1. Change Summary", "")
    affected_claims = sections.get("## 2. Affected Claims", "")
    benchmark_coverage = sections.get("## 5. Benchmark Coverage", "")
    downstream_conservatism = sections.get("## 6. Downstream Conservatism Check", "")
    output_path = sections.get("## 8. Output Path Check", "")
    deliverables = sections.get("## 9. Deliverables Produced", "")

    changed_areas = parse_bulleted_backtick_values(
        extract_labeled_block(change_summary, "- **Changed Area**:")
    )
    related_files = parse_bulleted_backtick_values(
        extract_labeled_block(change_summary, "- **Related Files**:")
    )
    why_change = extract_labeled_block(change_summary, "- **Why This Change Was Made**:")

    existing_cases = parse_bulleted_lines(
        extract_labeled_block(benchmark_coverage, "- **Existing cases used**:")
    )
    new_contrast = extract_labeled_block(
        benchmark_coverage, "- **New contrast case added?**:"
    )
    observed_updates = parse_bulleted_lines(
        extract_labeled_block(benchmark_coverage, "- **Observed IR files updated**:")
    )
    results_updates = parse_bulleted_lines(
        extract_labeled_block(benchmark_coverage, "- **Results tables updated**:")
    )

    primary_claim = extract_labeled_block(affected_claims, "- **Primary Claim**:")
    secondary_claims = parse_bulleted_lines(
        extract_labeled_block(affected_claims, "- **Secondary Claims**:")
    )
    claim_map_refs = parse_bulleted_backtick_values(
        extract_labeled_block(affected_claims, "- **Claim Map References**:")
    )

    affected_consumers = parse_bulleted_backtick_values(
        extract_labeled_block(downstream_conservatism, "- **Affected consumers**:")
    )
    stronger_concretization = extract_labeled_block(
        downstream_conservatism, "- **Expected stronger concretization**:"
    )
    weaker_fallback = extract_labeled_block(
        downstream_conservatism, "- **Expected weaker/generic fallback**:"
    )
    todo_stop_points = extract_labeled_block(
        downstream_conservatism, "- **TODO stop points introduced or removed**:"
    )

    touched_output_modules = parse_bulleted_lines(
        extract_labeled_block(output_path, "- **Touched modules with output-path changes**:")
    )
    output_classifications = parse_bulleted_backtick_values(
        extract_labeled_block(
            output_path,
            "- **Output classification checked against `docs/stdout_output_policy.md`**:",
        )
    )
    design_updates = extract_labeled_block(
        output_path, "- **Source-level `.design.md` updated for output-path changes**:"
    )
    raw_print_status = extract_labeled_block(
        output_path, "- **Any new raw `print` introduced?**:"
    )

    deliverable_lines = [
        line.strip()
        for line in deliverables.splitlines()
        if line.strip().startswith("- [")
    ]

    return {
        "changed_areas": changed_areas,
        "related_files": related_files,
        "why_change": why_change,
        "primary_claim": primary_claim,
        "secondary_claims": secondary_claims,
        "claim_map_refs": claim_map_refs,
        "existing_cases": existing_cases,
        "new_contrast": new_contrast,
        "observed_updates": observed_updates,
        "results_updates": results_updates,
        "affected_consumers": affected_consumers,
        "stronger_concretization": stronger_concretization,
        "weaker_fallback": weaker_fallback,
        "todo_stop_points": todo_stop_points,
        "touched_output_modules": touched_output_modules,
        "output_classifications": output_classifications,
        "design_updates": design_updates,
        "raw_print_status": raw_print_status,
        "deliverable_lines": deliverable_lines,
    }


def load_role_regression_rows() -> list[dict[str, str]]:
    return parse_markdown_table_rows(RESULTS_ROOT / "role_weakening_regression_table.md")


def load_alias_regression_rows() -> list[dict[str, str]]:
    return parse_markdown_table_rows(RESULTS_ROOT / "schema_alias_admission_regression_table.md")
