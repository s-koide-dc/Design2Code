"""Deterministic fingerprints for independent verification evidence scopes."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_CONFIG_INPUTS = (
    "config.json",
    "safety_policy.json",
    "retry_rules.json",
    "project_rules.json",
    "scoring_rules.json",
    "user_preferences.json",
    "response_rewriter_config.json",
)


def _source_files(root: Path, pattern: str) -> list[Path]:
    """Return source inputs while excluding compiler outputs.

    Build directories are intentionally omitted: their contents are not source
    evidence and can vary between clean and incremental builds.
    """
    return [
        path
        for path in root.rglob(pattern)
        if "bin" not in path.parts and "obj" not in path.parts
    ]


def _fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda candidate: candidate.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def generation_fingerprint() -> str:
    return _fingerprint([
        *(ROOT / "config" / name for name in _CONFIG_INPUTS),
        ROOT / "resources" / "method_store.json",
        *sorted((ROOT / "src" / "design_parser").rglob("*.py")),
        *sorted((ROOT / "src" / "ir_generator").rglob("*.py")),
        *sorted((ROOT / "src" / "code_synthesis").rglob("*.py")),
        *_source_files(ROOT / "tools" / "csharp" / "CodeBuilder", "*.cs"),
        ROOT / "scripts" / "generate" / "generate_from_design.py",
        ROOT / "scripts" / "design" / "review_design_generation_snapshot.py",
    ])


def runtime_oracle_fingerprint() -> str:
    return _fingerprint([
        ROOT / "src" / "code_verification" / "execution_verifier.py",
        ROOT / "src" / "code_verification" / "runtime_oracle.py",
        ROOT / "src" / "code_verification" / "runtime_oracle_contract.py",
        ROOT / "src" / "code_verification" / "runtime_oracle_executor.py",
        ROOT / "src" / "code_verification" / "runtime_oracle_test_builder.py",
        ROOT / "src" / "code_verification" / "sandbox_provisioner.py",
    ])


def generation_quality_fingerprint() -> str:
    return _fingerprint([
        ROOT / "src" / "code_verification" / "generation_quality.py",
        ROOT / "src" / "code_verification" / "semantic_assertions.py",
    ])


def compilation_fingerprint() -> str:
    return _fingerprint([
        ROOT / "src" / "code_verification" / "compilation_verifier.py",
        ROOT / "src" / "code_verification" / "dependency_contract.py",
    ])


def project_generation_fingerprint() -> str:
    return _fingerprint([
        *(ROOT / "config" / name for name in _CONFIG_INPUTS),
        ROOT / "resources" / "method_store.json",
        *sorted((ROOT / "templates" / "project").rglob("*.json")),
        *sorted((ROOT / "src" / "design_parser").rglob("*.py")),
        *sorted((ROOT / "src" / "code_generation").rglob("*.py")),
        *sorted((ROOT / "src" / "test_generator").rglob("*.py")),
        *sorted((ROOT / "src" / "ir_generator").rglob("*.py")),
        *sorted((ROOT / "src" / "code_synthesis").rglob("*.py")),
        *_source_files(ROOT / "tools" / "csharp" / "CodeBuilder", "*.cs"),
        ROOT / "scripts" / "validate" / "validate_generated_sqlserver.py",
    ])
