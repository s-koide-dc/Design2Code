# -*- coding: utf-8 -*-
import os
import json
import subprocess
import tempfile
import logging
import re
from typing import List, Dict, Any, Optional

class DynamicHarvester:
    """
    オンデマンドで C# の型からメソッド定義を収穫するクラス。
    リフレクションを使用して標準ライブラリや指定されたアセンブリからメソッド情報を抽出する。
    """

    def __init__(self, config_manager=None):
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.capability_map = self._load_capability_map()
        
        # 自然言語クエリから型へのマッピング辞書 (簡易版)
        self.query_map = {
            "read file": "System.IO.File",
            "write file": "System.IO.File",
            "file exists": "System.IO.File",
            "delete file": "System.IO.File",
            "directory": "System.IO.Directory",
            "folder": "System.IO.Directory",
            "path": "System.IO.Path",
            "json": "System.Text.Json.JsonSerializer",
            "http": "System.Net.Http.HttpClient",
            "math": "System.Math",
            "date": "System.DateTime",
            "time": "System.DateTime",
            "guid": "System.Guid",
            "base64": "System.Convert",
            "md5": "System.Security.Cryptography.MD5",
            "sha256": "System.Security.Cryptography.SHA256",
            "environment": "System.Environment",
            "task": "System.Threading.Tasks.Task",
            "thread": "System.Threading.Thread",
            "average": "System.Linq.Enumerable",
            "sum": "System.Linq.Enumerable",
            "count": "System.Linq.Enumerable",
            "max": "System.Linq.Enumerable",
            "min": "System.Linq.Enumerable",
            "filter": "System.Linq.Enumerable",
            "select": "System.Linq.Enumerable"
        }

    def search_standard_library(self, query: str) -> List[Dict[str, Any]]:
        """クエリに基づいて標準ライブラリからメソッドを収穫する"""
        query_lower = query.lower()
        target_types = set()
        
        # 簡易キーワードマッチ
        for key, val in self.query_map.items():
            if key in query_lower:
                target_types.add(val)
        
        results = []
        for type_name in target_types:
            methods = self.harvest_from_type(type_name)
            if methods:
                self.logger.info(f"Harvested {len(methods)} methods from {type_name}")
                results.extend(methods)
                
        return results

    def harvest_from_type(self, type_name: str) -> List[Dict[str, Any]]:
        """指定された型の public static メソッドを収穫する"""
        inspector_code = self._generate_inspector_code(type_name)
        
        try:
            with tempfile.TemporaryDirectory_() as temp_dir: # Using custom context manager wrapper later if needed, but standard is fine
                pass # Using plain tempfile logic below
        except: pass

        # 手動で一時ディレクトリ作成 (Python < 3.8 backport logic safe)
        temp_dir = tempfile.mkdtemp(prefix="harvester_")
        try:
            # プロジェクト作成
            csproj = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
</Project>"""
            
            with open(os.path.join(temp_dir, "Inspector.csproj"), "w", encoding="utf-8") as f:
                f.write(csproj)
                
            with open(os.path.join(temp_dir, "Program.cs"), "w", encoding="utf-8") as f:
                f.write(inspector_code)

            # 実行
            cmd = ["dotnet", "run"]
            result = subprocess.run(
                cmd, 
                cwd=temp_dir, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode != 0:
                self.logger.warning(f"Harvesting failed for {type_name}: {result.stderr}")
                return []
                
            # 出力 (JSON) をパース
            # Dotnet run might output some build info, so pick the last line assuming it's JSON
            output_lines = result.stdout.strip().split('\n')
            json_str = ""
            for line in reversed(output_lines):
                if line.strip().startswith("[") or line.strip().startswith("{"):
                    json_str = line
                    break
            
            if not json_str: 
                return []

            methods_data = json.loads(json_str)
            return self._convert_to_store_format(methods_data, type_name)

        except Exception as e:
            self.logger.error(f"Error harvesting {type_name}: {e}")
            return []
        finally:
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except: pass

    def harvest_from_package(self, package_name: str, version: str) -> List[Dict[str, Any]]:
        """NuGet パッケージの DLL からメソッドを収穫する"""
        from src.utils.nuget_client import NuGetClient
        client = NuGetClient(self.config_manager)
        dlls = client.get_package_dlls(package_name, version)
        
        if not dlls:
            self.logger.warning(f"No DLLs found for package {package_name} {version}")
            return []
            
        # ツールパスの解決
        cli_path = os.path.join(os.getcwd(), "tools", "csharp", "MethodHarvesterCLI", "bin", "Debug", "net10.0", "MethodHarvesterCLI.exe")
        if not os.path.exists(cli_path):
            self.logger.error(f"MethodHarvesterCLI not found at {cli_path}")
            return []
             
        try:
            # 大量に DLL がある場合はコマンドライン長の制限に注意が必要だが、通常は数個
            cmd = [cli_path]
            map_path = self._get_map_path()
            if map_path:
                cmd += ["--map", map_path]
            cmd += dlls
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                self.logger.warning(f"MethodHarvesterCLI failed: {result.stderr}")
                return []
                
            data = json.loads(result.stdout)
            raw_methods = data.get("methods", [])
            
            # 形式変換 (MethodHarvesterCLI の出力はほぼ MethodStore 互換)
            converted = []
            for m in raw_methods:
                # 必要な正規化
                m["return_type"] = m.pop("returnType")
                if "isStatic" in m:
                    m["is_static"] = m.pop("isStatic")
                if "intent" not in m:
                    mapped = self._lookup_map_value(m.get("class", ""), m.get("name", ""), "intent")
                    if isinstance(mapped, str):
                        m["intent"] = mapped
                if "capabilities" not in m:
                    mapped = self._lookup_map_value(m.get("class", ""), m.get("name", ""), "capabilities")
                    if isinstance(mapped, list):
                        m["capabilities"] = mapped
                
                # Tier Handling (MethodHarvesterCLI now provides Tier, but we ensure it's mapped to tier)
                if "Tier" in m:
                    m["tier"] = m.pop("Tier")
                
                if "tier" not in m:
                    cls_name = m.get("class", "")
                    m["tier"] = 1 if (cls_name.startswith("System.") or cls_name.startswith("Common.")) else 2

                # 追加のメタデータ
                if "tags" not in m: m["tags"] = []
                m["tags"].append("harvested-nuget")
                m["tags"].append(package_name.lower())
                
                # 名前空間
                if "." in m["class"]:
                    m["namespace"] = m["class"].rsplit(".", 1)[0]
                
                converted.append(m)
            
            return converted

        except Exception as e:
            self.logger.error(f"Error harvesting from package {package_name}: {e}")
            return []

    def _convert_to_store_format(self, raw_methods: List[Dict[str, Any]], type_name: str) -> List[Dict[str, Any]]:
        """リフレクション結果をMethodStore形式に変換"""
        converted = []
        for m in raw_methods:
            # MethodStore形式
            # {
            #   "id": ..., "name": ..., "class": ..., "code": ..., "definition": ...,
            #   "params": [{"name": "...", "type": "..."}], "return_type": "...",
            #   "dependencies": [], "tags": [], "usings": []
            # }
            
            method_name = m["Name"]
            params = m["Parameters"] 
            ret_type = m["ReturnType"]
            
            params_store = [{"name": p["Name"], "type": p["Type"], "role": p.get("Role")} for p in params]
            
            # 呼び出しコードのテンプレート作成
            args_str = ", ".join([f"{{{p['Name']}}}" for p in params])
            code_template = f"{type_name}.{method_name}({args_str})"
            
            # ソースコード定義はリフレクションでは取れないため、ダミー（シグネチャのみ）
            params_sig = ", ".join([f"{p['Type']} {p['Name']}" for p in params])
            definition = f"public static {ret_type} {method_name}({params_sig}) {{ /* Compiled Library */ }}"
            
            # 依存関係
            ns = "System"
            if "." in type_name:
                ns = type_name.rsplit(".", 1)[0]
            
            mapped_intent = self._lookup_map_value(type_name, method_name, "intent")
            mapped_caps = self._lookup_map_value(type_name, method_name, "capabilities")
            entry = {
                "id": f"harvested_{type_name}_{method_name}",
                "name": method_name,
                "class": type_name,
                "return_type": ret_type,
                "params": params_store,
                "code": code_template,
                "definition": definition,
                "namespace": ns,
                "code_body": definition,
                "usings": [ns],
                "dependencies": [], # Standard libraries usually handled by default references
                "tags": ["harvested", "standard-lib"],
                "intent": mapped_intent if isinstance(mapped_intent, str) else None,
                "capabilities": mapped_caps if isinstance(mapped_caps, list) else [],
                "has_side_effects": False, # 安全側に倒す、あるいは名前で判定
                "tier": 1 if (type_name.startswith("System.") or type_name.startswith("Common.")) else 2
            }
            converted.append(entry)
            
        return converted

    def _generate_inspector_code(self, type_name: str) -> str:
        """C# Inspector Code Generation"""
        return f"""
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text.Json;

public class Program
{{
    public static void Main()
    {{
        try
        {{
            string targetType = "{type_name}";
            Type t = Type.GetType(targetType);
            
            // Try standard assemblies if not found directly
            if (t == null) t = typeof(string).Assembly.GetType(targetType); // System.Private.CoreLib
            if (t == null) t = Assembly.Load("System.Runtime").GetType(targetType);
            if (t == null) t = Assembly.Load("System.Console").GetType(targetType);
            if (t == null) t = Assembly.Load("System.IO.FileSystem").GetType(targetType);
            if (t == null) t = Assembly.Load("System.Net.Http").GetType(targetType);
            if (t == null) t = Assembly.Load("System.Text.Json").GetType(targetType);
            if (t == null) t = Assembly.Load("System.Linq").GetType(targetType);
            if (t == null) t = Assembly.Load("System.Security.Cryptography.Algorithms").GetType(targetType);

            if (t == null) 
            {{
                Console.WriteLine("[]"); // Empty list
                return;
            }}

            var methods = t.GetMethods(BindingFlags.Public | BindingFlags.Static)
                           .Where(m => !m.IsSpecialName) // Getters/Setters除外
                           .Select(m => new 
                           {{
                               Name = m.Name,
                               ReturnType = GetScrubbedTypeName(m.ReturnType),
                               Parameters = m.GetParameters().Select(p => new {{ Name = p.Name, Type = GetScrubbedTypeName(p.ParameterType) }}).ToList()
                           }})
                           .ToList();

            string json = JsonSerializer.Serialize(methods);
            Console.WriteLine(json);
        }}
        catch 
        {{
            Console.WriteLine("[]");
        }}
    }}

    static string GetScrubbedTypeName(Type t)
    {{
        if (t == typeof(void)) return "void";
        if (t == typeof(int)) return "int";
        if (t == typeof(string)) return "string";
        if (t == typeof(bool)) return "bool";
        if (t.IsGenericType)
        {{
            string name = t.Name.Substring(0, t.Name.IndexOf('`'));
            string args = string.Join(", ", t.GetGenericArguments().Select(GetScrubbedTypeName));
            return $"{{name}}<{{args}}>";
        }}
        return t.Name;
    }}
}}
        """

    def _get_map_path(self) -> Optional[str]:
        path = os.path.join(os.getcwd(), "resources", "method_capability_map.json")
        return path if os.path.exists(path) else None

    def _load_capability_map(self) -> Dict[str, Any]:
        path = self._get_map_path()
        if not path:
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            methods = data.get("methods", {}) if isinstance(data, dict) else {}
            normalized = {}
            for k, v in methods.items():
                if not isinstance(k, str):
                    continue
                key = k.strip()
                if not key:
                    continue
                normalized[key] = v
                normalized[key.lower()] = v
            return {"methods": normalized}
        except Exception:
            return {}

    def _lookup_map_value(self, class_full_name: str, method_name: str, key: str) -> Any:
        if not self.capability_map:
            return None
        full = f"{class_full_name}.{method_name}"
        methods = self.capability_map.get("methods", {})
        entry = methods.get(full) or methods.get(full.lower())
        if not isinstance(entry, dict):
            return None
        return entry.get(key)
