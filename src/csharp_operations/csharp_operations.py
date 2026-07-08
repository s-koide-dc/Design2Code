# -*- coding: utf-8 -*- 
# src/csharp_operations/csharp_operations.py

import os
import json
import subprocess
import hashlib
import shutil
import tempfile
from typing import Dict, Any, Tuple

class CSharpOperations:
    """C#関連の操作を担当する独立モジュール"""
    
    def __init__(self, action_executor):
        self.ae = action_executor

    def _analysis_fingerprint(self, target_path: str, analyzer_project: str) -> str:
        digest = hashlib.sha256()
        excluded_directories = {".git", ".vs", "bin", "obj", "logs"}
        accepted_suffixes = {".cs", ".csproj", ".sln", ".slnx", ".props", ".targets"}
        roots = [
            os.path.dirname(target_path) if os.path.isfile(target_path) else target_path,
            os.path.dirname(analyzer_project),
        ]
        files = []
        for root_index, root in enumerate(roots):
            for current_root, directories, filenames in os.walk(root):
                directories[:] = sorted(
                    directory
                    for directory in directories
                    if directory not in excluded_directories
                )
                for filename in sorted(filenames):
                    if os.path.splitext(filename)[1].lower() in accepted_suffixes:
                        files.append((root_index, os.path.join(current_root, filename)))
        for root_index, file_path in sorted(set(files)):
            relative_path = os.path.relpath(file_path, roots[root_index])
            digest.update(f"{root_index}:{relative_path}".encode("utf-8"))
            with open(file_path, "rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
        return digest.hexdigest()

    def _is_complete_analysis(self, output_path: str) -> bool:
        return (
            os.path.isfile(os.path.join(output_path, "manifest.json"))
            and os.path.isdir(os.path.join(output_path, "details"))
        )

    def _remove_analysis_workdir(self, work_path: str, output_base: str) -> None:
        resolved_work = os.path.abspath(work_path)
        resolved_base = os.path.abspath(output_base)
        if (
            os.path.commonpath([resolved_work, resolved_base]) == resolved_base
            and os.path.basename(resolved_work).startswith(".analysis-work-")
            and os.path.isdir(resolved_work)
        ):
            shutil.rmtree(resolved_work)

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
        fingerprint = self._analysis_fingerprint(path, analyzer_project)
        out_dir_name = f"analysis_{fingerprint[:24]}"
        cache_out = os.path.join(output_base, out_dir_name)
        cache_hit = self._is_complete_analysis(cache_out)
        temp_out = (
            cache_out
            if cache_hit
            else tempfile.mkdtemp(prefix=".analysis-work-", dir=output_base)
        )

        try:
            manifest_path = os.path.join(temp_out, "manifest.json")
            if cache_hit:
                result = subprocess.CompletedProcess([], 0, "", "")
            else:
                cmd = ["dotnet", "run", "--project", analyzer_project, "--", path, temp_out]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
            
            if result.returncode == 0:
                if not cache_hit and self._is_complete_analysis(temp_out):
                    try:
                        os.replace(temp_out, cache_out)
                        temp_out = cache_out
                    except OSError:
                        if self._is_complete_analysis(cache_out):
                            self._remove_analysis_workdir(temp_out, output_base)
                            temp_out = cache_out
                            cache_hit = True
                        else:
                            raise
                    manifest_path = os.path.join(temp_out, "manifest.json")
                # Parse output directory
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
                        "output_path": temp_out,
                        "cache_hit": cache_hit,
                    }
                else:
                    self._remove_analysis_workdir(temp_out, output_base)
                    context["action_result"] = {"status": "error", "message": f"解析結果 (manifest.json) が生成されませんでした。\n{result.stdout}"}
            else:
                self._remove_analysis_workdir(temp_out, output_base)
                context["action_result"] = {"status": "error", "message": f"解析ツールの実行に失敗しました (code {result.returncode}):\n{result.stderr}"}
        except Exception as e:
            self._remove_analysis_workdir(temp_out, output_base)
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
                build_output = (build_result.stdout or "") + (build_result.stderr or "")
                build_errors = self._extract_build_error_details(build_output)
                summary_err = "\n".join(
                    error["raw_line"] for error in build_errors[:3]
                )
                if not summary_err:
                    summary_err = build_output[-2000:]
                context["action_result"] = {
                    "status": "error",
                    "message": f"ビルドエラーが発生したためテストを実行できません。\n{summary_err}",
                    "build_failed": True,
                    "raw_output": build_output,
                    "build_errors": build_errors,
                }
                return context
        except Exception as e:
            context["action_result"] = {"status": "error", "message": f"ビルド試行中にエラー: {e}"}
            return context

        # 2. Run test with log file
        log_file = os.path.join(self.ae.workspace_root, "logs", "last_dotnet_test.log")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        cmd = ["dotnet", "test", abs_project_path, "--no-build"]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                errors="replace",
            )
            output = result.stdout + result.stderr
            with open(log_file, 'w', encoding='utf-8', errors='replace') as f:
                f.write(output)
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

    def _extract_build_error_details(self, output: str):
        errors = []
        for line in output.splitlines():
            parsed = self._parse_build_error_line(line)
            if parsed:
                errors.append(parsed)
        return errors

    @staticmethod
    def _parse_build_error_line(line: str):
        stripped = line.strip()
        marker = "): error "
        marker_index = stripped.find(marker)
        if marker_index < 0:
            return None
        location = stripped[:marker_index]
        open_paren = location.rfind("(")
        if open_paren < 0:
            return None
        file_path = location[:open_paren].strip()
        line_col = location[open_paren + 1:].split(",", 1)
        if not file_path or not line_col or not line_col[0].isdigit():
            return None
        rest = stripped[marker_index + len(marker):]
        code, separator, message = rest.partition(":")
        code = code.strip()
        if not separator or not code.startswith("CS") or not code[2:].isdigit():
            return None
        return {
            "file": file_path,
            "line": int(line_col[0]),
            "code": code,
            "message": message.strip(),
            "raw_line": stripped,
        }

    def parse_dotnet_test_result(self, output: str) -> Dict[str, Any]:
        summary = {
            "failed_tests": [], "failed_count": 0, "passed_count": 0, "total_count": 0,
            "error_details": [], "summary_line": "テスト結果を解析できませんでした。"
        }
        output_clean = self._strip_ansi_sequences(output)
        lines = output_clean.splitlines()

        for index, line in enumerate(lines):
            method_name = self._extract_failed_method_name(line)
            if not method_name or method_name in summary["failed_tests"]:
                continue
            chunk_lines = self._collect_failure_chunk(lines, index + 1)
            error_info = self._parse_failure_chunk(method_name, chunk_lines)
            summary["error_details"].append(error_info)
            summary["failed_tests"].append(method_name)

        summary["failed_count"] = len(summary["failed_tests"])
        for line in lines:
            counts = self._parse_test_count_line(line)
            if counts:
                summary.update(counts)
                break
        summary["summary_line"] = f"Total: {summary['total_count']}, Passed: {summary['passed_count']}, Failed: {summary['failed_count']}"
        return summary

    @staticmethod
    def _strip_ansi_sequences(text: str) -> str:
        result = []
        index = 0
        while index < len(text):
            char = text[index]
            if char != "\x1b":
                result.append(char)
                index += 1
                continue
            index += 1
            if index < len(text) and text[index] == "[":
                index += 1
                while index < len(text) and not ("@" <= text[index] <= "~"):
                    index += 1
                if index < len(text):
                    index += 1
            elif index < len(text):
                index += 1
        return "".join(result)

    @staticmethod
    def _extract_failed_method_name(line: str) -> str:
        stripped = line.strip()
        marker = "[FAIL]"
        if marker in stripped:
            before_marker = stripped.split(marker, 1)[0].strip()
            if "]" in before_marker:
                before_marker = before_marker.rsplit("]", 1)[-1].strip()
            tokens = before_marker.split()
            return tokens[-1] if tokens and "." in tokens[-1] else ""

        for prefix in ("Failed ", "失敗 "):
            if stripped.startswith(prefix):
                payload = stripped[len(prefix):].strip()
                first_token = payload.split()[0] if payload.split() else ""
                return first_token if "." in first_token else ""
        return ""

    def _collect_failure_chunk(self, lines, start_index: int):
        chunk = []
        for line in lines[start_index:]:
            if self._extract_failed_method_name(line):
                break
            chunk.append(line)
        return chunk

    def _parse_failure_chunk(self, method_name: str, chunk_lines):
        error_info = {"method": method_name}
        message_lines = []
        stack_lines = []
        destination = message_lines
        saw_label = False

        for line in chunk_lines:
            stripped = line.strip()
            if stripped in {"Error Message:", "エラー メッセージ:", "Error Message：", "エラー メッセージ："}:
                destination = message_lines
                saw_label = True
                continue
            if stripped in {"Stack Trace:", "スタック トレース:", "Stack Trace：", "スタック トレース："}:
                destination = stack_lines
                saw_label = True
                continue
            if not saw_label and (stripped.startswith("at ") or " in " in stripped):
                destination = stack_lines
            destination.append(line)

        message = "\n".join(message_lines).strip()
        stack_trace = "\n".join(stack_lines).strip()
        if message:
            error_info["message"] = message
            self._add_structured_exception_context(error_info)
        if stack_trace:
            error_info["stack_trace"] = stack_trace
        return error_info

    @staticmethod
    def _parse_test_count_line(line: str) -> Dict[str, int]:
        counts = {}
        label_map = {
            "Total": "total_count",
            "合計": "total_count",
            "Passed": "passed_count",
            "成功数": "passed_count",
            "成功": "passed_count",
            "合格": "passed_count",
            "Failed": "failed_count",
            "失敗数": "failed_count",
            "失敗": "failed_count",
        }
        for label, key in label_map.items():
            value = CSharpOperations._extract_count_after_label(line, label)
            if value is not None:
                counts[key] = value
        return counts if "total_count" in counts else {}

    @staticmethod
    def _extract_count_after_label(line: str, label: str):
        label_index = line.find(label)
        if label_index < 0:
            return None
        colon_indices = [
            idx for idx in (line.find(":", label_index), line.find("：", label_index))
            if idx >= 0
        ]
        if not colon_indices:
            return None
        colon_index = min(colon_indices)
        payload = line[colon_index + 1:].lstrip()
        digits = []
        for char in payload:
            if not char.isdigit():
                if digits:
                    break
                continue
            digits.append(char)
        return int("".join(digits)) if digits else None

    def _add_structured_exception_context(self, error_info: Dict[str, Any]) -> None:
        message = error_info.get("message", "")
        if not isinstance(message, str) or not message:
            return
        first_line = message.splitlines()[0].strip()
        exception_type = first_line.partition(':')[0].strip()
        if not exception_type:
            return
        error_info["exception_type"] = exception_type
        root_cause_by_exception = {
            "System.NullReferenceException": "missing_test_data",
            "NullReferenceException": "missing_test_data",
        }
        root_cause = root_cause_by_exception.get(exception_type)
        if root_cause:
            error_info["root_cause"] = root_cause

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
