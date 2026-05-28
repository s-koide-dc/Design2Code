from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.cli_output import emit_error, emit_progress
from scripts.validate.ir_meaning_preservation_regression_lib import (
    DOCS_ROOT,
    RESEARCH_ROOT,
    RESULTS_ROOT,
    TEMPLATES_ROOT,
    collect_backtick_paths,
    extract_labeled_block,
    extract_run_record_targets,
    load_alias_regression_rows,
    load_role_regression_rows,
    parse_sections,
    resolve_reference,
)


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    message: str


SCRIPTS_ROOT = PROJECT_ROOT / "scripts"

EXPECTED_SECTIONS = [
    "## 1. Change Summary",
    "## 2. Affected Claims",
    "## 3. Role Weakening Check",
    "## 4. Alias Admission Check",
    "## 5. Benchmark Coverage",
    "## 6. Downstream Conservatism Check",
    "## 7. Validation Run",
    "## 8. Output Path Check",
    "## 9. Deliverables Produced",
    "## 10. Final Judgment",
]

SECTION_LABELS = {
    "## 1. Change Summary": [
        "- **Date**:",
        "- **Changed Area**:",
        "- **Related Files**:",
        "- **Why This Change Was Made**:",
    ],
    "## 2. Affected Claims": [
        "- **Primary Claim**:",
        "- **Secondary Claims**:",
        "- **Claim Map References**:",
    ],
    "## 3. Role Weakening Check": [
        "- **Affected `spec_role` values**:",
        "- **Expected runtime impact**:",
        "- **Role weakening risk**:",
        "- **Expected IR fields that must remain stable**:",
        "- **Expected IR fields that may change**:",
        "- **Runtime fields that must not weaken**:",
    ],
    "## 4. Alias Admission Check": [
        "- **Alias touched**:",
        "- **Admission state**:",
        "- **Timing root**:",
        "- **Why this root applies**:",
        "- **Coverage tier**:",
    ],
    "## 5. Benchmark Coverage": [
        "- **Existing cases used**:",
        "- **New contrast case added?**:",
        "- **Observed IR files updated**:",
        "- **Results tables updated**:",
    ],
    "## 6. Downstream Conservatism Check": [
        "- **Affected consumers**:",
        "- **Expected stronger concretization**:",
        "- **Expected weaker/generic fallback**:",
        "- **TODO stop points introduced or removed**:",
    ],
    "## 7. Validation Run": [
        "- **regression_runner**:",
        "- **sync_project_map**:",
        "- **project_consistency**:",
        "- **regression_run_validator**:",
        "- **unit/integration tests**:",
        "- **other checks**:",
    ],
    "## 8. Output Path Check": [
        "- **Touched modules with output-path changes**:",
        "- **Output classification checked against `docs/stdout_output_policy.md`**:",
        "- **Source-level `.design.md` updated for output-path changes**:",
        "- **Any new raw `print` introduced?**:",
    ],
    "## 10. Final Judgment": [
        "- **Regression status**:",
        "- **Open risks**:",
        "- **Next action**:",
    ],
}

REQUIRED_ASSETS = [
    RESEARCH_ROOT / "combined_regression_playbook.md",
    RESEARCH_ROOT / "schema_alias_role_weakening_regression_checklist.md",
    RESEARCH_ROOT / "claim_evidence_implementation_map.md",
    RESEARCH_ROOT / "implementation_priority_from_claims.md",
    RESULTS_ROOT / "role_weakening_regression_table.md",
    RESULTS_ROOT / "schema_alias_admission_regression_table.md",
    RESULTS_ROOT / "schema_alias_admission_status_table.md",
    TEMPLATES_ROOT / "ir_meaning_preservation_regression_run_template.md",
    DOCS_ROOT / "stdout_output_policy.md",
    SCRIPTS_ROOT / "sync_project_map.py",
    SCRIPTS_ROOT / "validate_project_consistency.py",
]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate IR meaning-preservation regression run records."
    )
    parser.add_argument(
        "--run-file",
        type=Path,
        help="Path to a specific regression run markdown file. Defaults to the latest file in results/ matching regression_run_*.md.",
    )
    return parser.parse_args()


def choose_run_file(explicit_path: Path | None) -> Path:
    if explicit_path:
        return (PROJECT_ROOT / explicit_path).resolve() if not explicit_path.is_absolute() else explicit_path

    candidates = sorted(RESULTS_ROOT.glob("regression_run_*.md"))
    if not candidates:
        raise FileNotFoundError("No regression_run_*.md file found under research/ir_meaning_preservation/results.")
    return candidates[-1]

def validate_required_assets(issues: list[ValidationIssue]) -> None:
    for asset in REQUIRED_ASSETS:
        if not asset.exists():
            issues.append(ValidationIssue("ERROR", f"Required asset is missing: {asset.relative_to(PROJECT_ROOT)}"))

def validate_regression_table_links(run_file: Path, issues: list[ValidationIssue]) -> None:
    role_rows = load_role_regression_rows()
    alias_rows = load_alias_regression_rows()

    known_roles = {
        row["`spec_role`"].strip().strip("`")
        for row in role_rows
        if "`spec_role`" in row
    }
    alias_pairs = {
        (
            row["Timing Root"].strip().strip("`"),
            row["Admission State"].strip().strip("`"),
        )
        for row in alias_rows
        if "Timing Root" in row and "Admission State" in row
    }

    roles, alias_target = extract_run_record_targets(run_file)
    for role in roles:
        if role not in known_roles:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    f"Affected spec_role '{role}' is not present in results/role_weakening_regression_table.md",
                )
            )

    if alias_target is not None:
        if alias_target not in alias_pairs:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "Alias Admission Check does not match any "
                    "`Timing Root` + `Admission State` row in results/schema_alias_admission_regression_table.md: "
                    f"{alias_target[0]} / {alias_target[1]}",
                )
            )


def validate_sections(run_file: Path, content: str, issues: list[ValidationIssue]) -> dict[str, str]:
    sections = parse_sections(content)

    for expected_heading in EXPECTED_SECTIONS:
        if expected_heading not in sections:
            issues.append(ValidationIssue("ERROR", f"Missing section: '{expected_heading}'"))

    for heading, labels in SECTION_LABELS.items():
        if heading not in sections:
            continue
        section_text = sections[heading]
        for label in labels:
            if label not in section_text:
                issues.append(
                    ValidationIssue("ERROR", f"Section '{heading}' is missing required label '{label}'")
                )

    validation_section = sections.get("## 7. Validation Run", "")
    if "run_ir_meaning_preservation_regression.py" not in validation_section:
        issues.append(ValidationIssue("ERROR", "Validation Run does not record regression runner execution."))
    if "sync_project_map.py" not in validation_section:
        issues.append(ValidationIssue("ERROR", "Validation Run does not record sync_project_map execution."))
    if "validate_project_consistency.py" not in validation_section:
        issues.append(ValidationIssue("ERROR", "Validation Run does not record project consistency validation."))

    output_section = sections.get("## 8. Output Path Check", "")
    for expected_classification in [
        "`Formal CLI stdout`",
        "`Formal CLI stderr`",
        "`debug_print`",
        "`logger`",
    ]:
        if expected_classification not in output_section:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    f"Output Path Check must enumerate the output classification '{expected_classification}'.",
                )
            )

    deliverables_section = sections.get("## 9. Deliverables Produced", "")
    for deliverable in [
        "benchmark case updated",
        "observed IR updated",
        "results observation updated",
        "claim/evidence map updated",
        "changelog updated",
    ]:
        if deliverable not in deliverables_section:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    f"Deliverables Produced must include checkbox item '{deliverable}'.",
                )
            )

    if "- [x] changelog updated" not in deliverables_section:
        issues.append(ValidationIssue("ERROR", "Deliverables Produced must mark 'changelog updated' as completed."))

    if "- [x]" not in deliverables_section:
        issues.append(ValidationIssue("ERROR", "Deliverables Produced must mark at least one completed deliverable."))

    related_files_block = extract_labeled_block(
        sections.get("## 1. Change Summary", ""),
        "- **Related Files**:",
    )
    for raw_path in collect_backtick_paths(related_files_block):
        resolved = resolve_reference(raw_path, run_file)
        if not resolved.exists():
            issues.append(
                ValidationIssue(
                    "ERROR",
                    f"Related file reference does not resolve: '{raw_path}' from {run_file.relative_to(PROJECT_ROOT)}",
                )
            )

    claim_refs_block = extract_labeled_block(
        sections.get("## 2. Affected Claims", ""),
        "- **Claim Map References**:",
    )
    for raw_path in collect_backtick_paths(claim_refs_block):
        resolved = resolve_reference(raw_path, run_file)
        if not resolved.exists():
            issues.append(
                ValidationIssue(
                    "ERROR",
                    f"Claim reference does not resolve: '{raw_path}' from {run_file.relative_to(PROJECT_ROOT)}",
                )
            )

    validate_regression_table_links(run_file, issues)

    return sections


def main() -> int:
    args = parse_args()
    issues: list[ValidationIssue] = []

    try:
        run_file = choose_run_file(args.run_file)
    except FileNotFoundError as exc:
        emit_error(f"ERROR: {exc}")
        return 1

    if not run_file.exists():
        emit_error(f"ERROR: Run file not found: {run_file}")
        return 1

    validate_required_assets(issues)

    content = run_file.read_text(encoding="utf-8")
    validate_sections(run_file, content, issues)

    emit_progress("--- IR Meaning Preservation Regression Validation ---")
    emit_progress(f"Run file: {run_file.relative_to(PROJECT_ROOT)}")

    if not issues:
        emit_progress("OK: Regression run record is structurally consistent.")
        return 0

    errors = [issue for issue in issues if issue.severity == "ERROR"]
    warnings = [issue for issue in issues if issue.severity == "WARNING"]

    if errors:
        emit_error("\nERRORS (must be fixed):")
        for issue in errors:
            emit_error(f" - {issue.message}")

    if warnings:
        emit_error("\nWARNINGS (should be reviewed):")
        for issue in warnings:
            emit_error(f" - {issue.message}")

    emit_error("\n--- End of Validation ---")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
