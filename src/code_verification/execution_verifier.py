# -*- coding: utf-8 -*-
import os
import subprocess
import json
import tempfile
import shutil
import xml.etree.ElementTree as ET
from typing import Dict, List, Any
from .compilation_verifier import CompilationVerifier
from src.utils.stdout_guard import debug_print

class ExecutionVerifier(CompilationVerifier):
    """
    生成されたコードを実際に実行して動作を検証するクラス。
    """

    def __init__(self, config_manager=None):
        super().__init__(config_manager)
        root = getattr(config_manager, "workspace_root", os.getcwd()) if config_manager else os.getcwd()
        self.code_builder_project_path = os.path.join(
            str(root),
            "tools",
            "csharp",
            "CodeBuilder",
            "CodeBuilder.csproj",
        )
        self.json_start_marker = "__CODEBUILDER_JSON_START__"
        self.json_end_marker = "__CODEBUILDER_JSON_END__"

    def _inspect_source_structure(self, source_code: str, method_name: str) -> Dict[str, Any]:
        if not os.path.exists(self.code_builder_project_path):
            return {
                "status": "error",
                "message": "CodeBuilder project is not available.",
                "project_path": self.code_builder_project_path,
            }

        request = {
            "source_code": source_code,
            "method_name": method_name,
        }
        result = subprocess.run(
            [
                self.dotnet_path,
                "run",
                "--project",
                self.code_builder_project_path,
                "--quiet",
                "--nologo",
                "--",
                "--inspect-source",
            ],
            input=json.dumps(request, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return {
                "status": "error",
                "message": "CodeBuilder inspection command failed.",
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        payload = self._extract_marked_json_payload(result.stdout)
        if not payload:
            return {
                "status": "error",
                "message": "CodeBuilder inspection did not return JSON.",
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            return {
                "status": "error",
                "message": "CodeBuilder inspection returned invalid JSON.",
                "error_type": type(exc).__name__,
                "stdout": result.stdout,
            }
        return parsed

    def _extract_marked_json_payload(self, stdout: str) -> str:
        if not stdout:
            return ""
        if self.json_start_marker in stdout and self.json_end_marker in stdout:
            start_idx = stdout.rfind(self.json_start_marker)
            end_idx = stdout.rfind(self.json_end_marker)
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                return stdout[start_idx + len(self.json_start_marker):end_idx].strip()
        lines = [line for line in stdout.splitlines() if line.strip()]
        return lines[-1] if lines else ""

    def _build_constructor_args(self, parameters: List[Dict[str, Any]]) -> str:
        args = []
        for parameter in parameters or []:
            param_type = parameter.get("type")
            if isinstance(param_type, str) and param_type.strip():
                args.append(f"NSubstitute.Substitute.For<{param_type.strip()}>()")
        return ", ".join(args)

    def _build_method_args(self, parameters: List[Dict[str, Any]]) -> List[str]:
        from src.advanced_tdd.dummy_factory import DummyDataFactory

        factory = DummyDataFactory()
        args = []
        for parameter in parameters or []:
            param_type = parameter.get("type")
            if isinstance(param_type, str) and param_type.strip():
                args.append(factory.generate_instantiation(param_type.strip()))
        return args

    def run_and_capture(self, source_code: str, method_name: str, args: List[Any] = None, work_dir: str = None, assertion_goals: List[Dict[str, Any]] = None, dependencies: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """コードを単純実行可能な形式にラップして実行し、実行時エラーを捕捉する"""
        temp_dir = work_dir or tempfile.mkdtemp(prefix="cs_exec_")
        os.makedirs(temp_dir, exist_ok=True)

        assertion_goals = assertion_goals or []
        dependencies = dependencies or []

        try:
            inspection_result = self._inspect_source_structure(source_code, method_name)
            if inspection_result.get("status") != "success":
                return {
                    "success": False,
                    "error_type": "SOURCE_INSPECTION_FAILED",
                    "inspection": inspection_result,
                }

            inspection = inspection_result["inspection"]
            qualified_name = inspection["qualified_name"]
            method_info = inspection["method"]
            return_type = method_info.get("return_type", "void")
            ctor_args_code = self._build_constructor_args(
                inspection.get("constructor_parameters", []),
            )
            method_args_code = self._build_method_args(method_info.get("parameters", []))

            call_args = ", ".join(method_args_code) if method_args_code else ""

            # アサーションコードの生成
            assertion_code = ""
            is_collection = any(kw in return_type for kw in ["IEnumerable", "List", "[]"])

            if return_type != "void":
                for goal in assertion_goals:
                    if goal['type'] == 'numeric':
                        op = goal['operator']
                        expected = goal['expected_value']
                        var_hint = goal.get('variable_hint')

                        op_map = {
                            "GreaterEqual": ">=", "LessEqual": "<=", "Equal": "==",
                            "NotEqual": "!=", "Greater": ">", "Less": "<"
                        }
                        cs_op = op_map.get(op, "==")

                        # 評価対象の式
                        expr = "result"
                        if is_collection:
                            # コレクションの場合は All で全要素をチェック
                            prop_access = f".{var_hint}" if var_hint else ""
                            assertion_code += f"""
                if (!result.All(item => item{prop_access} {cs_op} {expected})) {{
                    throw new InvalidOperationException($"Expected all items to have {var_hint or 'value'} {cs_op} {expected}");
                }}"""
                        else:
                            assertion_code += f"""
                if (!(result {cs_op} {expected})) {{
                    throw new InvalidOperationException($"Expected result {cs_op} {expected}, but got {{result}}");
                }}"""
                    elif goal['type'] == 'string' and goal['operator'] == 'Contains':
                        expected = goal['expected_value']
                        if is_collection:
                            assertion_code += f"""
                if (!result.Any(item => item.ToString().Contains("{expected}"))) {{
                    throw new InvalidOperationException($"Expected at least one item to contain '{expected}'");
                }}"""
                        else:
                            assertion_code += f"""
                if (!result.ToString().Contains("{expected}")) {{
                    throw new InvalidOperationException($"Expected result to contain '{expected}', but got {{result}}");
                }}"""

            # fixture fileはテスト契約で明示されたものだけを作成する
            for goal in assertion_goals:
                for fixture in goal.get("fixture_files", []) or []:
                    if not isinstance(fixture, dict):
                        continue
                    filename = fixture.get("path")
                    content = fixture.get("content")
                    if not isinstance(filename, str) or not isinstance(content, str):
                        continue
                    filepath = os.path.abspath(os.path.join(temp_dir, filename))
                    if os.path.commonpath([temp_dir, filepath]) != os.path.abspath(temp_dir):
                        raise ValueError("Fixture file must remain inside the execution sandbox.")
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    debug_print(f"[ExecutionVerifier] Created fixture file: {filename}")

            wrapper = f"""
using System;
using System.Threading.Tasks;
using System.Collections.Generic;
using System.Linq;
using System.IO;
using System.Net.Http;
using System.Text.Json;
using NSubstitute;

public class Program
{{
    public static async Task Main(string[] args)
    {{
        try
        {{
            Console.SetIn(new StringReader("1"));
            var processor = new {qualified_name}({ctor_args_code});
            {"var result = await " if return_type.startswith("Task<") else ("await " if return_type == "Task" else ("var result = " if return_type != "void" else ""))}processor.{method_name}({call_args});
            {assertion_code}
        }}
        catch (Exception ex)
        {{
            Exception actualEx = ex;
            if (ex is AggregateException aggEx) actualEx = aggEx.InnerException;

            Console.WriteLine("__RUNTIME_JSON__" + JsonSerializer.Serialize(new
            {{
                type = actualEx.GetType().FullName,
                message = actualEx.Message,
                stackTrace = actualEx.StackTrace
            }}));
            Environment.Exit(1);
        }}
    }}
}}
"""
            # csproj (work_dir が指定されていない、またはファイルが存在しない場合のみ作成)
            target_csproj = os.path.join(temp_dir, "Exec.csproj")

            dep_items = ""
            for dep in dependencies:
                name = dep.get("name")
                version = dep.get("version", "*")
                if name:
                    dep_items += f'    <PackageReference Include="{name}" Version="{version}" />\n'

            if not os.path.exists(target_csproj):
                with open(target_csproj, "w", encoding="utf-8") as f:
                    f.write(f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
    <PackageReference Include="NSubstitute" Version="5.3.0" />
{dep_items}
  </ItemGroup>
</Project>""")

            # 結合コード
            source_lines = source_code.split('\n')
            wrapper_lines = wrapper.split('\n')
            all_usings = set()
            other_source = []
            other_wrapper = []

            for line in source_lines:
                if line.strip().startswith("using "): all_usings.add(line.strip())
                else: other_source.append(line)
            for line in wrapper_lines:
                if line.strip().startswith("using "): all_usings.add(line.strip())
                else: other_wrapper.append(line)

            combined_code = "\n".join(sorted(list(all_usings))) + "\n\n"
            combined_code += "\n".join(other_source) + "\n\n"
            combined_code += "\n".join(other_wrapper)

            with open(os.path.join(temp_dir, "Program.cs"), "w", encoding="utf-8") as f:
                f.write(combined_code)

            # 実行
            run_cmd = [self.dotnet_path, 'run', '--nologo']
            if work_dir or temp_dir in self._initialized_dirs:
                run_cmd.append('--no-restore')

            result = subprocess.run(
                run_cmd,
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                return {"success": True, "stdout": result.stdout}
            else:
                exception_info = self._parse_runtime_exception(result.stdout + result.stderr)
                return {
                    "success": False,
                    "error_type": "RUNTIME_EXCEPTION",
                    "exception": exception_info,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }

        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def _parse_runtime_exception(self, output: str) -> Dict[str, Any]:
        """生成ラッパーのJSON診断を取得する。"""
        marker = "__RUNTIME_JSON__"
        for line in output.splitlines():
            if not line.startswith(marker):
                continue
            try:
                payload = json.loads(line[len(marker):])
            except json.JSONDecodeError:
                break
            return {
                "type": payload.get("type") or "UnknownException",
                "message": payload.get("message") or "",
                "stack_trace": payload.get("stackTrace") or "",
                "raw": output,
            }
        return {"type": "UnknownException", "message": "詳細はstderrを確認してください"}

    def verify_runtime(self, source_code: str, test_code: str, dependencies: List[Dict[str, str]] = None, has_side_effects: bool = False) -> Dict[str, Any]:
        """旧来の dotnet test 方式 (xUnitテストを実行)"""
        if has_side_effects:
            return {
                "success": False,
                "error_type": "SIDE_EFFECT_EXECUTION_BLOCKED",
                "message": (
                    "Runtime verification requires an explicit external sandbox "
                    "for side-effecting code."
                ),
                "summary": {"total": 0, "passed": 0, "failed": 0},
            }
        temp_dir = tempfile.mkdtemp(prefix="cs_test_")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            def _extract_namespace(code: str) -> str | None:
                for line in code.splitlines():
                    text = line.strip()
                    if text.startswith("namespace "):
                        ns = text[len("namespace "):].strip()
                        if ns.endswith("{"):
                            ns = ns[:-1].strip()
                        return ns if ns else None
                return None

            # 1. 依存関係の構築
            dep_items = ""
            dependencies = dependencies or []
            for dep in dependencies:
                name = dep.get("name")
                version = dep.get("version", "*")
                if name:
                    dep_items += f'    <PackageReference Include="{name}" Version="{version}" />\n'

            # 2. プロジェクトファイルの作成
            target_csproj = os.path.join(temp_dir, "TestProject.csproj")
            with open(target_csproj, "w", encoding="utf-8") as f:
                f.write(f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <IsPackable>false</IsPackable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.8.0" />
    <PackageReference Include="xunit" Version="2.6.1" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.5.3" />
    <PackageReference Include="NSubstitute" Version="5.1.0" />
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
{dep_items}
  </ItemGroup>
</Project>""")

            # 3. ソースコードとテストコードの書き出し
            processed_source = source_code
            with open(os.path.join(temp_dir, "Source.cs"), "w", encoding="utf-8") as f:
                f.write(processed_source)
            ns_name = _extract_namespace(processed_source)
            if ns_name and f"using {ns_name};" not in test_code:
                test_code = f"using {ns_name};\n" + test_code
            with open(os.path.join(temp_dir, "Tests.cs"), "w", encoding="utf-8") as f:
                f.write(test_code)

            # 4. テスト実行
            results_directory = os.path.join(temp_dir, "TestResults")
            result = subprocess.run(
                [
                    self.dotnet_path,
                    'test',
                    '--nologo',
                    '--verbosity',
                    'normal',
                    '--logger',
                    'trx;LogFileName=results.trx',
                    '--results-directory',
                    results_directory,
                ],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            # 5. TRX XMLから結果を構造的に取得
            trx_path = os.path.join(results_directory, "results.trx")
            total = 0
            passed = 0
            failed = 0
            failures = []
            if os.path.exists(trx_path):
                root = ET.parse(trx_path).getroot()
                counters = root.find(".//{*}Counters")
                if counters is not None:
                    total = int(counters.get("total", "0"))
                    passed = int(counters.get("passed", "0"))
                    failed = int(counters.get("failed", "0"))
                for test_result in root.findall(".//{*}UnitTestResult"):
                    if test_result.get("outcome") != "Failed":
                        continue
                    error_info = test_result.find(".//{*}ErrorInfo")
                    message = ""
                    stack_trace = ""
                    if error_info is not None:
                        message_node = error_info.find("{*}Message")
                        stack_node = error_info.find("{*}StackTrace")
                        message = message_node.text if message_node is not None else ""
                        stack_trace = stack_node.text if stack_node is not None else ""
                    failures.append({
                        "test_name": test_result.get("testName"),
                        "message": message,
                        "stack_trace": stack_trace,
                    })
            elif result.returncode != 0:
                failed = 1
                total = 1

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "summary": {"total": total, "passed": passed, "failed": failed},
                "failures": failures,
            }

        except Exception as e:
            return {"success": False, "message": str(e)}
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
