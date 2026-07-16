#!/usr/bin/env python
"""Generate the representative project and run its SQL Server integration tests."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.code_generation.project_generator import ProjectGenerator
from src.design_parser import ProjectSpecParser


def _run(command: list[str], *, cwd: Path | None = None) -> int:
    print(f"[sqlserver-ci] {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=cwd, check=False)
    return completed.returncode


def _verify_localdb() -> int:
    if shutil.which("sqllocaldb") is None:
        print("sqllocaldb was not found; SQL Server LocalDB is required.", file=sys.stderr)
        return 1

    info_code = _run(["sqllocaldb", "info", "MSSQLLocalDB"])
    if info_code != 0:
        print("The MSSQLLocalDB instance is not available on this runner.", file=sys.stderr)
        return info_code

    start_code = _run(["sqllocaldb", "start", "MSSQLLocalDB"])
    if start_code != 0:
        print("The MSSQLLocalDB instance could not be started.", file=sys.stderr)
    return start_code


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--design",
        default="scenarios/SampleProject.design.md",
        help="Design document used to generate the representative project.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if _verify_localdb() != 0:
        return 1

    design_path = WORKSPACE_ROOT / args.design
    if not design_path.is_file():
        print(f"Design document not found: {design_path}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="nlp-sqlserver-ci-") as temporary_root:
        output_root = Path(temporary_root)
        spec = ProjectSpecParser().parse_file(str(design_path))
        ProjectGenerator().generate(spec, str(output_root))
        test_project = output_root / "Tests" / f"{spec['project_name']}.Tests.csproj"
        if not test_project.is_file():
            print(f"Generated test project not found: {test_project}", file=sys.stderr)
            return 1

        return _run(
            [
                "dotnet",
                "test",
                str(test_project),
                "--configuration",
                "Release",
                "--nologo",
                "--filter",
                "FullyQualifiedName~ProjectSqlServerEndpointTests",
            ],
            cwd=WORKSPACE_ROOT,
        )


if __name__ == "__main__":
    raise SystemExit(main())
