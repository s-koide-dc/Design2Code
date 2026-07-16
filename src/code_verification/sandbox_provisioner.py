# -*- coding: utf-8 -*-
"""Provision short-lived .NET projects for generated-code verification."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

from .dependency_contract import render_package_references


class SandboxProvisioner:
    """Create one owned temporary project directory per verification run."""

    def __init__(self, config, dotnet_path: str = "dotnet"):
        self.config = config
        self.dotnet_path = dotnet_path
        self.temp_dir: Path | None = None
        self.logger = logging.getLogger(__name__)

    def provision_sandbox(self, project_name: str, dependencies: List[Dict[str, str]]) -> Path:
        """Create a fresh project and restore its validated dependencies.

        ``project_name`` remains part of the public API for compatibility.  The
        generated project always uses a fixed, internal filename so callers
        cannot influence paths in the temporary directory.
        """
        del project_name
        package_references = render_package_references(dependencies)
        self.clean_up()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="nlp_codegen_sandbox_"))

        csproj_path = self.temp_dir / "Sandbox.csproj"
        csproj_path.write_text(
            self._generate_csproj(package_references),
            encoding="utf-8",
        )

        try:
            result = subprocess.run(
                [self.dotnet_path, "restore", str(csproj_path)],
                cwd=self.temp_dir,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode != 0:
                self.logger.warning("Sandbox restore failed: %s", result.stderr.strip())
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.logger.warning("Sandbox restore failed: %s", exc)

        return self.temp_dir

    @staticmethod
    def _generate_csproj(package_references: str) -> str:
        return f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
{package_references}  </ItemGroup>
</Project>
"""

    def clean_up(self):
        """Remove only the temporary directory created by this instance."""
        if self.temp_dir is None:
            return
        temporary_directory = self.temp_dir
        self.temp_dir = None
        shutil.rmtree(temporary_directory, ignore_errors=True)
