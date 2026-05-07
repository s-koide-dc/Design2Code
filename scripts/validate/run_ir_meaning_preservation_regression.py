from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validate.ir_meaning_preservation_regression_lib import (
    extract_run_record_draft_inputs,
    extract_run_record_targets,
    load_alias_regression_rows,
    load_role_regression_rows,
)

TEST_SUITES = {
    "none": [],
    "ir-generator": [
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.unit.test_ir_generator",
        ]
    ],
    "binder": [
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.unit.test_semantic_binder_logic",
        ]
    ],
    "synthesizer": [
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.unit.test_code_synthesizer_integration",
        ]
    ],
    "ir-core": [
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.unit.test_ir_generator",
            "tests.unit.test_semantic_binder_logic",
            "tests.unit.test_code_synthesizer_integration",
        ]
    ],
}


@dataclass(frozen=True)
class StepResult:
    name: str
    command: list[str]
    return_code: int
    stdout: str
    stderr: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the standard IR meaning-preservation regression workflow."
    )
    parser.add_argument(
        "--run-file",
        required=True,
        type=Path,
        help="Regression run markdown file to validate.",
    )
    parser.add_argument(
        "--test-suite",
        default="none",
        choices=sorted(TEST_SUITES.keys()),
        help="Predefined test suite to run after the mandatory validators.",
    )
    return parser.parse_args()


def resolve_run_file(raw_path: Path) -> Path:
    return raw_path if raw_path.is_absolute() else (PROJECT_ROOT / raw_path).resolve()


def build_steps(run_file: Path, test_suite: str) -> list[tuple[str, list[str]]]:
    steps: list[tuple[str, list[str]]] = [
        (
            "sync_project_map",
            [sys.executable, "scripts/sync_project_map.py"],
        ),
        (
            "project_consistency",
            [sys.executable, "scripts/validate_project_consistency.py"],
        ),
        (
            "regression_run_validator",
            [
                sys.executable,
                "scripts/validate/validate_ir_meaning_preservation_regression.py",
                "--run-file",
                str(run_file.relative_to(PROJECT_ROOT)),
            ],
        ),
    ]

    for command in TEST_SUITES[test_suite]:
        steps.append(("test_suite", command))

    return steps


def run_step(name: str, command: list[str]) -> StepResult:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="" if completed.stderr.endswith("\n") else "\n")
    return StepResult(
        name=name,
        command=command,
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def display_command(command: list[str]) -> str:
    if not command:
        return ""

    rendered: list[str] = []
    for index, part in enumerate(command):
        if index == 0 and Path(part).name.lower().startswith("python"):
            rendered.append("python")
        else:
            rendered.append(part.replace("\\", "/"))
    return " ".join(rendered)


def summarize_output(result: StepResult) -> str:
    combined = "\n".join(
        part.strip() for part in [result.stdout, result.stderr] if part and part.strip()
    ).strip()
    if not combined:
        return "実行済み"

    lines = [line.strip() for line in combined.splitlines() if line.strip()]

    if result.name == "sync_project_map":
        for line in reversed(lines):
            if "Synchronization complete." in line:
                return "`Synchronization complete.`"
    elif result.name == "project_consistency":
        for line in reversed(lines):
            if "OK: All checks passed. Project is consistent." in line:
                return "`OK: All checks passed. Project is consistent.`"
    elif result.name == "regression_run_validator":
        for line in reversed(lines):
            if "OK: Regression run record is structurally consistent." in line:
                return "`OK: Regression run record is structurally consistent.`"
    elif result.name == "test_suite":
        for index, line in enumerate(lines):
            if line.startswith("Ran ") and index + 1 < len(lines):
                return f"`{line}` / `{lines[index + 1]}`"
        for line in reversed(lines):
            if line == "OK":
                return "`OK`"

    return f"`{lines[-1]}`"


def normalize_draft_line(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("- "):
        return stripped[2:].strip()
    return stripped


def collect_regression_checks(run_file: Path) -> tuple[list[tuple[str, str]], tuple[str, str] | None]:
    roles, alias_target = extract_run_record_targets(run_file)
    role_rows = load_role_regression_rows()
    alias_rows = load_alias_regression_rows()

    role_checks: list[tuple[str, str]] = []
    for role in roles:
        for row in role_rows:
            row_role = row.get("`spec_role`", "").strip().strip("`")
            if row_role == role:
                role_checks.append((role, row.get("Regression Check", "").strip()))
                break

    alias_check: tuple[str, str] | None = None
    if alias_target is not None:
        timing_root, admission_state = alias_target
        for row in alias_rows:
            row_timing = row.get("Timing Root", "").strip().strip("`")
            row_state = row.get("Admission State", "").strip().strip("`")
            if row_timing == timing_root and row_state == admission_state:
                alias_check = (
                    f"{timing_root} / {admission_state}",
                    row.get("Regression Check", "").strip(),
                )
                break

    return role_checks, alias_check


def print_regression_checks(run_file: Path) -> None:
    role_checks, alias_check = collect_regression_checks(run_file)
    print("\n--- Relevant Regression Checks ---")

    if role_checks:
        print("Role-side:")
        for role, check in role_checks:
            print(f"- {role}: {check}")
    else:
        print("Role-side:")
        print("- none")

    print("Alias-side:")
    if alias_check is None:
        print("- none")
        return

    label, check = alias_check
    print(f"- {label}: {check}")


def print_check_draft_snippet(run_file: Path) -> None:
    role_checks, alias_check = collect_regression_checks(run_file)
    roles, alias_target = extract_run_record_targets(run_file)

    print("\n--- Paste-Ready Check Draft ---")
    print("```md")
    print("## 3. Role Weakening Check")
    print("")
    print("- **Affected `spec_role` values**:")
    if roles:
        for role in roles:
            print(f"  - `{role}`")
    else:
        print("  - `none`")
    print("- **Expected runtime impact**:")
    print("- **Role weakening risk**:")
    print("")
    print("### Before / After Expectation")
    print("")
    print("- **Expected IR fields that must remain stable**:")
    print("- **Expected IR fields that may change**:")
    print("- **Runtime fields that must not weaken**:")
    if role_checks:
        for role, check in role_checks:
            print(f"  - `{role}`: {check}")

    print("")
    print("## 4. Alias Admission Check")
    print("")
    print("- **Alias touched**:")
    print("- **Admission state**:")
    if alias_target is not None:
        raw_state = "Admit Now" if alias_target[1] == "admitted" else "Hold For Evidence / Reject"
        print(f"  - `{raw_state}`")
    print("- **Timing root**:")
    if alias_target is not None:
        print(f"  - `{alias_target[0]}`")
    print("- **Why this root applies**:")
    print("- **Coverage tier**:")
    if alias_check is not None:
        label, check = alias_check
        print(f"- **Regression Check Reference**: `{label}` -> {check}")
    print("```")


def print_summary_draft_snippet(run_file: Path) -> None:
    draft = extract_run_record_draft_inputs(run_file)

    print("\n--- Paste-Ready Summary Draft ---")
    print("```md")
    print("## 1. Change Summary")
    print("")
    print("- **Date**:")
    print("- **Changed Area**:")
    changed_areas = draft["changed_areas"]
    if isinstance(changed_areas, list) and changed_areas:
        for area in changed_areas:
            print(f"  - `{area}`")
    else:
        print("  - `none`")
    print("- **Related Files**:")
    related_files = draft["related_files"]
    if isinstance(related_files, list) and related_files:
        for file_path in related_files:
            print(f"  - `{file_path}`")
    else:
        print("  - `none`")
    print("- **Why This Change Was Made**:")
    why_change = draft["why_change"]
    if isinstance(why_change, str) and why_change:
        for line in why_change.splitlines():
            normalized = normalize_draft_line(line)
            if normalized:
                print(f"  - {normalized}")
    print("")
    print("## 5. Benchmark Coverage")
    print("")
    print("- **Existing cases used**:")
    existing_cases = draft["existing_cases"]
    if isinstance(existing_cases, list) and existing_cases:
        for case_line in existing_cases:
            print(f"  - {case_line}")
    else:
        print("  - なし")
    print("- **New contrast case added?**:")
    new_contrast = draft["new_contrast"]
    if isinstance(new_contrast, str) and new_contrast:
        print(f"  - {normalize_draft_line(new_contrast)}")
    print("- **Observed IR files updated**:")
    observed_updates = draft["observed_updates"]
    if isinstance(observed_updates, list) and observed_updates:
        for item in observed_updates:
            print(f"  - {item}")
    else:
        print("  - なし")
    print("- **Results tables updated**:")
    results_updates = draft["results_updates"]
    if isinstance(results_updates, list) and results_updates:
        for item in results_updates:
            print(f"  - {item}")
    else:
        print("  - なし")
    print("```")


def print_claims_and_downstream_draft_snippet(run_file: Path) -> None:
    draft = extract_run_record_draft_inputs(run_file)

    print("\n--- Paste-Ready Claims / Downstream Draft ---")
    print("```md")
    print("## 2. Affected Claims")
    print("")
    print("- **Primary Claim**:")
    primary_claim = draft["primary_claim"]
    if isinstance(primary_claim, str) and primary_claim:
        for line in primary_claim.splitlines():
            normalized = normalize_draft_line(line)
            if normalized:
                print(f"  - {normalized}")
    print("- **Secondary Claims**:")
    secondary_claims = draft["secondary_claims"]
    if isinstance(secondary_claims, list) and secondary_claims:
        for claim in secondary_claims:
            print(f"  - {claim}")
    print("- **Claim Map References**:")
    claim_map_refs = draft["claim_map_refs"]
    if isinstance(claim_map_refs, list) and claim_map_refs:
        for ref in claim_map_refs:
            print(f"  - `{ref}`")

    print("")
    print("## 6. Downstream Conservatism Check")
    print("")
    print("- **Affected consumers**:")
    affected_consumers = draft["affected_consumers"]
    if isinstance(affected_consumers, list) and affected_consumers:
        for consumer in affected_consumers:
            print(f"  - `{consumer}`")
    else:
        print("  - `none`")
    print("- **Expected stronger concretization**:")
    stronger_concretization = draft["stronger_concretization"]
    if isinstance(stronger_concretization, str) and stronger_concretization:
        for line in stronger_concretization.splitlines():
            normalized = normalize_draft_line(line)
            if normalized:
                print(f"  - {normalized}")
    print("- **Expected weaker/generic fallback**:")
    weaker_fallback = draft["weaker_fallback"]
    if isinstance(weaker_fallback, str) and weaker_fallback:
        for line in weaker_fallback.splitlines():
            normalized = normalize_draft_line(line)
            if normalized:
                print(f"  - {normalized}")
    print("- **TODO stop points introduced or removed**:")
    todo_stop_points = draft["todo_stop_points"]
    if isinstance(todo_stop_points, str) and todo_stop_points:
        for line in todo_stop_points.splitlines():
            normalized = normalize_draft_line(line)
            if normalized:
                print(f"  - {normalized}")
    print("```")


def print_output_and_deliverables_draft_snippet(run_file: Path) -> None:
    draft = extract_run_record_draft_inputs(run_file)

    print("\n--- Paste-Ready Output / Deliverables Draft ---")
    print("```md")
    print("## 8. Output Path Check")
    print("")
    print("- **Touched modules with output-path changes**:")
    touched_output_modules = draft["touched_output_modules"]
    if isinstance(touched_output_modules, list) and touched_output_modules:
        for item in touched_output_modules:
            print(f"  - {item}")
    else:
        print("  - なし")
    print("- **Output classification checked against `docs/stdout_output_policy.md`**:")
    output_classifications = draft["output_classifications"]
    if isinstance(output_classifications, list) and output_classifications:
        for item in output_classifications:
            print(f"  - `{item}`")
    else:
        print("  - `Formal CLI stdout`")
        print("  - `Formal CLI stderr`")
        print("  - `debug_print`")
        print("  - `logger`")
    print("- **Source-level `.design.md` updated for output-path changes**:")
    design_updates = draft["design_updates"]
    if isinstance(design_updates, str) and design_updates:
        for line in design_updates.splitlines():
            normalized = normalize_draft_line(line)
            if normalized:
                print(f"  - {normalized}")
    print("- **Any new raw `print` introduced?**:")
    raw_print_status = draft["raw_print_status"]
    if isinstance(raw_print_status, str) and raw_print_status:
        for line in raw_print_status.splitlines():
            normalized = normalize_draft_line(line)
            if normalized:
                print(f"  - {normalized}")

    print("")
    print("## 9. Deliverables Produced")
    print("")
    deliverable_lines = draft["deliverable_lines"]
    if isinstance(deliverable_lines, list) and deliverable_lines:
        for line in deliverable_lines:
            print(line)
    else:
        print("- [ ] benchmark case updated")
        print("- [ ] observed IR updated")
        print("- [ ] results observation updated")
        print("- [ ] claim/evidence map updated")
        print("- [ ] changelog updated")
    print("```")


def print_markdown_snippet(results: list[StepResult], run_file: Path, test_suite: str) -> None:
    summary_by_name = {result.name: result for result in results}
    print("\n--- Paste-Ready Validation Block ---")
    print("```md")
    print("- **regression_runner**:")
    print(
        "  - `python scripts/validate/run_ir_meaning_preservation_regression.py "
        f"--run-file {str(run_file.relative_to(PROJECT_ROOT)).replace('\\', '/')} --test-suite {test_suite}`"
    )
    print("  - 結果: `OK: IR meaning-preservation regression workflow completed.`")

    ordered_names = [
        ("sync_project_map", "- **sync_project_map**:"),
        ("project_consistency", "- **project_consistency**:"),
        ("regression_run_validator", "- **regression_run_validator**:"),
    ]

    for internal_name, heading in ordered_names:
        result = summary_by_name[internal_name]
        print(heading)
        print(f"  - `{display_command(result.command)}`")
        print(f"  - 結果: {summarize_output(result)}")

    test_results = [result for result in results if result.name == "test_suite"]
    print("- **unit/integration tests**:")
    if not test_results:
        print("  - `not run`")
    else:
        for result in test_results:
            print(f"  - `{display_command(result.command)}`")
            print(f"  - 結果: {summarize_output(result)}")
    print("- **other checks**:")
    role_checks, alias_check = collect_regression_checks(run_file)
    if not role_checks and alias_check is None:
        print("  - なし")
    else:
        if role_checks:
            print("  - role regression checks:")
            for role, check in role_checks:
                print(f"    - `{role}`: {check}")
        if alias_check is not None:
            label, check = alias_check
            print(f"  - alias regression check: `{label}` -> {check}")
    print("```")


def main() -> int:
    args = parse_args()
    run_file = resolve_run_file(args.run_file)

    if not run_file.exists():
        print(f"ERROR: Run file not found: {run_file}")
        return 1

    print("--- IR Meaning Preservation Regression Runner ---")
    print(f"Run file: {run_file.relative_to(PROJECT_ROOT)}")
    print(f"Test suite: {args.test_suite}")

    results: list[StepResult] = []
    for name, command in build_steps(run_file, args.test_suite):
        print(f"\n>>> {name}: {' '.join(command)}")
        result = run_step(name, command)
        results.append(result)
        if result.return_code != 0:
            print(f"\nFAILED: {name} exited with code {result.return_code}")
            print("\n--- Regression Runner Summary ---")
            for item in results:
                status = "OK" if item.return_code == 0 else "FAILED"
                print(f"- {status}: {item.name} -> {display_command(item.command)}")
            return result.return_code

    print("\n--- Regression Runner Summary ---")
    for item in results:
        print(f"- OK: {item.name} -> {display_command(item.command)}")
    print("OK: IR meaning-preservation regression workflow completed.")
    print_regression_checks(run_file)
    print_summary_draft_snippet(run_file)
    print_claims_and_downstream_draft_snippet(run_file)
    print_check_draft_snippet(run_file)
    print_output_and_deliverables_draft_snippet(run_file)
    print_markdown_snippet(results, run_file, args.test_suite)
    return 0


if __name__ == "__main__":
    sys.exit(main())
