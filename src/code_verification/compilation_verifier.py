# -*- coding: utf-8 -*-
import os
import subprocess
import re
import shutil
import tempfile
from typing import Dict, List, Any

class CompilationVerifier:
    """生成された C# コードのコンパイル可能性を検証するクラス"""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.dotnet_path = "dotnet"
        self._initialized_dirs = set()
        self.base_sandbox_path = os.path.join(os.getcwd(), "cache", "base_sandbox")
        self.default_deps = [
            {"name": "Dapper", "version": "2.1.35"},
            {"name": "Newtonsoft.Json", "version": "13.0.3"}
        ]

    def _merge_deps(self, base_deps: List[Dict[str, str]], extra_deps: List[Dict[str, str]] = None):
        deps_by_name = {d.get("name"): dict(d) for d in base_deps if d.get("name")}
        changed = False
        if extra_deps:
            for d in extra_deps:
                name = d.get("name")
                if not name:
                    continue
                if name not in deps_by_name:
                    deps_by_name[name] = dict(d)
                    changed = True
                else:
                    ver = d.get("version")
                    if ver and ver != "*" and deps_by_name[name].get("version") != ver:
                        deps_by_name[name]["version"] = ver
                        changed = True
        return list(deps_by_name.values()), changed

    def _ensure_base_sandbox(self, dependencies: List[Dict[str, str]] = None):
        """共通の依存関係が解決済みのベース・サンドボックスを準備する"""
        base_deps, _ = self._merge_deps(self.default_deps, dependencies)
        base_obj = os.path.join(self.base_sandbox_path, "obj")
        base_csproj = os.path.join(self.base_sandbox_path, "Sandbox.csproj")
        if os.path.exists(base_obj) and os.path.exists(base_csproj):
            try:
                with open(base_csproj, "r", encoding="utf-8") as f:
                    csproj_text = f.read()
                has_all = True
                for dep in base_deps:
                    name = dep.get("name")
                    ver = dep.get("version")
                    if not name:
                        continue
                    if f'Include="{name}"' not in csproj_text:
                        has_all = False
                        break
                    if ver and ver != "*" and f'Version="{ver}"' not in csproj_text:
                        has_all = False
                        break
                if has_all:
                    return True
            except Exception:
                pass
        self.initialize_sandbox(self.base_sandbox_path, base_deps)
        return True

    def initialize_sandbox(self, work_dir: str, dependencies: List[Dict[str, str]] = None) -> bool:
        """指定されたディレクトリにプロジェクトを作成し、Restoreを実行して準備する"""
        os.makedirs(work_dir, exist_ok=True)
        
        # プロジェクトファイルの作成
        package_refs = ""
        default_deps = list(self.default_deps)
        final_deps, _ = self._merge_deps(default_deps, dependencies)
        
        for dep in final_deps:
            ver = dep.get("version", "*")
            package_refs += f'    <PackageReference Include="{dep["name"]}" Version="{ver}" />\n'

        target_csproj = os.path.join(work_dir, 'Sandbox.csproj')
        csproj_content = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <OutputType>Library</OutputType>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="GeneratedCode.cs" />
  </ItemGroup>
  <ItemGroup>
{package_refs}  </ItemGroup>
</Project>
"""
        with open(target_csproj, 'w', encoding='utf-8') as f:
            f.write(csproj_content)
            
        # ダミーの空ファイルを生成してRestoreを走らせる
        with open(os.path.join(work_dir, "GeneratedCode.cs"), 'w', encoding='utf-8') as f:
            f.write("// Initializing\npublic class Init {}")

        # 最初のRestore
        result = subprocess.run(
            [self.dotnet_path, 'restore'],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            self._initialized_dirs.add(work_dir)
            return True
        return False

    def verify(self, source_code: str, dependencies: List[Dict[str, str]] = None, work_dir: str = None) -> Dict[str, Any]:
        """サンドボックス環境でコードをビルドし、結果を返す"""
        
        # 1. 作業ディレクトリの準備
        temp_dir = work_dir or tempfile.mkdtemp(prefix="cs_sandbox_")
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # 1.1. ベース・サンドボックスの適用 (高速化)
            is_fast_track = False
            if temp_dir not in self._initialized_dirs and not os.path.exists(os.path.join(temp_dir, "obj")):
                self._ensure_base_sandbox() # デフォルトのベースを確保
                if os.path.exists(self.base_sandbox_path):
                    base_obj = os.path.join(self.base_sandbox_path, "obj")
                    if os.path.exists(base_obj):
                        shutil.copytree(base_obj, os.path.join(temp_dir, "obj"), dirs_exist_ok=True)
                        # csproj もコピー
                        shutil.copy2(os.path.join(self.base_sandbox_path, "Sandbox.csproj"), os.path.join(temp_dir, "Sandbox.csproj"))
                        self._initialized_dirs.add(temp_dir)
                        is_fast_track = True

            # 依存関係の構築
            package_refs = ""
            default_deps = list(self.default_deps)
            
            # マージ (指定がない場合はデフォルトのみ)
            final_deps, deps_changed = self._merge_deps(default_deps, dependencies)
            if deps_changed:
                # 依存が増減/バージョン変更される場合は restore が必要
                is_fast_track = False
            
            for dep in final_deps:
                ver = dep.get("version", "*") # バージョン指定がなければ最新
                package_refs += f'    <PackageReference Include="{dep["name"]}" Version="{ver}" />\n'

            # 2. プロジェクトの初期化
            target_csproj = os.path.join(temp_dir, 'Sandbox.csproj')
            
            # 依存関係に変更があるか、csproj が存在しない場合は作成
            csproj_content = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <OutputType>Library</OutputType>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="GeneratedCode.cs" />
  </ItemGroup>
  <ItemGroup>
{package_refs}  </ItemGroup>
</Project>
"""
            should_write_csproj = False
            if not os.path.exists(target_csproj):
                should_write_csproj = True
            else:
                with open(target_csproj, 'r', encoding='utf-8') as f:
                    if f.read() != csproj_content:
                        should_write_csproj = True
            
            if should_write_csproj:
                with open(target_csproj, 'w', encoding='utf-8') as f:
                    f.write(csproj_content)
                if is_fast_track and deps_changed:
                    is_fast_track = False # Restore required when deps change

            # 3. ソースコードの正規化と書き出し
            # Synthesizerが出力するコードは partial class や wrapper が必要な場合がある
            normalized_code = self._normalize_code(source_code)
            with open(os.path.join(temp_dir, "GeneratedCode.cs"), 'w', encoding='utf-8') as f:
                f.write(normalized_code)

            # 4. ビルド実行
            build_cmd = [self.dotnet_path, 'build', '--verbosity', 'quiet', '--nologo']
            if is_fast_track:
                build_cmd.append('--no-restore')
                
            result = subprocess.run(
                build_cmd,
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=120  # タイムアウトを延長
            )

            # 5. 結果の解析
            is_valid = (result.returncode == 0)
            errors = self._parse_errors(result.stdout + result.stderr)
            
            # ビルド成功時はエラーがあっても（警告等）成功とみなす
            if is_valid:
                return {
                    'valid': True,
                    'errors': [],
                    'stdout': result.stdout
                }
            
            return {
                'valid': False,
                'errors': errors,
                'stdout': result.stdout,
                'stderr': result.stderr
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "work_dir": temp_dir
            }
        finally:
            # work_dir が指定されていない場合のみ自動削除
            if not work_dir and os.path.exists(temp_dir):
                # shutil.rmtree(temp_dir) # デバッグのために一旦残すことも検討
                pass

    def _normalize_code(self, code: str) -> str:
        """コードが完全なクラス定義を含まない場合、ラップする"""
        if "class " in code:
            return code
            
        # using句とそれ以外を分離
        lines = code.split('\n')
        usings = [line for line in lines if line.strip().startswith("using ")]
        rest = [line for line in lines if not line.strip().startswith("using ")]
        
        wrapped = "\n".join(usings) + "\n\n"
        wrapped += "public class Sandbox {\n"
        wrapped += "    private static dynamic _service = null;\n" # ダミー
        wrapped += "\n".join(rest)
        wrapped += "\n}"
        return wrapped

    def _parse_errors(self, output: str) -> List[Dict[str, Any]]:
        """MSBuild のエラー出力をパースして構造化データにする"""
        errors = []
        # Handle variations: "error CS0246: The type..." or "error CS0246:The type..."
        pattern = r"(.+)\((\d+),(\d+)\):\s+error\s+(CS\d+)\s*:\s*(.+)"
        for match in re.finditer(pattern, output):
            code = match.group(4)
            msg = match.group(5)
            
            # エラータイプの分類
            error_type = "UNKNOWN"
            if code in ["CS0103", "CS0246"]: error_type = "SYMBOL_NOT_FOUND"
            elif code in ["CS1503", "CS0029", "CS0266"]: error_type = "TYPE_MISMATCH"
            elif code in ["CS1002"]: error_type = "SYNTAX_ERROR"
            elif code in ["CS0117", "CS1061"]: error_type = "MEMBER_NOT_FOUND"
            elif code in ["CS0120"]: error_type = "INSTANCE_REQUIRED"

            errors.append({
                "file": match.group(1),
                "line": int(match.group(2)),
                "column": int(match.group(3)),
                "code": code,
                "error_type": error_type,
                "message": msg
            })
        return errors

    def verify_project(self, project_root: str, project_name: str = None) -> Dict[str, Any]:
        """プロジェクト全体のビルドを実行して結果を返す"""
        if not project_root or not os.path.exists(project_root):
            return {"valid": False, "errors": [{"message": "Project root not found"}]}

        project_root = os.path.abspath(project_root)
        csproj_files = [f for f in os.listdir(project_root) if f.endswith(".csproj")]
        main_csproj = None
        if project_name:
            candidate = f"{project_name}.csproj"
            if candidate in csproj_files:
                main_csproj = os.path.join(project_root, candidate)
        if main_csproj is None:
            non_test = [f for f in csproj_files if not f.endswith(".Tests.csproj")]
            if non_test:
                main_csproj = os.path.join(project_root, non_test[0])

        test_csproj = None
        if project_name:
            test_candidate = os.path.join(project_root, "Tests", f"{project_name}.Tests.csproj")
            if os.path.exists(test_candidate):
                test_csproj = test_candidate

        results = []
        for csproj in [main_csproj, test_csproj]:
            if not csproj:
                continue
            result = subprocess.run(
                [self.dotnet_path, "build", csproj, "--verbosity", "quiet", "--nologo"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=180
            )
            is_valid = (result.returncode == 0)
            errors = self._parse_errors(result.stdout + result.stderr)
            if not is_valid and not errors:
                msg = (result.stderr or result.stdout or "").strip()
                if msg:
                    errors = [{"message": msg}]
            results.append({
                "project": csproj,
                "valid": is_valid,
                "errors": errors,
                "stdout": result.stdout,
                "stderr": result.stderr
            })

        overall_valid = all(r["valid"] for r in results) if results else False
        all_errors = []
        for r in results:
            all_errors.extend(r.get("errors") or [])

        return {
            "valid": overall_valid,
            "errors": all_errors,
            "projects": results
        }
