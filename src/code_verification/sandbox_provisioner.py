# -*- coding: utf-8 -*-
import os
import shutil
import subprocess
import tempfile
from typing import List, Dict, Any, Optional
from pathlib import Path

class SandboxProvisioner:
    """
    [Phase 24.4: Development Environment Provisioning]
    検証用の隔離された C# プロジェクト環境（Sandbox）を動的に構築し、
    NuGet パッケージのリストアやビルドを可能にする。
    """
    def __init__(self, config):
        self.config = config
        self.root = getattr(config, 'workspace_root', os.getcwd())
        self.temp_dir = Path(tempfile.gettempdir()) / "gemini_nlp_sandbox"

    def provision_sandbox(self, project_name: str, dependencies: List[Dict[str, str]]) -> Path:
        """
        最小限の .csproj を含むプロジェクトディレクトリを作成し、依存関係を設定する。
        """
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Create .csproj
        csproj_content = self._generate_csproj(dependencies)
        csproj_path = self.temp_dir / f"{project_name}.csproj"
        with open(csproj_path, "w", encoding="utf-8") as f:
            f.write(csproj_content)
        
        # 2. Restore packages
        try:
            subprocess.run(["dotnet", "restore", str(csproj_path)], 
                           capture_output=True, check=True, timeout=30)
        except Exception as e:
            print(f"[!] Sandbox restore failed: {e}")
            
        return self.temp_dir

    def _generate_csproj(self, dependencies: List[Dict[str, str]]) -> str:
        pkg_refs = []
        for dep in dependencies:
            name = dep.get("name")
            version = dep.get("version", "*")
            if name:
                pkg_refs.append(f'    <PackageReference Include="{name}" Version="{version}" />')
        
        refs_str = "\n".join(pkg_refs)
        
        return f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
{refs_str}
  </ItemGroup>
</Project>
"""

    def clean_up(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
