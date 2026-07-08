# -*- coding: utf-8 -*-
# src/tdd_operations/tdd_operations.py

import os
import shutil
import subprocess
import logging
from datetime import datetime
from typing import Dict, Any
from collections import defaultdict

class TDDOperations:
    """TDDおよびコード修正の操作を担当する独立モジュール"""
    
    def __init__(self, action_executor):
        self.ae = action_executor
        self.logger = logging.getLogger(__name__)

    def _relativize_path(self, path_text: str) -> str:
        if not path_text:
            return ""
        try:
            if os.path.isabs(path_text):
                return os.path.relpath(path_text, self.ae.workspace_root)
        except ValueError:
            return path_text
        return path_text

    def _build_dialogue_metadata(self, phase: str, **kwargs) -> Dict[str, Any]:
        metadata = {"phase": phase}
        metadata.update({k: v for k, v in kwargs.items() if v not in [None, "", [], {}]})
        return metadata

    def _build_failure_analysis_context(self, failure: Dict[str, Any]) -> Dict[str, Any]:
        analysis_context: Dict[str, Any] = {}
        explicit_root_cause = failure.get("root_cause")
        if isinstance(explicit_root_cause, str) and explicit_root_cause:
            analysis_context["root_cause"] = explicit_root_cause
        explicit_exception_type = failure.get("exception_type")
        if isinstance(explicit_exception_type, str) and explicit_exception_type:
            analysis_context["exception_type"] = explicit_exception_type
        return analysis_context

    def _extract_build_error_details(self, raw_output: str):
        details = []
        for line in raw_output.splitlines():
            parsed = self._parse_build_error_line(line)
            if not parsed:
                continue
            details.append({
                "method": "BuildError",
                "file": parsed["file"],
                "line": parsed["line"],
                "location": f"{parsed['file']}:line {parsed['line']}",
                "message": f"{parsed['code']}: {parsed['message']}",
                "stack_trace": line,
                "is_build_error": True,
            })
        return details

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
        if not separator:
            return None
        code = code.strip()
        if not code.startswith("CS") or not code[2:].isdigit():
            return None
        return {
            "file": file_path,
            "line": int(line_col[0]),
            "code": code,
            "message": message.strip(),
        }

    @staticmethod
    def _strip_line_suffix(path_text: str) -> str:
        stripped = path_text.strip()
        separator_index = stripped.rfind(":")
        if separator_index < 0:
            return stripped
        suffix = stripped[separator_index + 1:].strip()
        prefix = stripped[:separator_index].rstrip()
        if suffix.isdigit():
            return prefix
        line_marker = "line "
        if suffix.startswith(line_marker) and suffix[len(line_marker):].strip().isdigit():
            return prefix
        return stripped

    def _validate_test_fix_behavior(self, target_files) -> Dict[str, Any]:
        project_paths = set()
        for target_file in target_files:
            current_dir = os.path.dirname(os.path.abspath(target_file))
            while current_dir:
                projects = [
                    os.path.join(current_dir, name)
                    for name in os.listdir(current_dir)
                    if name.endswith(".csproj")
                ]
                if len(projects) == 1:
                    project_paths.add(projects[0])
                    break
                if len(projects) > 1:
                    return {
                        "valid": False,
                        "error": f"対象プロジェクトを一意に解決できません: {current_dir}",
                    }
                if current_dir == self.ae.workspace_root:
                    break
                parent_dir = os.path.dirname(current_dir)
                if parent_dir == current_dir:
                    break
                current_dir = parent_dir

        if not project_paths:
            return {
                "valid": False,
                "error": "修正後テストを実行するプロジェクトが見つかりません。",
            }

        for project_path in sorted(project_paths):
            try:
                result = subprocess.run(
                    ["dotnet", "test", project_path, "--no-restore", "--nologo"],
                    cwd=os.path.dirname(project_path),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=120,
                    shell=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return {
                    "valid": False,
                    "error": f"修正後テストの実行に失敗しました: {type(exc).__name__}",
                }
            if result.returncode != 0:
                output = (result.stdout or "") + (result.stderr or "")
                return {
                    "valid": False,
                    "error": output[-4000:],
                }
        return {"valid": True, "error": ""}

    def _load_failure_project_analysis(
        self,
        context: Dict[str, Any],
        parameters: Dict[str, Any],
    ):
        project_path = self.ae._get_entity_value(parameters.get("project_path"))
        if not project_path:
            for past_context in reversed(context.get("history", [])):
                past_plan = past_context.get("plan", {}).get("parameters", {})
                project_path = self.ae._get_entity_value(
                    past_plan.get("project_path")
                )
                if project_path:
                    break
                past_result = past_context.get("action_result", {})
                project_path = past_result.get("target_name")
                if project_path:
                    break
        if not project_path:
            return None
        analysis_context = {
            "session_id": context.get("session_id", "failure_analysis"),
            "analysis": {"entities": {}},
        }
        result_context = self.ae.csharp_ops.analyze_csharp(
            analysis_context,
            {"filename": project_path},
        )
        result = result_context.get("action_result", {})
        if result.get("status") != "success":
            return None
        return result.get("analysis")

    def analyze_test_failure(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """テスト失敗を分析して修正提案を生成"""
        parameters = context.get("plan", {}).get("parameters", {})
        
        # --- NEW: Auto-populate from action_result or history if available ---
        # Search for test results in current context or history
        last_result = context.get("action_result", {})
        summary = last_result.get("test_summary", {})
        
        error_details = summary.get("error_details", [])
        
        # Build error handling: if no error_details but we have build_failed and raw_output
        if not error_details and last_result.get("build_failed") and last_result.get("raw_output"):
            raw_output = last_result["raw_output"]
            error_details.extend(self._extract_build_error_details(raw_output))

        if not error_details:
            # Check history
            history = context.get("history", [])
            for past_context in reversed(history):
                past_result = past_context.get("action_result", {})
                
                # Check for execution errors
                if past_result.get("test_summary", {}).get("error_details"):
                    summary = past_result["test_summary"]
                    error_details = summary.get("error_details", [])
                    break
                
                # Check for build errors in history
                if past_result.get("build_failed") and past_result.get("raw_output"):
                    raw_output = past_result["raw_output"]
                    error_details.extend(self._extract_build_error_details(raw_output))
                    if error_details:
                        break

        all_suggestions = []
        all_analyses = []
        project_analysis = self._load_failure_project_analysis(
            context,
            parameters,
        )
        
        for failure in error_details:
            test_method = failure.get("method", "")

            test_failure_data = {
                'test_file': failure.get("file", failure.get("location", "")),
                'test_method': test_method,
                'error_type': "compile_error" if failure.get("is_build_error") else "assertion_failure",
                'error_message': failure.get("message", ""),
                'stack_trace': failure.get("stack_trace", ""),
                'line_number': failure.get("line"),
                'analysis_context': self._build_failure_analysis_context(failure),
                'target_code': {
                    'file': "",
                    'method': "",
                    'current_implementation': "",
                    'analysis_results': None,
                    'target_method_analysis': None,
                }
            }
            
            try:
                result = self.ae.advanced_tdd_support.analyze_and_fix_test_failure(
                    test_failure_data,
                    roslyn_data=project_analysis,
                )
                if result['status'] == 'success':
                    all_analyses.append(result['analysis'])
                    # Tag each suggestion with the test method it fixes
                    for sug in result['fix_suggestions']:
                        sug['test_method'] = test_method
                        all_suggestions.append(sug)
            except Exception as e:
                self.ae.log_manager.log_event("analyze_test_failure_error", {"error": str(e), "test_method": test_method}, level="ERROR")
                self.logger.error("Error analyzing %s: %s", test_method, e)

        if not all_suggestions:
            # Collect some debug info from failure objects if any
            debug_info = f" (Failure count: {len(error_details)})"
            if all_analyses:
                 debug_info += f" (Analyses: {len(all_analyses)}, first status: {all_analyses[0].get('status')})"

            primary_failure = error_details[0] if error_details else {}
            primary_target = self._relativize_path(primary_failure.get("file", ""))
            
            context["action_result"] = {
                "status": "error",
                "message": f"{len(error_details)}件の失敗を分析しましたが、修正案を生成できませんでした。{debug_info}",
                "dialogue_metadata": self._build_dialogue_metadata(
                    "failure_analysis",
                    failure_count=len(error_details),
                    suggestion_count=0,
                    primary_error_type=primary_failure.get("error_type") or primary_failure.get("message", ""),
                    primary_target_file=primary_target,
                    next_action="inspect_failure_context"
                ),
                "failure_summary": {
                    "failure_count": len(error_details),
                    "suggestion_count": 0,
                    "primary_target_file": primary_target
                }
            }
            return context

        # Generate summary message
        message_parts = [
            f"一括テスト失敗分析が完了しました。",
            f"分析した失敗数: {len(error_details)}件",
            f"生成された修正提案数: {len(all_suggestions)}個",
            "\n主要な修正提案:"
        ]
        
        for i, suggestion in enumerate(all_suggestions[:5], 1): # Show top 5
            applicability = "自動適用可" if suggestion.get('auto_applicable', True) else "手動確認"
            message_parts.append(f"{i}. [{suggestion.get('test_method', '不明')}] {suggestion['description']} ({applicability})")

        if len(all_suggestions) > 5:
            message_parts.append(f"...他 {len(all_suggestions) - 5} 件の提案があります。")

        primary_target_file = ""
        primary_conversation_hint = ""
        primary_reason = ""
        primary_recommended_action = ""
        primary_target_summary = ""
        if all_suggestions:
            primary_target_file = self._relativize_path(all_suggestions[0].get("target_file", ""))
            primary_conversation_hint = all_suggestions[0].get("conversation_hint", "")
            primary_reason = all_suggestions[0].get("reason", "")
            primary_recommended_action = all_suggestions[0].get("recommended_action", "")
            primary_target_summary = all_suggestions[0].get("target_summary", "")
        if not primary_target_file:
            for failure in error_details:
                primary_target_file = self._relativize_path(failure.get("file", ""))
                if primary_target_file:
                    break

        failed_test_names = [failure.get("method", "") for failure in error_details if failure.get("method")]
        primary_error_type = ""
        if all_analyses:
            summary = all_analyses[0].get("analysis_summary", {})
            primary_error_type = summary.get("error_type") or all_analyses[0].get("root_cause", "")
            if not primary_target_file:
                primary_target_file = self._relativize_path(summary.get("target_file", ""))

        context["action_result"] = {
            "status": "success",
            "message": "\n".join(message_parts),
            "analysis_result": {
                "status": "success",
                "analyses": all_analyses,
                "fix_suggestions": all_suggestions
            },
            "dialogue_metadata": self._build_dialogue_metadata(
                "failure_analysis",
                failure_count=len(error_details),
                suggestion_count=len(all_suggestions),
                failed_test_names=failed_test_names[:3],
                primary_target_file=primary_target_file,
                primary_error_type=primary_error_type,
                primary_conversation_hint=primary_conversation_hint,
                primary_reason=primary_reason,
                primary_recommended_action=primary_recommended_action,
                primary_target_summary=primary_target_summary,
                next_action="apply_code_fix"
            ),
            "failure_summary": {
                "failure_count": len(error_details),
                "suggestion_count": len(all_suggestions),
                "failed_test_names": failed_test_names,
                "primary_target_file": primary_target_file,
                "primary_error_type": primary_error_type,
                "primary_conversation_hint": primary_conversation_hint,
                "primary_reason": primary_reason,
                "primary_recommended_action": primary_recommended_action,
                "primary_target_summary": primary_target_summary
            }
        }
        return context
    
    def execute_goal_driven_tdd(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """ゴール駆動型TDDを実行"""
        parameters = context.get("plan", {}).get("parameters", {})
        
        goal_data = {
            'description': self.ae._get_entity_value(parameters.get("goal_description", "")),
            'acceptance_criteria': parameters.get("acceptance_criteria", []),
            'priority': self.ae._get_entity_value(parameters.get("priority", "medium")),
            'estimated_effort': self.ae._get_entity_value(parameters.get("estimated_effort", "1 hour")),
            'constraints': {
                'language': self.ae._get_entity_value(parameters.get("language", "csharp")),
                'test_framework': self.ae._get_entity_value(parameters.get("test_framework", "xunit")),
                'coverage_target': parameters.get("coverage_target", 80),
                'max_complexity': parameters.get("max_complexity", 5)
            },
            'context': {
                'existing_code': self.ae._get_entity_value(parameters.get("existing_code", "")),
                'existing_tests': self.ae._get_entity_value(parameters.get("existing_tests", ""))
            }
        }
        
        try:
            result = self.ae.advanced_tdd_support.execute_goal_driven_tdd(goal_data)
            
            if result['status'] == 'success':
                cycle_results = result['tdd_cycle_results']
                artifacts = result['generated_artifacts']
                metrics = result['quality_metrics']
                goal_description = goal_data['description']
                
                message_parts = [
                    f"ゴール駆動型TDDが完了しました。",
                    f"目標: {goal_description}",
                    f"実行イテレーション: {cycle_results['total_iterations']}回",
                    f"成功率: {cycle_results['success_rate']:.1%}",
                    f"実行時間: {cycle_results['total_time_seconds']:.1f}秒"
                ]
                
                test_count = len(artifacts.get('tests', []))
                code_count = len(artifacts.get('code', []))
                message_parts.extend([
                    f"\n生成された成果物:",
                    f"- テストケース: {test_count}個",
                    f"- コード実装: {code_count}個"
                ])
                
                message_parts.extend([
                    f"\n品質メトリクス:",
                    f"- 推定カバレッジ: {metrics['estimated_coverage']}%",
                    f"- 循環複雑度: {metrics['cyclomatic_complexity']}",
                    f"- 技術的負債: {metrics['technical_debt']}"
                ])
                
                recommendations = result.get('recommendations', [])
                if recommendations:
                    message_parts.append(f"\n推奨事項:")
                    for i, rec in enumerate(recommendations[:3], 1):
                        message_parts.append(f"{i}. {rec}")
                
                context["action_result"] = {
                    "status": "success",
                    "message": "\n".join(message_parts),
                    "tdd_result": result,
                    "target_name": goal_description,
                    "dialogue_metadata": self._build_dialogue_metadata(
                        "goal_driven_tdd",
                        goal_description=goal_description,
                        iteration_count=cycle_results.get("total_iterations"),
                        success_rate=cycle_results.get("success_rate"),
                        generated_code_count=code_count,
                        generated_test_count=test_count,
                        next_action="review_generated_artifacts"
                    ),
                    "tdd_summary": {
                        "goal_description": goal_description,
                        "iteration_count": cycle_results.get("total_iterations"),
                        "success_rate": cycle_results.get("success_rate"),
                        "generated_code_count": code_count,
                        "generated_test_count": test_count
                    }
                }
            else:
                context["action_result"] = {
                    "status": "error",
                    "message": f"ゴール駆動型TDD実行に失敗しました: {result.get('error', '不明なエラー')}",
                    "target_name": goal_data['description'],
                    "dialogue_metadata": self._build_dialogue_metadata(
                        "goal_driven_tdd",
                        goal_description=goal_data['description'],
                        next_action="inspect_tdd_error"
                    )
                }
                
        except Exception as e:
            self.ae.log_manager.log_event("tdd_execution_error", {"message": f"ゴール駆動型TDD実行中にエラーが発生: {e}"}, level="ERROR")
            context["action_result"] = {
                "status": "error",
                "message": f"ゴール駆動型TDD実行中にエラーが発生しました: {str(e)}",
                "dialogue_metadata": self._build_dialogue_metadata(
                    "goal_driven_tdd",
                    goal_description=goal_data.get('description', ''),
                    next_action="inspect_tdd_error"
                )
            }
        
        return context
    
    def apply_code_fix(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """コード修正提案を適用（一括適用対応）"""
        parameters = context.get("plan", {}).get("parameters", {})
        fix_id_requested = self.ae._get_entity_value(parameters.get("fix_id", ""))
        backup_enabled = parameters.get("backup_enabled", True)
        
        # If fix_id_requested doesn't look like a real ID, treat as "all"
        known_id_prefixes = ("fix_", "heal_", "manual_", "calc_", "nullcheck_")
        is_valid_id = fix_id_requested and fix_id_requested.startswith(known_id_prefixes)
        if fix_id_requested and not is_valid_id:
            fix_id_requested = "all"
        
        if not fix_id_requested:
            fix_id_requested = "all"

        target_suggestions = []
        analysis_result_context = {}
        history = context.get("history", [])
        
        # 適用対象の提案を特定
        found_suggestions = False
        for i, past_context in enumerate(reversed(history)):
            past_result = past_context.get("action_result", {})
            past_analysis = past_result.get("analysis_result", {})
            suggestions = past_analysis.get("fix_suggestions", [])
            
            if suggestions:
                analysis_result_context = past_analysis
                if fix_id_requested and fix_id_requested.lower() != "all":
                    # 特定のIDのみ
                    match = next((s for s in suggestions if s["id"] == fix_id_requested), None)
                    if match:
                        target_suggestions = [match]
                        found_suggestions = True
                else:
                    # すべての提案を一括対象にする
                    target_suggestions = suggestions
                    found_suggestions = True
                
                if found_suggestions:
                    break

        if not target_suggestions:
            context["action_result"] = {
                "status": "error",
                "message": f"適用可能な修正提案が見つかりません（リクエストID: {fix_id_requested or 'ALL'}）。"
            }
            return context

        applied_count = 0
        failed_count = 0
        files_modified = set()
        backups = {} # target_path -> backup_path
        package_failures = []

        try:
            # ファイルごとに修正をグループ化して適用
            fixes_by_file = defaultdict(list)
            
            for sug in target_suggestions:
                # ターゲットファイルの特定
                if not sug.get("auto_applicable", True):
                    failed_count += 1
                    continue

                target_file = sug.get("target_file")
                if not target_file:
                    # 歴史から探索
                    for analysis in analysis_result_context.get("analyses", []):
                        test_context = analysis.get("analysis_details", {}).get("test_context", {})
                        if test_context.get("test_method") == sug.get("test_method"):
                            if sug.get("type") in ["test_arrange_fix", "test_self_healing"]:
                                # Look for the Test file in stack trace locations
                                locs = analysis.get("analysis_details", {}).get("stack_trace_analysis", {}).get("file_locations", [])
                                for loc in locs:
                                    f = loc.get("file", "")
                                    if 'Test' in f or f.endswith('Tests.cs'):
                                        target_file = f
                                        break
                            
                            if not target_file:
                                # Check if it's an SUT fix (has target_code) or Test fix
                                if analysis.get("target_code", {}).get("file"):
                                    target_file = analysis["target_code"]["file"]
                                else:
                                    target_file = test_context.get("test_file")
                            
                            # Remove line suffix
                            if target_file:
                                target_file = self._strip_line_suffix(target_file)
                            break
                
                if target_file:
                    is_cs_file = target_file.endswith('.cs')
                    if sug.get("type") == "add_package":
                        fixes_by_file[target_file or "PROJECT_CONFIG"].append(sug)
                    elif is_cs_file:
                        fixes_by_file[target_file].append(sug)
                    else:
                        failed_count += 1
                else:
                    failed_count += 1

            for target_file, suggestions in fixes_by_file.items():
                target_path = self.ae._safe_join(target_file) if target_file != "PROJECT_CONFIG" else None
                
                # 特殊ケース: add_package はコマンド実行
                if any(s.get("type") == "add_package" for s in suggestions):
                    for sug in suggestions:
                        if sug.get("type") == "add_package":
                            package_name = sug["suggested_code"]
                            
                            # .csproj を探す (近傍からルートへ)
                            search_dir = os.path.dirname(target_path) if target_path else self.ae.workspace_root
                            csproj_files = []
                            curr = search_dir
                            while curr:
                                if os.path.exists(curr):
                                    csproj_files = [f for f in os.listdir(curr) if f.endswith('.csproj')]
                                    if csproj_files: break
                                if curr == self.ae.workspace_root: break
                                next_dir = os.path.dirname(curr)
                                if next_dir == curr: break
                                curr = next_dir
                            
                            if csproj_files:
                                try:
                                    proj_dir = curr
                                    subprocess.run(['dotnet', 'add', 'package', package_name], cwd=proj_dir, check=True, capture_output=True)
                                    applied_count += 1
                                    files_modified.add(os.path.relpath(os.path.join(proj_dir, csproj_files[0]), self.ae.workspace_root))
                                except (
                                    OSError,
                                    subprocess.CalledProcessError,
                                    subprocess.TimeoutExpired,
                                ) as exc:
                                    failed_count += 1
                                    package_failures.append({
                                        "package": package_name,
                                        "error_type": type(exc).__name__,
                                    })
                            else:
                                failed_count += 1
                    
                    if all(s.get("type") == "add_package" for s in suggestions):
                        continue

                # 通常のファイル修正 (行置換/挿入)
                if not target_path or not os.path.exists(target_path):
                    failed_count += len([s for s in suggestions if s.get("type") != "add_package"])
                    continue

                if backup_enabled and target_path not in backups:
                    backup_path = target_path + ".bak"
                    shutil.copy2(target_path, backup_path)
                    backups[target_path] = backup_path

                with open(target_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # 行番号情報を付与して降順ソート
                suggestions_with_lines = []
                for sug in suggestions:
                    if sug.get("type") == "add_package": continue
                    line_num = sug.get("line_number")
                    if not line_num:
                        for analysis in analysis_result_context.get("analyses", []):
                            if analysis.get("analysis_details", {}).get("test_context", {}).get("test_method") == sug.get("test_method"):
                                line_num = analysis.get("analysis_details", {}).get("stack_trace_analysis", {}).get("primary_location", {}).get("line")
                                break
                    if line_num:
                        suggestions_with_lines.append((line_num, sug))
                    else:
                        failed_count += 1

                suggestions_with_lines.sort(key=lambda x: x[0], reverse=True)

                for line_num, sug in suggestions_with_lines:
                    if 0 < line_num <= len(lines):
                        indent = lines[line_num-1][:len(lines[line_num-1]) - len(lines[line_num-1].lstrip())]
                        if sug.get("type") == "test_self_healing":
                            lines[line_num-1] = f"{indent}{sug['suggested_code']}\n"
                        elif sug.get("type") == "add_using":
                            lines.insert(0, f"using {sug['suggested_code']};\n")
                        elif sug.get("type") == "null_validation":
                            found_brace = False
                            for offset in range(0, 5):
                                idx = line_num - 1 + offset
                                if idx < len(lines) and "{" in lines[idx]:
                                    lines.insert(idx + 1, f"{indent}    {sug['suggested_code']}\n")
                                    found_brace = True
                                    break
                            if not found_brace:
                                lines.insert(line_num, f"{indent}    {sug['suggested_code']}\n")
                        elif sug.get("type") in ["add_async", "parameter_fix"]:
                            lines[line_num-1] = f"{indent}{sug['suggested_code']}\n"
                        else:
                            lines.insert(line_num, f"{indent}{sug['suggested_code']}\n")
                        applied_count += 1
                    else:
                        failed_count += 1

                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write("".join(lines))
                files_modified.add(target_file)

            if package_failures and applied_count == 0 and not files_modified:
                context["action_result"] = {
                    "status": "error",
                    "message": "NuGetパッケージの追加に失敗しました。",
                    "package_failures": package_failures,
                    "dialogue_metadata": self._build_dialogue_metadata(
                        "code_fix",
                        skipped_count=failed_count,
                        reason="パッケージ追加コマンドを完了できませんでした。",
                        recommended_action="inspect_package_failure",
                        next_action="inspect_package_failure",
                    ),
                }
                return context

            # バリデーション
            all_valid = True
            error_msg = ""
            for target_file in files_modified:
                target_path = os.path.join(self.ae.workspace_root, target_file)
                val_result = self.validate_code_syntax(target_path, target_file)
                if not val_result['valid']:
                    all_valid = False
                    error_msg = val_result['error']
                    break

            test_fix_types = {"test_arrange_fix", "test_self_healing"}
            requires_test_validation = any(
                suggestion.get("type") in test_fix_types
                for suggestion in target_suggestions
            )
            if all_valid and requires_test_validation:
                test_targets = [
                    os.path.join(self.ae.workspace_root, target_file)
                    for target_file in files_modified
                    if target_file.endswith(".cs")
                ]
                behavioral_result = self._validate_test_fix_behavior(test_targets)
                if not behavioral_result["valid"]:
                    all_valid = False
                    error_msg = behavioral_result["error"]
            
            should_rollback = not all_valid
            has_add_package = any(s.get("type") == "add_package" for s in target_suggestions)
            if has_add_package and not all_valid:
                should_rollback = False

            if applied_count > 0 and (all_valid or not should_rollback):
                modified_files_list = sorted(self._relativize_path(path) for path in files_modified)
                context["action_result"] = {
                    "status": "success",
                    "message": f"一括コード修正を完了しました。\n適用成功: {applied_count}件, スキップ: {failed_count}件\n修正ファイル: {', '.join(files_modified)}",
                    "applied_fixes": {"count": applied_count, "files": list(files_modified)},
                    "package_failures": package_failures,
                    "generated_files": modified_files_list,
                    "target_name": modified_files_list[0] if modified_files_list else None,
                    "dialogue_metadata": self._build_dialogue_metadata(
                        "code_fix",
                        applied_count=applied_count,
                        skipped_count=failed_count,
                        modified_files=modified_files_list,
                        reason="修正提案をコードへ反映し、構文検証を通過しました。",
                        recommended_action="run_related_tests",
                        target_summary=modified_files_list[0] if modified_files_list else "",
                        next_action="run_related_tests"
                    )
                }
            elif should_rollback:
                for t_path, b_path in backups.items():
                    shutil.copy2(b_path, t_path)
                context["action_result"] = {
                    "status": "error",
                    "message": f"修正後の検証でエラーが発生したためロールバックしました。\n詳細: {error_msg}",
                    "dialogue_metadata": self._build_dialogue_metadata(
                        "code_fix",
                        applied_count=applied_count,
                        skipped_count=failed_count,
                        reason="修正後の検証で不整合が見つかったため、変更を巻き戻しました。",
                        recommended_action="inspect_validation_error",
                        next_action="inspect_validation_error"
                    )
                }
        except Exception as e:
            for t_path, b_path in backups.items():
                if os.path.exists(b_path): shutil.copy2(b_path, t_path)
            context["action_result"] = {
                "status": "error",
                "message": f"一括修正適用中に予期せぬエラーが発生しました: {e}",
                "dialogue_metadata": self._build_dialogue_metadata(
                    "code_fix",
                    reason="修正適用処理そのものが失敗しました。",
                    recommended_action="inspect_fix_application_error",
                    next_action="inspect_fix_application_error"
                )
            }
        
        return context
    
    def validate_code_syntax(self, file_path: str, relative_path: str) -> Dict[str, Any]:
        """コードの構文を検証"""
        try:
            if relative_path.endswith('.cs'):
                result = subprocess.run(['dotnet', 'build', '--verbosity', 'quiet'], cwd=os.path.dirname(file_path), capture_output=True, text=True, timeout=30)
                return {'valid': result.returncode == 0, 'error': (result.stdout + "\n" + result.stderr).strip()}
            elif relative_path.endswith('.py'):
                import ast
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        ast.parse(f.read())
                        return {'valid': True}
                    except SyntaxError as e:
                        return {'valid': False, 'error': str(e)}
            return {'valid': True}
        except Exception as e:
            return {'valid': False, 'error': str(e)}
