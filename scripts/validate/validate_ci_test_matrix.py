"""Validate the explicit CI/local integration-test boundary."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "tests" / "ci_test_matrix.json"
INTEGRATION_DIR = ROOT / "tests" / "integration"


def validate_matrix() -> list[str]:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    included = matrix["integration"]["ci_included"]
    excluded = matrix["integration"]["ci_excluded"]
    names = [entry["file"] for entry in excluded]
    errors = []

    if len(names) != len(set(names)):
        errors.append("duplicate integration exclusion")
    if len(included) != len(set(included)):
        errors.append("duplicate integration inclusion")
    if set(names) & set(included):
        errors.append("integration test appears in both included and excluded lists")

    for entry in excluded:
        name = entry.get("file")
        if not isinstance(name, str) or not name.startswith("test_") or not name.endswith(".py"):
            errors.append(f"invalid integration test filename: {name!r}")
        elif not (INTEGRATION_DIR / name).is_file():
            errors.append(f"excluded integration test does not exist: {name}")
        if not entry.get("reason") or not entry.get("validation"):
            errors.append(f"missing exclusion rationale: {name}")

    all_tests = {path.name for path in INTEGRATION_DIR.glob("test_*.py")}
    for name in included:
        if not isinstance(name, str) or not name.startswith("test_") or not name.endswith(".py"):
            errors.append(f"invalid included integration test filename: {name!r}")
        elif name not in all_tests:
            errors.append(f"included integration test does not exist: {name}")

    unclassified = sorted(all_tests - set(names) - set(included))
    if unclassified:
        errors.append(
            "integration tests missing from CI matrix: " + ", ".join(unclassified)
        )
    return errors


def main() -> int:
    errors = validate_matrix()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: CI test matrix is complete and consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
