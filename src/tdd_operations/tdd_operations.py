# -*- coding: utf-8 -*-
# src/tdd_operations/tdd_operations.py

import os
import shutil
import subprocess
import re
from datetime import datetime
from typing import Dict, Any
from collections import defaultdict

class TDDOperations:
    """TDDおよびコード修正の操作を担当する独立モジュール"""
    
    def __init__(self, action_executor):
        self.ae = action_executor

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
            # Extract C# build errors: file(line,col): error CSxxxx: message
            # Example: C:\path\file.cs(17,34): error CS1026: ) expected
            build_error_matches = re.finditer(r'^\s*([a-zA-Z]:[^\s(]+)\((\d+),\d+\):\s+error\s+(CS\d+):\s+(.+)', raw_output, re.MULTILINE)
            for match in build_error_matches:
                error_details.append({
                    "method": "BuildError",
                    "file": match.group(1),
                    "line": int(match.group(2)),
                    "location": f"{match.group(1)}:line {match.group(2)}",
                    "message": f"{match.group(3)}: {match.group(4)}",
                    "stack_trace": match.group(0),
                    "is_build_error": True
                })

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
                    build_error_matches = re.finditer(r'^\s*([a-zA-Z]:[^\s(]+)\((\d+),\d+\):\s+error\s+(CS\d+):\s+(.+)', raw_output, re.MULTILINE)
                    for match in build_error_matches:
                        error_details.append({
                            "method": "BuildError",
                            "file": match.group(1),
                            "line": int(match.group(2)),
                            "location": f"{match.group(1)}:line {match.group(2)}",
                            "message": f"{match.group(3)}: {match.group(4)}",
                            "stack_trace": match.group(0),
                            "is_build_error": True
                        })
                    if error_details:
                        break

        all_suggestions = []
        all_analyses = []
        
        for failure in error_details:
            test_method = failure.get("method", "")
            
            # --- NEW: Resolve target code from test_method name ---
            target_file = ""
            target_method = ""
            current_impl = ""
            
            if test_method:
                # Heuristic: Extract Class and Method from "Namespace.Tests.ClassTests.Method_Should..."
                match = re.search(r'([\w\.]+)\.([\w\.]+)Tests\.([\w\.]+)_Should', test_method)
                if match:
                    # Remove '.Tests' from namespace if present
                    namespace = match.group(1).replace(".Tests", "")
                    target_class_full = f"{namespace}.{match.group(2)}"
                    target_method_name = match.group(3)
                    
                    # Use knowledge graph to find file and implementation
                    output_path = self.ae._get_entity_value(parameters.get("output_path"))
                    if not output_path:
                        # Try to find output_path in history
                        history = context.get("history", [])
                        for past_context in reversed(history):
                            if past_context.get("analysis", {}).get("entities", {}).get("output_path"):
                                output_path = past_context["analysis"]["entities"]["output_path"]["value"]
                                break
                    
                    if output_path:
                        try:
                            manifest, details_by_id = self.ae.csharp_ops.load_csharp_analysis_results(output_path)
                            class_obj = next((obj for obj in manifest.get("objects", []) if obj.get("fullName") == target_class_full), None)
                            if class_obj:
                                detail = details_by_id.get(class_obj["id"], {})
                                target_file = class_obj.get("filePath", "")
                                m_detail = next((m for m in detail.get("methods", []) if m.get("name") == target_method_name), None)
                                if m_detail:
                                    target_method = target_method_name
                                    # --- NEW: Read actual source code ---
                                    try:
                                        if os.path.exists(target_file):
                                            with open(target_file, 'r', encoding='utf-8') as f:
                                                full_source = f.read().splitlines()
                                                s_line = m_detail.get("startLine", 1)
                                                e_line = m_detail.get("endLine", s_line + 5)
                                                # Extract the method body
                                                current_impl = "\n".join(full_source[max(0, s_line-1):min(len(full_source), e_line)])
                                        else:
                                            current_impl = f"// File not found: {target_file}"
                                    except Exception as e:
                                        current_impl = f"// Error reading source: {e}"
                        except: pass

            test_failure_data = {
                'test_file': failure.get("file", failure.get("location", "")),
                'test_method': test_method,
                'error_type': "compile_error" if failure.get("is_build_error") else "assertion_failure",
                'error_message': failure.get("message", ""),
                'stack_trace': failure.get("stack_trace", ""),
                'line_number': failure.get("line"),
                'target_code': {
                    'file': target_file,
                    'method': target_method,
                    'current_implementation': current_impl
                }
            }
            
            try:
                result = self.ae.advanced_tdd_support.analyze_and_fix_test_failure(test_failure_data)
                if result['status'] == 'success':
                    all_analyses.append(result['analysis'])
                    # Tag each suggestion with the test method it fixes
                    for sug in result['fix_suggestions']:
                        sug['test_method'] = test_method
                        all_suggestions.append(sug)
            except Exception as e:
                self.ae.log_manager.log_event("analyze_test_failure_error", {"error": str(e), "test_method": test_method}, level="ERROR")
                print(f"Error analyzing {test_method}: {e}")

        if not all_suggestions:
            # Collect some debug info from failure objects if any
            debug_info = f" (Failure count: {len(error_details)})"
            if all_analyses:
                 debug_info += f" (Analyses: {len(all_analyses)}, first status: {all_analyses[0].get('status')})"
            
            context["action_result"] = {
                "status": "error",
                "message": f"{len(error_details)}件の失敗を分析しましたが、修正案を生成できませんでした。{debug_info}"
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
            safety_indicator = "🟢" if suggestion['safety_score'] > 0.9 else "🟡" if suggestion['safety_score'] > 0.7 else "🔴"
            auto_indicator = "✅" if suggestion.get('auto_applicable', True) else "⚠️"
            message_parts.append(f"{i}. [{suggestion.get('test_method', '不明')}] {suggestion['description']} {safety_indicator} {auto_indicator}")

        if len(all_suggestions) > 5:
            message_parts.append(f"...他 {len(all_suggestions) - 5} 件の提案があります。")

        context["action_result"] = {
            "status": "success",
            "message": "\n".join(message_parts),
            "analysis_result": {
                "status": "success",
                "analyses": all_analyses,
                "fix_suggestions": all_suggestions
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
                
                message_parts = [
                    f"ゴール駆動型TDDが完了しました。",
                    f"目標: {goal_data['description']}",
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
                    "tdd_result": result
                }
            else:
                context["action_result"] = {
                    "status": "error",
                    "message": f"ゴール駆動型TDD実行に失敗しました: {result.get('error', '不明なエラー')}"
                }
                
        except Exception as e:
            self.ae.log_manager.log_event("tdd_execution_error", {"message": f"ゴール駆動型TDD実行中にエラーが発生: {e}"}, level="ERROR")
            context["action_result"] = {
                "status": "error",
                "message": f"ゴール駆動型TDD実行中にエラーが発生しました: {str(e)}"
            }
        
        return context
    
    def apply_code_fix(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """コード修正提案を適用（一括適用対応）"""
        parameters = context.get("plan", {}).get("parameters", {})
        fix_id_requested = self.ae._get_entity_value(parameters.get("fix_id", ""))
        backup_enabled = parameters.get("backup_enabled", True)
        
        # If fix_id_requested doesn't look like a real ID, treat as "all"
        is_valid_id = fix_id_requested and (fix_id_requested.startswith("heal_") or fix_id_requested.startswith("manual_") or fix_id_requested.startswith("calc_") or fix_id_requested.startswith("nullcheck_"))
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
                                target_file = re.sub(r':(?:line\s+)?\d+$', '', target_file)
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
                                except:
                                    failed_count += 1
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
            
            should_rollback = not all_valid
            has_add_package = any(s.get("type") == "add_package" for s in target_suggestions)
            if has_add_package and not all_valid:
                should_rollback = False

            if applied_count > 0 and (all_valid or not should_rollback):
                context["action_result"] = {
                    "status": "success",
                    "message": f"一括コード修正を完了しました。\n適用成功: {applied_count}件, スキップ: {failed_count}件\n修正ファイル: {', '.join(files_modified)}",
                    "applied_fixes": {"count": applied_count, "files": list(files_modified)}
                }
            elif should_rollback:
                for t_path, b_path in backups.items():
                    shutil.copy2(b_path, t_path)
                context["action_result"] = {
                    "status": "error",
                    "message": f"修正後の検証でエラーが発生したためロールバックしました。\n詳細: {error_msg}"
                }
        except Exception as e:
            for t_path, b_path in backups.items():
                if os.path.exists(b_path): shutil.copy2(b_path, t_path)
            context["action_result"] = {"status": "error", "message": f"一括修正適用中に予期せぬエラーが発生しました: {e}"}
        
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