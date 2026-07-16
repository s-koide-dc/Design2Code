# -*- coding: utf-8 -*-
"""Diagnose which local project capabilities are ready without changing the workspace."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
CORE_CONFIG_FILES = (
    "config/config.json",
    "config/safety_policy.json",
    "config/retry_rules.json",
    "config/project_rules.json",
    "config/scoring_rules.json",
    "config/user_preferences.json",
    "config/response_rewriter_config.json",
)
PYTHON_PACKAGES = ("Janome", "numpy")


def _check(name: str, status: str, detail: str, remediation: str | None = None) -> dict[str, str]:
    result = {"name": name, "status": status, "detail": detail}
    if remediation:
        result["remediation"] = remediation
    return result


def _dotnet_version(command_runner: Callable[..., subprocess.CompletedProcess[str]]) -> tuple[str | None, str | None]:
    executable = shutil.which("dotnet")
    if executable is None:
        return None, "dotnet executable was not found on PATH"
    try:
        result = command_runner(
            [executable, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"dotnet --version could not run: {type(exc).__name__}"
    if result.returncode != 0:
        return None, (result.stderr or result.stdout or "dotnet --version failed").strip()
    version = result.stdout.strip()
    return (version or None), None


def _required_version(workspace_root: Path) -> str | None:
    global_json = workspace_root / "global.json"
    if not global_json.is_file():
        return None
    try:
        data = json.loads(global_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    sdk = data.get("sdk") if isinstance(data, dict) else None
    version = sdk.get("version") if isinstance(sdk, dict) else None
    return version if isinstance(version, str) else None


def _version_parts(version: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in version.split("-", 1)[0].split("."))
    except ValueError:
        return None


def _is_dotnet_compatible(installed: str, required: str | None) -> bool:
    if required is None:
        return True
    installed_parts = _version_parts(installed)
    required_parts = _version_parts(required)
    return (
        installed_parts is not None
        and required_parts is not None
        and installed_parts[:1] == required_parts[:1]
        and installed_parts >= required_parts
    )


def _invalid_config_paths(workspace_root: Path) -> list[str]:
    invalid: list[str] = []
    for relative_path in CORE_CONFIG_FILES:
        path = workspace_root / relative_path
        if not path.is_file():
            continue
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            invalid.append(relative_path)
            continue
        if not isinstance(content, dict):
            invalid.append(relative_path)
    return invalid


def diagnose(
    workspace_root: Path,
    *,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    package_version: Callable[[str], str] = importlib.metadata.version,
) -> dict[str, Any]:
    """Return a structured, read-only capability report for a workspace."""
    workspace_root = workspace_root.resolve()
    checks: list[dict[str, str]] = []

    python_ready = sys.version_info >= (3, 13)
    checks.append(_check(
        "python",
        "ready" if python_ready else "blocked",
        f"Python {sys.version.split()[0]}",
        "Use Python 3.13 or newer." if not python_ready else None,
    ))

    missing_packages: list[str] = []
    installed_packages: list[str] = []
    for package in PYTHON_PACKAGES:
        try:
            installed_packages.append(f"{package} {package_version(package)}")
        except importlib.metadata.PackageNotFoundError:
            missing_packages.append(package)
    checks.append(_check(
        "python_dependencies",
        "ready" if not missing_packages else "blocked",
        ", ".join(installed_packages) if not missing_packages else f"missing: {', '.join(missing_packages)}",
        "Install project dependencies with: pip install -r requirements-dev.txt" if missing_packages else None,
    ))

    missing_configs = [path for path in CORE_CONFIG_FILES if not (workspace_root / path).is_file()]
    invalid_configs = _invalid_config_paths(workspace_root)
    configuration_issues = missing_configs + invalid_configs
    checks.append(_check(
        "configuration",
        "ready" if not configuration_issues else "blocked",
        "all required configuration files are present and valid" if not configuration_issues else f"missing or invalid: {', '.join(configuration_issues)}",
        "Restore valid repository configuration files before running the project." if configuration_issues else None,
    ))

    dotnet_version, dotnet_error = _dotnet_version(command_runner)
    required_dotnet = _required_version(workspace_root)
    dotnet_ready = dotnet_version is not None and _is_dotnet_compatible(dotnet_version, required_dotnet)
    checks.append(_check(
        "dotnet_sdk",
        "ready" if dotnet_ready else "blocked",
        f".NET SDK {dotnet_version}" if dotnet_ready else (dotnet_error or f"requires .NET SDK {required_dotnet}"),
        f"Install .NET SDK {required_dotnet} or a compatible stable feature band." if not dotnet_ready else None,
    ))

    codebuilder_project = workspace_root / "tools" / "csharp" / "CodeBuilder" / "CodeBuilder.csproj"
    checks.append(_check(
        "codebuilder_source",
        "ready" if codebuilder_project.is_file() else "blocked",
        str(codebuilder_project.relative_to(workspace_root)) if codebuilder_project.is_file() else "CodeBuilder project is missing",
        "Restore tools/csharp/CodeBuilder from the repository." if not codebuilder_project.is_file() else None,
    ))

    model_path = workspace_root / "resources" / "vectors" / "chive-1.3-mc90.txt"
    vector_assets = (model_path, Path(f"{model_path}.v0.vocab.npy"), Path(f"{model_path}.v0.matrix.npy"))
    missing_vector_assets = [path.name for path in vector_assets if not path.is_file()]
    checks.append(_check(
        "semantic_vector_model",
        "ready" if not missing_vector_assets else "optional_missing",
        "chiVe model and caches are available" if not missing_vector_assets else f"missing: {', '.join(missing_vector_assets)}",
        "Run: python scripts/data/fetch_vectors.py, then python scripts/data/convert_vectors.py" if missing_vector_assets else None,
    ))

    vector_db = workspace_root / "resources" / "vectors" / "vector_db"
    method_search_assets = (vector_db / "method_store_meta.json", vector_db / "method_store_vectors.npy")
    missing_method_assets = [path.name for path in method_search_assets if not path.is_file()]
    checks.append(_check(
        "semantic_method_search",
        "ready" if not missing_vector_assets and not missing_method_assets else "optional_missing",
        "method-store vector database is available" if not missing_vector_assets and not missing_method_assets else f"missing: {', '.join(missing_method_assets or missing_vector_assets)}",
        "After preparing chiVe, run: python scripts/tools/manage_vector_db.py seed" if missing_vector_assets or missing_method_assets else None,
    ))

    dictionary_path = workspace_root / "resources" / "dictionary.db"
    checks.append(_check(
        "dictionary_search",
        "ready" if dictionary_path.is_file() else "optional_missing",
        "dictionary.db is available" if dictionary_path.is_file() else "dictionary.db is missing",
        "Run: python scripts/data/fetch_jmdict.py, then python scripts/data/parse_jmdict.py" if not dictionary_path.is_file() else None,
    ))

    status_by_name = {check["name"]: check["status"] for check in checks}
    capabilities = {
        "design_generation": all(status_by_name[name] == "ready" for name in ("python", "python_dependencies", "configuration", "dotnet_sdk", "codebuilder_source")),
        "semantic_pipeline": status_by_name["semantic_vector_model"] == "ready",
        "semantic_method_search": status_by_name["semantic_method_search"] == "ready",
        "dictionary_search": status_by_name["dictionary_search"] == "ready",
    }
    return {"workspace_root": str(workspace_root), "checks": checks, "capabilities": capabilities}


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose local Design2Code prerequisites without modifying files.")
    parser.add_argument("--workspace-root", type=Path, default=WORKSPACE_ROOT)
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.add_argument(
        "--require",
        choices=("design_generation", "semantic_pipeline", "semantic_method_search", "dictionary_search"),
        action="append",
        help="Return a non-zero status unless the named capability is ready. Repeatable.",
    )
    args = parser.parse_args()
    report = diagnose(args.workspace_root)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Workspace: {report['workspace_root']}")
        for check in report["checks"]:
            print(f"[{check['status'].upper()}] {check['name']}: {check['detail']}")
            if "remediation" in check:
                print(f"  -> {check['remediation']}")
        print("Capabilities:")
        for name, ready in report["capabilities"].items():
            print(f"  {name}: {'ready' if ready else 'unavailable'}")

    missing = [name for name in args.require or [] if not report["capabilities"][name]]
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
