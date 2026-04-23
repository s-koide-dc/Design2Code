# -*- coding: utf-8 -*- 
# src/csharp_operations/csharp_operations.py

import os
import json
import subprocess
import re
import time
from typing import Dict, Any, Tuple

class CSharpOperations:
    """C#関連の操作を担当する独立モジュール"""
    
    def __init__(self, action_executor):
        self.ae = action_executor

    def analyze_csharp(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        filename = self.ae._get_entity_value(parameters.get("filename"))
        if not filename:
             context["action_result"] = {"status": "error", "message": "解析対象のファイル名が指定されていません。"}
             return context
             
        path = self.ae._safe_join(filename)
        if not path or not os.path.exists(path):
             context["action_result"] = {"status": "error", "message": "ファイルが見つかりません。"}
             return context

        # Calculate project root relative to this file's location (src/csharp_operations/csharp_operations.py)
        current_file_dir = os.path.dirname(__file__)
        project_root = os.path.abspath(os.path.join(current_file_dir, "..", ".."))
        analyzer_project = os.path.join(project_root, "tools", "csharp", "MyRoslynAnalyzer", "MyRoslynAnalyzer.csproj")
        
        # Create a persistent output directory based on filename/session to allow subsequent queries
        if os.path.abspath(self.ae.workspace_root) == project_root:
            output_base = os.path.join(project_root, "logs", "analysis_output")
        else:
            output_base = os.path.join(self.ae.workspace_root, "logs", "analysis_output")
            
        os.makedirs(output_base, exist_ok=True)
        session_id = context.get("session_id", "default")
        out_dir_name = f"analysis_{session_id}_{int(time.time())}"
        temp_out = os.path.join(output_base, out_dir_name)
        os.makedirs(temp_out, exist_ok=True)

        try:
            cmd = ["dotnet", "run", "--project", analyzer_project, "--", path, temp_out]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
            
            if result.returncode == 0:
                # Parse output directory
                manifest_path = os.path.join(temp_out, "manifest.json")
                if os.path.exists(manifest_path):
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest = json.load(f)
                    
                    details_by_id = {}
                    details_dir = os.path.join(temp_out, "details")
                    if os.path.exists(details_dir):
                        for detail_file in os.listdir(details_dir):
                            if detail_file.endswith(".json"):
                                with open(os.path.join(details_dir, detail_file), 'r', encoding='utf-8') as f:
                                    detail = json.load(f)
                                    details_by_id[detail.get("id")] = detail
                    
                    analysis_data = {
                        "manifest": manifest,
                        "details_by_id": details_by_id,
                        "classes": [],
                        "project_metrics": manifest.get("projectMetrics")
                    }
                    
                    class_summary = []
                    for obj in manifest.get("objects", []):
                        if obj.get("type") == "Class":
                            obj_id = obj.get("id")
                            detail = details_by_id.get(obj_id, {})
                            
                            class_info = {
                                "name": obj.get("fullName"),
                                "methods": [m.get("name") for m in detail.get("methods", [])],
                                "file_path": obj.get("filePath") ,
                                "start_line": obj.get("startLine") ,
                                "end_line": obj.get("endLine") ,
                                "summary": obj.get("summary")
                            }
                            analysis_data["classes"].append(class_info)
                            
                            m_names = class_info["methods"]
                            if m_names:
                                class_summary.append(f"{class_info['name']} (methods: {', '.join(m_names)}, lines: {class_info['start_line']}-{class_info['end_line']})")
                            else:
                                class_summary.append(f"{class_info['name']} (lines: {class_info['start_line']}-{class_info['end_line']})")
                    
                    message = f"C# ファイル '{filename}' の解析が完了しました。"
                    if class_summary:
                        message += " 抽出されたクラス: " + "; ".join(class_summary)
                    
                    project_metrics = manifest.get("projectMetrics")
                    if project_metrics:
                        message += (f"\nプロジェクトメトリクス: 合計CC={project_metrics.get('totalCyclomaticComplexity')}, "
                                    f"最大CC={project_metrics.get('maxCyclomaticComplexity')}, "
                                    f"平均CC={project_metrics.get('averageCyclomaticComplexity'):.2f}, "
                                    f"総行数={project_metrics.get('totalLineCount')}")
                    
                    # Ensure it's available for history resolution in subsequent turns
                    context.setdefault("analysis", {})
                    context["analysis"].setdefault("entities", {})
                    context["analysis"]["entities"]["output_path"] = {"value": temp_out, "confidence": 1.0}

                    context["action_result"] = {
                        "status": "success",
                        "message": message,
                        "analysis": analysis_data,
                        "output_path": temp_out # Store for subsequent queries
                    }
                else:
                    context["action_result"] = {"status": "error", "message": f"解析結果 (manifest.json) が生成されませんでした。\n{result.stdout}"}
            else:
                context["action_result"] = {"status": "error", "message": f"解析ツールの実行に失敗しました (code {result.returncode}):\n{result.stderr}"}
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"C# 解析中にエラーが発生しました: {e}")
            
        return context

    def run_dotnet_test(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        project_path = self.ae._get_entity_value(parameters.get("project_path"))
        
        # Smart resolution
        generated_proj = os.path.join(self.ae.workspace_root, "tests", "generated", "GeneratedTests.csproj")
        if not project_path or project_path == "." or "MyRoslynAnalyzer" in project_path:
            if os.path.exists(generated_proj):
                project_path = generated_proj
            elif not project_path:
                project_path = "."
        
        abs_project_path = self.ae._safe_join(project_path)
        if not abs_project_path:
             context["action_result"] = {"status": "error", "message": "無効なパスです。"}
             return context

        # 1. Clean and Build check
        clean_cmd = ["dotnet", "clean", abs_project_path]
        build_cmd = ["dotnet", "build", abs_project_path]
        try:
            subprocess.run(clean_cmd, capture_output=True, text=True, timeout=10, check=False)
            build_result = subprocess.run(build_cmd, capture_output=True, text=True, timeout=30, check=False, errors="replace")
            if build_result.returncode != 0:
                error_lines = build_result.stdout.splitlines() + build_result.stderr.splitlines()
                summary_err = "\n".join([line for line in error_lines if "error" in line][:3])
                context["action_result"] = {
                    "status": "error",
                    "message": f"ビルドエラーが発生したためテストを実行できません。\n{summary_err}",
                    "build_failed": True,
                    "raw_output": build_result.stdout
                }
                return context
        except Exception as e:
            context["action_result"] = {"status": "error", "message": f"ビルド試行中にエラー: {e}"}
            return context

        # 2. Run test with log file
        log_file = os.path.join(self.ae.workspace_root, "logs", "last_dotnet_test.log")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        cmd = f'dotnet test "{abs_project_path}" --no-build > "{log_file}" 2>&1'
        try:
            result = subprocess.run(cmd, shell=True, timeout=60, check=False)
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                output = f.read()
            summary = self.parse_dotnet_test_result(output)
            status = "success" if result.returncode == 0 and summary.get("failed_count", 0) == 0 and summary.get("total_count", 0) > 0 else "error"
            
            msg = f"dotnet test の実行が完了しました (Status: {status.upper()})\n"
            msg += f"サマリー: {summary.get('summary_line', '情報なし')}\n"
            context["action_result"] = {
                "status": status,
                "message": msg,
                "test_summary": summary,
                "raw_output": output
            }
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"dotnet test 実行中にエラーが発生しました: {e}")
        return context

    def parse_dotnet_test_result(self, output: str) -> Dict[str, Any]:
        summary = {
            "failed_tests": [], "failed_count": 0, "passed_count": 0, "total_count": 0,
            "error_details": [], "summary_line": "テスト結果を解析できませんでした。"
        }
        ansi_escape = re.compile(r'\x1B(?:[@-Z\-_]|[[0-?]*[ -/]*[@-~])')
        output_clean = ansi_escape.sub('', output)
        chunks = re.split(r'\s+(?:Failed|失敗)\s+([\w\.]+\.[\w\.]+)\s+\[', output_clean)
        
        if len(chunks) > 1:
            for i in range(1, len(chunks), 2):
                method_name = chunks[i]
                chunk_body = chunks[i+1] if i+1 < len(chunks) else ""
                if method_name in summary["failed_tests"]: continue
                error_info = {"method": method_name}
                msg_match = re.search(r'(?:エラー メッセージ|Error Message)\s*[:：]\s*(.*?)(?:スタック トレース|Stack Trace|at |in )', chunk_body, re.DOTALL)
                if msg_match: error_info["message"] = msg_match.group(1).strip()
                
                trace_match = re.search(r'(?:スタック トレース|Stack Trace)\s*[:：]\s*(.*)', chunk_body, re.DOTALL)
                if trace_match: error_info["stack_trace"] = trace_match.group(1).strip()
                elif 'at ' in chunk_body or 'in ' in chunk_body:
                    # Fallback: extract from 'at ' onwards
                    fallback_trace_match = re.search(r'((?:at |in ).*)', chunk_body, re.DOTALL)
                    if fallback_trace_match: error_info["stack_trace"] = fallback_trace_match.group(1).strip()
                summary["error_details"].append(error_info)
                summary["failed_tests"].append(method_name)

        summary["failed_count"] = len(summary["failed_tests"])
        for line in output_clean.splitlines():
            l_total = re.search(r'(?:合計|Total)\s*[:：]\s*(\d+)', line)
            l_passed = re.search(r'(?:成功数|成功|合格|Passed)\s*[:：]\s*(\d+)', line)
            l_failed = re.search(r'(?:失敗数|失敗|Failed)\s*[:：]\s*(\d+)', line)
            if l_total:
                summary["total_count"] = int(l_total.group(1))
                if l_passed: summary["passed_count"] = int(l_passed.group(1))
                if l_failed: summary["failed_count"] = int(l_failed.group(1))
                break
        summary["summary_line"] = f"Total: {summary['total_count']}, Passed: {summary['passed_count']}, Failed: {summary['failed_count']}"
        return summary

    def load_csharp_analysis_results(self, output_path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        full_output_path = self.ae._safe_join(output_path)
        if not full_output_path or not os.path.isdir(full_output_path):
            raise ValueError(f"Output path '{output_path}' is invalid or does not exist.")
        manifest_path = os.path.join(full_output_path, "manifest.json")
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)
        details_dir = os.path.join(full_output_path, "details")
        all_detail_objects_by_id = {}
        if os.path.isdir(details_dir):
            for filename in os.listdir(details_dir):
                if filename.endswith(".json"):
                    with open(os.path.join(details_dir, filename), 'r', encoding='utf-8') as f:
                        detail_obj = json.load(f)
                        all_detail_objects_by_id[detail_obj["id"]] = detail_obj
        return manifest_data, all_detail_objects_by_id

    def recursively_find_callers(self, target_method_id: str, all_detail_objects_by_id: Dict[str, Any], visited_methods: set) -> set:
        if isinstance(target_method_id, dict): target_method_id = target_method_id.get("id")
        if not target_method_id or target_method_id in visited_methods: return set()
        visited_methods.add(target_method_id)
        current_callers = set()
        method_data = None
        for det in all_detail_objects_by_id.values():
            for m in det.get("methods", []):
                if m.get("id") == target_method_id:
                    method_data = m
                    break
            if method_data: break
        if not method_data: return set()
        for caller_entry in method_data.get("calledBy", []):
            caller_id = caller_entry.get("id") if isinstance(caller_entry, dict) else caller_entry
            for det in all_detail_objects_by_id.values():
                for m in det.get("methods", []):
                    if m.get("id") == caller_id:
                        caller_full_name = f"{det.get('fullName')}.{m.get('name')}"
                        if caller_full_name not in current_callers:
                            current_callers.add(caller_full_name)
                            current_callers.update(self.recursively_find_callers(caller_id, all_detail_objects_by_id, visited_methods))
                        break
        return current_callers

    def query_csharp_analysis_results(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        output_path = self.ae._get_entity_value(parameters.get("output_path"))
        query_type = self.ae._get_entity_value(parameters.get("query_type"))
        target_name = self.ae._get_entity_value(parameters.get("target_name"))
        if target_name: target_name = target_name.strip()

        requires_target_name = query_type in ["details", "class_summary", "impact_scope_method", "impact_scope_class", "method_calls", "method_summary", "called_by", "method_metrics"]
        if not output_path or not query_type or (requires_target_name and not target_name):
            context["action_result"] = {"status": "error", "message": "必要なパラメータが不足しています。"}
            return context

        try:
            manifest, details_by_id = self.load_csharp_analysis_results(output_path)
            target_detail_obj = None
            target_method_obj = None 

            if requires_target_name:
                t_lower = target_name.lower()
                # 1. Match Class
                target_manifest_obj = next((obj for obj in manifest.get("objects", []) if obj["fullName"] == target_name or obj["fullName"].lower().endswith("." + t_lower) or obj["fullName"].lower() == t_lower), None)
                if target_manifest_obj:
                    target_detail_obj = details_by_id.get(target_manifest_obj.get("id"))
                
                # 2. Match Method (ClassName.MethodName)
                if not target_method_obj and "." in target_name:
                    parts = target_name.rsplit('.', 1)
                    c_part, m_part = parts[0].lower(), parts[1].lower()
                    for det in details_by_id.values():
                        fn = det.get("fullName", "").lower()
                        if fn == c_part or fn.endswith("." + c_part):
                            m_found = next((m for m in det.get("methods", []) if m["name"].lower() == m_part), None)
                            if m_found:
                                target_method_obj, target_detail_obj = m_found, det
                                break

                if not target_detail_obj and not target_method_obj:
                    context["action_result"] = {"status": "error", "message": f"ターゲット '{target_name}' が見つかりませんでした。"}
                    return context

            result_message = ""
            if query_type == "class_summary":
                if target_detail_obj and target_detail_obj.get("type", "").lower() in ["class", "object", "record"]:
                    summary = target_detail_obj.get("documentation", {}).get("summary", "要約なし")
                    remarks = target_detail_obj.get("documentation", {}).get("remarks", "")
                    result_message = f"クラス '{target_name}' のドキュメント要約:\n\n概要: {summary}\n\n備考: {remarks}"
                    context["action_result"] = {"status": "success", "message": result_message, "summary": summary, "remarks": remarks}
                else:
                    t_type = target_detail_obj.get("type") if target_detail_obj else "Unknown"
                    context["action_result"] = {"status": "error", "message": f"クエリタイプ 'class_summary' はクラスにのみ適用可能です。ターゲットは '{t_type}' です。"}
            
            elif query_type in ["method_calls", "method_summary", "called_by", "method_metrics"]:
                if target_method_obj:
                    if query_type == "method_calls":
                        calls = target_method_obj.get("calls", [])
                        called_names = []
                        for c_id_obj in calls:
                            cid = c_id_obj.get("id") if isinstance(c_id_obj, dict) else c_id_obj
                            for det in details_by_id.values():
                                found = next((m for m in det.get("methods", []) if m["id"] == cid), None)
                                if found:
                                    called_names.append(f"{det['fullName']}.{found['name']}")
                                    break
                        if called_names:
                            result_message = f"メソッド '{target_name}' が呼び出しているメソッド:\n" + "\n".join(called_names)
                            context["action_result"] = {"status": "success", "message": result_message, "called_methods": called_names}
                        else:
                            context["action_result"] = {"status": "success", "message": f"メソッド '{target_name}' は他のメソッドを呼び出していません。"}
                    elif query_type == "called_by":
                        calling_names = []
                        mid = target_method_obj["id"]
                        for det in details_by_id.values():
                            for m in det.get("methods", []):
                                if any((c.get("id") if isinstance(c, dict) else c) == mid for c in m.get("calls", [])):
                                    calling_names.append(f"{det['fullName']}.{m['name']}")
                        if calling_names:
                            result_message = f"メソッド '{target_name}' を呼び出しているメソッド:\n" + "\n".join(calling_names)
                            context["action_result"] = {"status": "success", "message": result_message, "calling_methods": calling_names}
                        else:
                            context["action_result"] = {"status": "success", "message": f"メソッド '{target_name}' を呼び出しているメソッドは見つかりませんでした。"}
                    elif query_type == "method_summary":
                        summary = target_method_obj.get("documentation", {}).get("summary", "要約なし")
                        remarks = target_method_obj.get("documentation", {}).get("remarks", "")
                        params = target_method_obj.get("documentation", {}).get("params", {})
                        p_str = ", ".join([f"{k}: {v}" for k, v in params.items()])
                        result_message = f"メソッド '{target_name}' のドキュメント要約:\n\n概要: {summary}\n\n備考: {remarks}\n\nパラメータ: {p_str}"
                        context["action_result"] = {"status": "success", "message": result_message, "summary": summary, "remarks": remarks, "params": params}
                    elif query_type == "method_metrics":
                        metrics = target_method_obj.get("metrics", {})
                        cc, lc = metrics.get("cyclomaticComplexity", 0), metrics.get("lineCount", 0)
                        bh = metrics.get("bodyHash", "N/A")
                        result_message = f"メソッド '{target_name}' のメトリクス:\n  CC: {cc}, Lines: {lc}, Hash: {bh}"
                        context["action_result"] = {
                            "status": "success", 
                            "message": result_message, 
                            "cyclomatic_complexity": cc, 
                            "line_count": lc,
                            "body_hash": bh
                        }
                else:
                    context["action_result"] = {"status": "error", "message": f"ターゲットメソッド '{target_name}' の詳細情報が見つかりませんでした。"}

            elif query_type == "impact_scope_method":
                if not target_method_obj:
                    context["action_result"] = {"status": "error", "message": f"メソッド '{target_name}' が見つかりませんでした。"}
                else:
                    impacted = self.recursively_find_callers(target_method_obj["id"], details_by_id, set())
                    if impacted:
                        result_message = f"メソッド '{target_name}' の影響範囲:\n" + "\n".join(sorted(list(impacted)))
                        context["action_result"] = {"status": "success", "message": result_message, "impacted_methods": sorted(list(impacted))}
                    else:
                        context["action_result"] = {"status": "success", "message": f"メソッド '{target_name}' の影響範囲は見つかりませんでした。"}

            elif query_type == "impact_scope_class":
                if not target_detail_obj:
                    context["action_result"] = {"status": "error", "message": f"クラス '{target_name}' が見つかりませんでした。"}
                else:
                    all_impacted = set()
                    for method in target_detail_obj.get("methods", []):
                        all_impacted.update(self.recursively_find_callers(method["id"], details_by_id, set()))
                    
                    if all_impacted:
                        result_message = f"クラス '{target_name}' の影響範囲:\n" + "\n".join(sorted(list(all_impacted)))
                        context["action_result"] = {"status": "success", "message": result_message, "impacted_methods": sorted(list(all_impacted))}
                    else:
                        context["action_result"] = {"status": "success", "message": f"クラス '{target_name}' の影響範囲は見つかりませんでした。"}

            elif query_type == "find_tests_for_methods":
                m_to_check = target_name.split(',') if isinstance(target_name, str) else target_name
                assoc_tests = []
                for m_full in m_to_check:
                    parts = m_full.rsplit('.', 1)
                    if len(parts) < 2: continue
                    c_short = parts[0].split('.')[-1]
                    for suffix in [f"{c_short}Tests", f"{c_short}Test"]:
                        t_obj = next((obj for obj in manifest["objects"] if obj["fullName"].endswith(suffix)), None)
                        if t_obj:
                            assoc_tests.append({"target_method": m_full, "test_class": t_obj["fullName"], "test_file": t_obj["filePath"]})
                            break
                context["action_result"] = {"status": "success", "associated_tests": assoc_tests}

            elif query_type == "unused_methods":
                all_decl, all_call = set(), set()
                for det in details_by_id.values():
                    for m in det.get("methods", []):
                        all_decl.add(m["id"])
                        for call in m.get("calls", []):
                            all_call.add(call.get("id") if isinstance(call, dict) else call)
                unused_ids = all_decl - all_call
                u_names = []
                for det in details_by_id.values():
                    for m in det.get("methods", []):
                        if m["id"] in unused_ids:
                            u_names.append(f"{det['fullName']}.{m['name']}")
                if u_names:
                    result_message = "未使用メソッド:\n" + "\n".join(u_names)
                    context["action_result"] = {"status": "success", "message": result_message, "unused_methods": u_names}
                else:
                    context["action_result"] = {"status": "success", "message": "未使用メソッドは見つかりませんでした。"}
            else:
                context["action_result"] = {"status": "error", "message": f"不明なクエリタイプ: '{query_type}'"}

        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"C#解析結果のクエリ中にエラーが発生しました: {e}")
            
        return context