"""Validate portable Markdown links and documentation ownership contracts."""

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOC_POLICY = ROOT / "config" / "doc_reference_policy.json"
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
MACHINE_PATH_PATTERN = re.compile(r"(?:[A-Za-z]:\\workspace|/C:/workspace)", re.IGNORECASE)


def validate() -> list[str]:
    import json

    errors = []
    policy = json.loads(DOC_POLICY.read_text(encoding="utf-8"))
    required_docs = set(policy.get("required_docs", []))
    required_docs.add("docs/documentation_source_of_truth.md")

    for relative in sorted(required_docs):
        if not (ROOT / relative).is_file():
            errors.append(f"required documentation is missing: {relative}")

    for document in ROOT.glob("**/*.md"):
        if (
            any(part in {".git", "__pycache__", "bin", "obj", "node_modules", "cache", "logs"} for part in document.parts)
            or document.name.endswith(".inferred.design.md")
        ):
            continue
        content = document.read_text(encoding="utf-8", errors="ignore")
        if MACHINE_PATH_PATTERN.search(content):
            errors.append(f"machine-specific workspace path found: {document.relative_to(ROOT)}")

        for target in LINK_PATTERN.findall(content):
            target = target.split("#", 1)[0].strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (document.parent / target).resolve().exists():
                errors.append(
                    f"broken local Markdown link: {document.relative_to(ROOT)} -> {target}"
                )
    return sorted(set(errors))


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: documentation links and portability checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
