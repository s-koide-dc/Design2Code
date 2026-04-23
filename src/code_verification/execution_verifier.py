# -*- coding: utf-8 -*-
import os
import subprocess
import re
import tempfile
import shutil
from typing import Dict, List, Any, Optional
from .compilation_verifier import CompilationVerifier

class ExecutionVerifier(CompilationVerifier):
    """
    生成されたコードを実際に実行して動作を検証するクラス。
    """

    def __init__(self, config_manager=None):
        super().__init__(config_manager)

    def run_and_capture(self, source_code: str, method_name: str, args: List[Any] = None, work_dir: str = None, assertion_goals: List[Dict[str, Any]] = None, dependencies: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """コードを単純実行可能な形式にラップして実行し、実行時エラーを捕捉する"""
        temp_dir = work_dir or tempfile.mkdtemp(prefix="cs_exec_")
        os.makedirs(temp_dir, exist_ok=True)
        
        assertion_goals = assertion_goals or []
        dependencies = dependencies or []
        
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

            def _extract_primary_class_name(code: str) -> str | None:
                for line in code.splitlines():
                    text = line.strip()
                    if " class " in text:
                        after = text.split(" class ", 1)[1].strip()
                        token = after.split()[0] if after else ""
                        token = token.split("{", 1)[0].split(":", 1)[0].strip()
                        if token:
                            return token
                return None

            class_name = _extract_primary_class_name(source_code) or "GeneratedProcessor"
            ns_name = _extract_namespace(source_code)
            qualified_name = f"{ns_name}.{class_name}" if ns_name else class_name

            # GeneratedProcessor のコンストラクタ引数を解析 (簡易版)
            ctor_match = re.search(r"public GeneratedProcessor\((.*?)\)", source_code)
            ctor_args_code = ""
            if ctor_match:
                params_str = ctor_match.group(1).strip()
                if params_str:
                    params = params_str.split(",")
                    arg_list = []
                    for p in params:
                        p = p.strip()
                        if not p: continue
                        p_parts = p.split(" ")
                        p_type = p_parts[0]
                        arg_list.append(f"NSubstitute.Substitute.For<{p_type}>()")
                    ctor_args_code = ", ".join(arg_list)

            # Method Arg Parsing (省略 - 既存ロジック維持)
            method_args_code = []
            m_match = re.search(fr"public .*? {method_name}\((.*?)\)", source_code)
            
            # 戻り値の型を特定（async 修飾を考慮）
            return_type = "void"
            for line in source_code.splitlines():
                text = line.strip()
                if "public " not in text or f"{method_name}(" not in text:
                    continue
                tokens = text.replace("(", " ").replace(")", " ").split()
                if method_name not in tokens:
                    continue
                try:
                    idx = tokens.index(method_name)
                except ValueError:
                    continue
                if idx <= 1:
                    continue
                sig_tokens = tokens[1:idx]
                sig_tokens = [t for t in sig_tokens if t != "async"]
                if sig_tokens:
                    return_type = sig_tokens[-1]
                break

            if m_match:
                from src.advanced_tdd.dummy_factory import DummyDataFactory
                factory = DummyDataFactory()
                
                class_chunks = re.split(r"public class (\w+)", source_code)
                if len(class_chunks) > 1:
                    for i in range(1, len(class_chunks), 2):
                        cls_name = class_chunks[i]
                        body = class_chunks[i+1]
                        props = re.findall(r"public ([\w<>\[\]]+) (\w+) \{ get; set; \}", body)
                        for p_type, p_name in props:
                            factory._add_learned_prop(cls_name, p_name)

                m_params = m_match.group(1).split(",")
                for p in m_params:
                    p = p.strip()
                    if not p: continue
                    p_parts = p.split(" ")
                    p_type = p_parts[0]
                    val = factory.generate_instantiation(p_type)
                    method_args_code.append(val)
            
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
                    Console.WriteLine($"[ASSERTION_FAILURE] Expected all items to have {var_hint or 'value'} {cs_op} {expected}");
                    Environment.Exit(2);
                }}"""
                        else:
                            assertion_code += f"""
                if (!(result {cs_op} {expected})) {{
                    Console.WriteLine($"[ASSERTION_FAILURE] Expected result {cs_op} {expected}, but got {{result}}");
                    Environment.Exit(2);
                }}"""
                    elif goal['type'] == 'string' and goal['operator'] == 'Contains':
                        expected = goal['expected_value']
                        if is_collection:
                            assertion_code += f"""
                if (!result.Any(item => item.ToString().Contains("{expected}"))) {{
                    Console.WriteLine($"[ASSERTION_FAILURE] Expected at least one item to contain '{expected}'");
                    Environment.Exit(2);
                }}"""
                        else:
                            assertion_code += f"""
                if (!result.ToString().Contains("{expected}")) {{
                    Console.WriteLine($"[ASSERTION_FAILURE] Expected result to contain '{expected}', but got {{result}}");
                    Environment.Exit(2);
                }}"""

            # ファイルモックの作成 (簡易版)
            for goal in assertion_goals:
                step = goal.get('original_step', "").lower()
                m = re.search(r'([\w\.]+\.json)', step)
                if m:
                    filename = m.group(1)
                    filepath = os.path.join(temp_dir, filename)
                    if not os.path.exists(filepath):
                        # ダミーJSON生成
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write('[{"Name": "Item1", "Price": 2000, "Stock": 2}, {"Name": "Item2", "Price": 500, "Stock": 10}]')
                        print(f"[ExecutionVerifier] Created mock file: {filename}")

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
            
            Console.WriteLine($"[RUNTIME_ERROR] {{actualEx.GetType().FullName}}: {{actualEx.Message}}");
            Console.WriteLine(actualEx.StackTrace);
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
        """スタックトレースから例外型とメッセージを抽出"""
        # アサーション失敗の優先検知
        assert_match = re.search(r"\[ASSERTION_FAILURE\] (.*)", output)
        if assert_match:
            return {
                "type": "AssertionFailure",
                "message": assert_match.group(1).strip(),
                "raw": output
            }

        tag_match = re.search(r"\[RUNTIME_ERROR\] ([\w\.]+): (.*)", output)
        if tag_match:
            return {
                "type": tag_match.group(1),
                "message": tag_match.group(2).split('\n')[0],
                "raw": output
            }
        match = re.search(r"Unhandled exception\. ([\w\.]+): (.*)", output)
        if match:
            return {
                "type": match.group(1),
                "message": match.group(2).split('\n')[0],
                "raw": output
            }
        ex_match = re.search(r"([\w\.]+Exception): (.*)", output)
        if ex_match:
            return {
                "type": ex_match.group(1),
                "message": ex_match.group(2).split('\n')[0],
                "raw": output
            }
        return {"type": "UnknownException", "message": "詳細はstderrを確認してください"}

    def verify_runtime(self, source_code: str, test_code: str, dependencies: List[Dict[str, str]] = None, has_side_effects: bool = False) -> Dict[str, Any]:
        """旧来の dotnet test 方式 (xUnitテストを実行)"""
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
            # 副作用フラグがあれば、危険なAPIを無効化する
            processed_source = source_code
            if has_side_effects:
                # 簡易的な無効化ロジック (File.WriteAllText 等をコメントアウト)
                processed_source = re.sub(r'(File\.(?:Write|Append|Delete|Move|Copy|Create).*?;)', r'// [MOCKED] \1', source_code)
                processed_source = re.sub(r'(Directory\.(?:Create|Delete|Move).*?;)', r'// [MOCKED] \1', processed_source)

            with open(os.path.join(temp_dir, "Source.cs"), "w", encoding="utf-8") as f:
                f.write(processed_source)
            ns_name = _extract_namespace(processed_source)
            if ns_name and f"using {ns_name};" not in test_code:
                test_code = f"using {ns_name};\n" + test_code
            with open(os.path.join(temp_dir, "Tests.cs"), "w", encoding="utf-8") as f:
                f.write(test_code)

            # 4. テスト実行
            result = subprocess.run(
                [self.dotnet_path, 'test', '--nologo', '--verbosity', 'normal'],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            # 5. 結果のパース
            from src.csharp_operations.csharp_operations import CSharpOperations
            # 簡易的なパース (本来は CSharpOperations を使うべきだが、ここではモックなしで動くように簡易化)
            summary_match = re.search(r'Total:\s*(\d+).*?Passed:\s*(\d+).*?Failed:\s*(\d+)', result.stdout + result.stderr, re.DOTALL)
            if not summary_match:
                # 日本語ロケール対応
                summary_match = re.search(r'合計:\s*(\d+).*?成功:\s*(\d+).*?失敗:\s*(\d+)', result.stdout + result.stderr, re.DOTALL)
            
            passed = int(summary_match.group(2)) if summary_match else (1 if result.returncode == 0 else 0)
            failed = int(summary_match.group(3)) if summary_match else (0 if result.returncode == 0 else 1)
            total = int(summary_match.group(1)) if summary_match else passed + failed

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "summary": {"total": total, "passed": passed, "failed": failed}
            }

        except Exception as e:
            return {"success": False, "message": str(e)}
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
