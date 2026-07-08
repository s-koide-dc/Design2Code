# -*- coding: utf-8 -*-
import os
import json
import sys
import subprocess
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from .models import TestFailure
from .knowledge_base import RepairKnowledgeBase

class TestFailureAnalyzer:
    """テスト失敗分析を担当するクラス"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.config_manager = config.get("config_manager")
        self.logger = logging.getLogger(__name__)
        self.knowledge_base = RepairKnowledgeBase(config_manager=self.config_manager)
        
        self.test_frameworks = {
            'csharp': {'command': 'dotnet test', 'result_parser': self._parse_dotnet_test_result},
            'python': {'command': 'pytest --tb=short', 'result_parser': self._parse_pytest_result},
            'javascript': {'command': 'npm test', 'result_parser': self._parse_jest_result}
        }
    
    def execute_test_and_analyze(self, test_file: str, language: str, project_path: str = ".") -> Dict[str, Any]:
        """テストを実行して失敗を分析"""
        try:
            test_result = self._execute_test(test_file, language, project_path)
            
            if test_result['status'] == 'success':
                return {
                    'status': 'success',
                    'message': 'すべてのテストが成功しました',
                    'test_results': test_result,
                    'execution_time': test_result.get('execution_time', 0),
                    'summary': {
                        'total_tests': test_result.get('total_tests', 0),
                        'passed_tests': test_result.get('passed_tests', 0),
                        'failed_tests': 0
                    }
                }
            
            failed_tests = test_result.get('failed_tests', [])
            analyses = []
            
            for failed_test in failed_tests:
                test_failure = TestFailure(
                    test_file=failed_test.get('file', test_file),
                    test_method=failed_test.get('method', ''),
                    error_type=failed_test.get('error_type', ''),
                    error_message=failed_test.get('error_message', ''),
                    stack_trace=failed_test.get('stack_trace', ''),
                    line_number=failed_test.get('line_number')
                )
                
                analysis = self.analyze_test_failure(test_failure)
                analyses.append(analysis)
            
            return {
                'status': 'failure_analyzed',
                'test_results': test_result,
                'failure_analyses': analyses,
                'execution_time': test_result.get('execution_time', 0),
                'summary': {
                    'total_tests': test_result.get('total_tests', 0),
                    'failed_tests': len(failed_tests),
                    'analyzed_failures': len(analyses),
                    'success_rate': (test_result.get('total_tests', 0) - len(failed_tests)) / max(test_result.get('total_tests', 1), 1)
                }
            }
            
        except Exception as e:
            self.logger.error(f"テスト実行・分析中にエラーが発生: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _execute_test(self, test_file: str, language: str, project_path: str) -> Dict[str, Any]:
        """実際のテスト実行"""
        framework = self.test_frameworks.get(language)
        if not framework: raise ValueError(f"サポートされていない言語: {language}")
        
        start_time = datetime.now()
        try:
            if language == 'csharp':
                command = [
                    'dotnet', 'test', test_file,
                    '--logger', 'trx',
                    '--results-directory', 'temp_results',
                    '--verbosity', 'normal',
                ]
            elif language == 'python':
                command = [
                    sys.executable, '-m', 'pytest', '--tb=short', test_file,
                    '--json-report',
                    '--json-report-file=temp_test_results.json',
                    '-v',
                ]
            else:
                command = [
                    'npm', 'test', '--',
                    f'--testPathPattern={test_file}',
                    '--json',
                    '--outputFile=temp_test_results.json',
                    '--verbose',
                ]
            
            self.logger.info(f"テスト実行コマンド: {command}")
            env = os.environ.copy()
            env['DOTNET_CLI_UI_LANGUAGE'] = 'en-US'
            env['VSLANG'] = '1033'

            result = subprocess.run(
                command,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
                check=False,
            )
            parsed_result = framework['result_parser'](result, project_path)
            parsed_result['execution_time'] = (datetime.now() - start_time).total_seconds()
            parsed_result['raw_output'] = result.stdout + "\n" + result.stderr
            return parsed_result
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _parse_dotnet_test_result(self, result: subprocess.CompletedProcess, project_path: str) -> Dict[str, Any]:
        output = result.stdout + '\n' + result.stderr
        if result.returncode == 0:
            return {'status': 'success', 'total_tests': self._extract_test_count(output), 'failed_tests': []}

        failed_test_names = self._extract_failed_test_names(output)
        failed_tests = []
        
        for test_name in failed_test_names:
            current_test = {
                'file': test_name.split('.')[-2] if '.' in test_name else test_name,
                'method': test_name,
                'error_type': 'assertion_failure',
                'error_message': '',
                'stack_trace': ''
            }
            error_block = self._extract_dotnet_error_block(output, test_name)
            current_test['error_message'] = error_block.get('error_message', '')
            current_test['stack_trace'] = error_block.get('stack_trace', '')
            failed_tests.append(current_test)

        return {'status': 'failure', 'total_tests': self._extract_test_count(output), 'failed_tests': failed_tests}

    def _extract_test_count(self, output: str) -> int:
        for line in output.splitlines():
            count = self._extract_count_after_marker(line, 'Total Tests:')
            if count is not None:
                return count
            if line.strip().startswith('Tests:'):
                parts = line.replace(',', ' ').split()
                for index, part in enumerate(parts):
                    if part.isdigit() and index + 1 < len(parts) and parts[index + 1] == 'total':
                        return int(part)
        return 0

    def _parse_pytest_stdout(self, output: str) -> List[Dict[str, Any]]:
        """pytestの標準出力から失敗したテストを抽出"""
        failed_tests = []
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped.startswith('FAILED '):
                continue
            payload = stripped[len('FAILED '):]
            location, separator, message = payload.partition(' - ')
            if not separator or '::' not in location:
                continue
            file_name, method = location.split('::', 1)
            failed_tests.append({
                'file': file_name,
                'method': method,
                'error_message': message.strip(),
                'error_type': 'assertion_failure'
            })
        return failed_tests

    def _parse_pytest_result(self, result, path): return {'status': 'success'} # Stub
    def _parse_jest_result(self, result, path): return {'status': 'success'} # Stub

    def analyze_test_failure(
        self,
        test_failure: TestFailure,
        roslyn_data: Optional[Dict[str, Any]] = None,
        expected_intent: Optional[str] = None,
        analysis_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """テスト失敗を分析"""
        try:
            error_type = self._classify_error_type(test_failure)
            root_cause = self._identify_root_cause(test_failure, error_type)
            if analysis_context:
                explicit_root_cause = analysis_context.get('root_cause')
                if isinstance(explicit_root_cause, str) and explicit_root_cause:
                    root_cause = explicit_root_cause
            
            semantic_mismatch = None
            if expected_intent and analysis_context:
                semantic_mismatch = self._detect_semantic_mismatch(
                    expected_intent,
                    analysis_context,
                )
                if semantic_mismatch:
                    root_cause = 'semantic_mismatch'

            # Roslynデータがある場合、より詳細なロジック分析を試みる
            logic_analysis = None
            if (
                error_type == 'assertion_failure'
                and roslyn_data
                and analysis_context
                and not semantic_mismatch
            ):
                logic_analysis = self._analyze_logic_mismatch(
                    test_failure,
                    roslyn_data,
                    analysis_context,
                )
                if logic_analysis and logic_analysis.get('refined_root_cause'):
                    root_cause = logic_analysis['refined_root_cause']

            fix_direction = self._determine_fix_direction(root_cause, test_failure)
            stack_trace_analysis = self._analyze_stack_trace(test_failure.stack_trace)
            analysis_summary = self._build_analysis_summary(
                test_failure=test_failure,
                error_type=error_type,
                root_cause=root_cause,
                fix_direction=fix_direction,
                stack_trace_analysis=stack_trace_analysis,
                logic_analysis=logic_analysis,
                semantic_mismatch=semantic_mismatch,
            )
            
            return {
                'status': 'success', 
                'error_type': error_type, 
                'root_cause': root_cause, 
                'fix_direction': fix_direction,
                'confidence': 0.9,
                'logic_analysis': logic_analysis,
                'semantic_mismatch': semantic_mismatch, # NEW
                'analysis_summary': analysis_summary,
                'analysis_details': {
                    'error_message': test_failure.error_message,
                    'line_number': test_failure.line_number,
                    'stack_trace_analysis': stack_trace_analysis,
                    'test_context': {'test_file': test_failure.test_file, 'test_method': test_failure.test_method}
                }
            }
        except Exception as e:
            self.logger.error(f"分析中にエラーが発生: {e}")
            return {'status': 'error', 'error': str(e)}

    def _build_analysis_summary(
        self,
        test_failure: TestFailure,
        error_type: str,
        root_cause: str,
        fix_direction: str,
        stack_trace_analysis: Dict[str, Any],
        logic_analysis: Optional[Dict[str, Any]],
        semantic_mismatch: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        primary_location = stack_trace_analysis.get('primary_location') or {}
        target_file = primary_location.get('file') or test_failure.test_file
        summary = {
            'test_method': test_failure.test_method,
            'error_type': error_type,
            'root_cause': root_cause,
            'fix_direction': fix_direction,
            'target_file': target_file,
            'line_number': primary_location.get('line') or test_failure.line_number,
            'has_logic_analysis': bool(logic_analysis),
            'has_semantic_mismatch': bool(semantic_mismatch),
        }
        if logic_analysis and logic_analysis.get('branch_condition'):
            summary['branch_condition'] = logic_analysis.get('branch_condition')
        if semantic_mismatch and semantic_mismatch.get('message'):
            summary['semantic_mismatch_message'] = semantic_mismatch.get('message')
        return summary

    def _analyze_logic_mismatch(
        self,
        test_failure: TestFailure,
        roslyn_data: Dict[str, Any],
        analysis_context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Roslynデータを用いてロジックの不一致を詳細分析 (Deep Stack Analysis対応)"""
        # 1. スタックトレースから全フレームを取得
        stack_info = self._analyze_stack_trace(test_failure.stack_trace)
        frames = stack_info.get('file_locations', [])
        
        if not frames: return None

        input_values = analysis_context.get('input_values')
        if not isinstance(input_values, dict) or not input_values:
            return None

        # 各スタックフレームを走査 (上から下へ)
        for frame in frames:
            target_method = self._find_method_for_frame(frame, roslyn_data)
            
            if not target_method or not target_method.get('branches'):
                continue

            # 4. 分岐条件と照合
            best_match = None
            for branch in target_method['branches']:
                condition = branch.get('condition', '')
                
                # 複合条件 (&&, ||) を優先順位 (&& > ||) を考慮して評価
                evaluation_result = self._evaluate_complex_condition(
                    condition,
                    input_values,
                    roslyn_data,
                )
                
                if not evaluation_result['evaluated']: continue

                res = {
                    'branch_condition': condition,
                    'input_values': input_values,
                    'is_satisfied': evaluation_result['is_satisfied'],
                    'failed_parts': evaluation_result['failed_parts'],
                    'refined_root_cause': 'logic_mismatch_with_branch',
                    'blamed_frame': frame # 原因と特定されたフレーム情報を付与
                }
                
                if not evaluation_result['is_satisfied']:
                    return res
                best_match = res
            
            # このフレームで不一致が見つからなければ、次のフレーム(呼び出し元)へ
        
        return best_match

    def _find_method_for_frame(
        self,
        frame: Dict[str, Any],
        roslyn_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """ファイルと行範囲を使ってスタックフレームに対応するメソッドを解決する。"""
        frame_file = frame.get('file')
        frame_line = frame.get('line')
        if not frame_file or not isinstance(frame_line, int):
            return None

        normalized_frame = os.path.normcase(os.path.abspath(frame_file))
        details = roslyn_data.get('details_by_id', {})
        for manifest_object in roslyn_data.get('manifest', {}).get('objects', []):
            object_file = manifest_object.get('filePath')
            if not object_file:
                continue
            if os.path.normcase(os.path.abspath(object_file)) != normalized_frame:
                continue
            detail = details.get(manifest_object.get('id'), {})
            for method in detail.get('methods', []):
                start_line = method.get('startLine')
                end_line = method.get('endLine')
                if (
                    isinstance(start_line, int)
                    and isinstance(end_line, int)
                    and start_line <= frame_line <= end_line
                ):
                    return method
        return None

    def _evaluate_complex_condition(self, condition: str, input_val: Any, roslyn_data: Optional[Dict[str, Any]] = None, test_failure: Optional[TestFailure] = None) -> Dict[str, Any]:
        """複合条件式 (A && B || C) を評価する"""
        # 1. OR (||) で分割
        or_groups = condition.split('||')
        
        or_results = []
        all_failed_parts = []
        
        for group in or_groups:
            # 2. AND (&&) で分割
            and_parts = group.split('&&')
            
            group_satisfied = True
            group_failed_parts = []
            
            for part in and_parts:
                part = part.strip()
                # カッコ除去 (簡易対応)
                clean_part = part.strip('()')
                
                parsed_condition = self._parse_condition_part(clean_part)
                if parsed_condition:
                    var_name, op, threshold_str = parsed_condition
                    
                    current_input = self._resolve_explicit_input(input_val, var_name)
                    if current_input is None:
                        group_satisfied = False
                        group_failed_parts.append(clean_part)
                        continue

                    is_satisfied = self._evaluate_condition(current_input, op, threshold_str, roslyn_data)
                    
                    if not is_satisfied:
                        group_satisfied = False
                        group_failed_parts.append(clean_part)
                else:
                    # 比較演算子がない場合 (例: user.IsActive, !isValid)
                    bool_condition = self._parse_boolean_condition(clean_part)
                    if bool_condition:
                        is_negated, var_name = bool_condition
                        
                        current_input = self._resolve_explicit_input(input_val, var_name)
                        if current_input is None:
                            group_satisfied = False
                            group_failed_parts.append(clean_part)
                            continue
                        
                        # ブール値としての評価
                        # inputが 'true'/'false' 文字列や Python bool の場合を考慮
                        val_str = str(current_input).lower()
                        is_true = val_str == 'true'
                        
                        is_satisfied = (not is_true) if is_negated else is_true
                        
                        if not is_satisfied:
                            group_satisfied = False
                            group_failed_parts.append(clean_part)
            
            or_results.append(group_satisfied)
            if not group_satisfied:
                all_failed_parts.extend(group_failed_parts)
        
        # 全体の充足判定 (ORなので、どれか一つでもTrueならTrue)
        is_satisfied_overall = any(or_results)
        
        return {
            'evaluated': True,
            'is_satisfied': is_satisfied_overall,
            'failed_parts': all_failed_parts if not is_satisfied_overall else []
        }

    @staticmethod
    def _parse_condition_part(condition_part: str) -> Optional[tuple]:
        for op in ('>=', '<=', '==', '!=', '>', '<'):
            op_index = condition_part.find(op)
            if op_index <= 0:
                continue
            left = condition_part[:op_index].strip()
            right = condition_part[op_index + len(op):].strip()
            if left and right:
                return left, op, right
        return None

    @staticmethod
    def _parse_boolean_condition(condition_part: str) -> Optional[tuple]:
        stripped = condition_part.strip()
        if not stripped:
            return None
        if stripped.startswith('!'):
            name = stripped[1:].strip()
            return (True, name) if name else None
        return False, stripped

    @staticmethod
    def _resolve_explicit_input(input_values: Any, variable_name: str) -> Optional[Any]:
        if not isinstance(input_values, dict):
            return input_values
        if variable_name in input_values:
            return input_values[variable_name]
        member_name = variable_name.rsplit('.', 1)[-1]
        return input_values.get(member_name)

    def _evaluate_condition(self, input_val: Any, op: str, threshold_str: str, roslyn_data: Optional[Dict[str, Any]] = None) -> bool:
        """単一の条件式を評価"""
        # 値の解決 (Enumや定数の場合)
        threshold_val = self._resolve_identifier_value(threshold_str, roslyn_data)
        
        if isinstance(threshold_val, str) and (threshold_val.startswith('"') or threshold_val.startswith("'")):
            threshold = threshold_val[1:-1]
            if op == '==': return str(input_val) == threshold
            if op == '!=': return str(input_val) != threshold
            return False
        else:
            try:
                threshold = int(threshold_val)
                input_num = int(input_val)
                if op == '>=': return input_num >= threshold
                if op == '<=': return input_num <= threshold
                if op == '>': return input_num > threshold
                if op == '<': return input_num < threshold
                if op == '==': return input_num == threshold
                if op == '!=': return input_num != threshold
            except (TypeError, ValueError):
                return False
        return False

    def _resolve_identifier_value(self, identifier: str, roslyn_data: Optional[Dict[str, Any]]) -> Any:
        """識別子 (Enum.Value や Constants.Max) を実際の値に解決する"""
        if not roslyn_data:
            return identifier
            
        # 既に数値や文字列リテラルの場合はそのまま返す
        if self._is_integer_literal(identifier) or identifier.startswith('"') or identifier.startswith("'"):
            return identifier

        # Roslynデータから検索
        # 簡易実装: 完全修飾名または末尾一致で検索
        # 注: 実際のRoslynデータの構造に依存します。ここでは details_by_id 内の Enum/Class を想定
        details = roslyn_data.get('details_by_id', {})
        
        # identifier が ClassName.Member 形式であることを期待
        parts = identifier.split('.')
        if len(parts) < 2:
            return identifier
            
        target_member = parts[-1]
        target_container = parts[-2] # Class or Enum name
        
        for detail in details.values():
            # コンテナ名が一致するか (Namespace込みのFullNameの末尾、またはNameそのもの)
            if detail.get('name') == target_container or detail.get('fullName', '').endswith(target_container):
                # Enumの場合
                if detail.get('type') == 'Enum':
                    for member in detail.get('members', []): # 仮: Enumメンバー構造
                        if member.get('name') == target_member:
                            return member.get('value')
                
                # Class/Structの定数フィールドの場合
                if detail.get('properties'):
                    for prop in detail.get('properties'):
                        if prop.get('name') == target_member and 'const' in prop.get('modifiers', []):
                             return prop.get('initializer_value') # 仮: 定数値フィールド

        return identifier

    def _classify_error_type(self, test_failure: TestFailure) -> str:
        explicit_type = test_failure.error_type
        known_types = {'assertion_failure', 'compile_error', 'runtime_error'}
        if explicit_type in known_types:
            return explicit_type
        return 'unknown_error'
    
    def analyze_compilation_failure(self, code: str, errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """MSBuildのエラー内容から型不一致などの詳細な原因を分析する"""
        results = []
        for err in errors:
            msg = err.get("message", "")
            code_num = err.get("code", "")
            
            # CS1503: Argument 1: cannot convert from 'source_type' to 'target_type'
            # CS0029: Cannot implicitly convert type 'source_type' to 'target_type'
            if code_num in ["CS1503", "CS0029", "CS0266"]:
                # 日本語と英語の両方のパターンに対応
                # 日本語例: 型 'int' を 'string' に変換できません。
                # 英語例: Cannot implicitly convert type 'int' to 'string'.
                type_pair = self._extract_type_pair_from_compiler_message(msg)
                if type_pair:
                    src_t, tgt_t = type_pair
                    recommendation = None
                    if src_t == "int" and tgt_t == "string":
                        recommendation = "ToString"
                    
                    results.append({
                        "type": "negative_feedback",
                        "error_code": code_num,
                        "source_type": src_t,
                        "target_type": tgt_t,
                        "recommendation": recommendation,
                        "line": err.get("line"),
                        "message": msg
                    })
            
            # CS0246: The type or namespace name '...' could not be found
            elif code_num == "CS0246":
                symbol = self._extract_first_quoted_segment(msg)
                if symbol:
                    results.append({
                        "type": "unresolved_symbol",
                        "symbol": symbol,
                        "error_code": code_num,
                        "line": err.get("line"),
                        "message": msg
                    })
        return results

    def analyze_runtime_failure(self, exception_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """実行時例外から原因を特定し、修正アクションを提案する"""
        results = []
        ex_type = exception_info.get("type", "")
        msg = exception_info.get("message", "")
        
        recommendation = None
        if "FileNotFoundException" in ex_type:
            recommendation = "AddFileCheck"
        elif "JsonException" in ex_type:
            recommendation = "AddJsonValidation"
        elif "HttpRequestException" in ex_type:
            recommendation = "AddNetworkRetry"
        elif "[ASSERTION_FAILURE]" in msg or ex_type == "AssertionFailure":
            recommendation = "FixLogicMismatch"
            
        results.append({
            "type": "runtime_feedback",
            "exception_type": ex_type,
            "message": msg,
            "recommendation": recommendation
        })
        return results

    def _identify_root_cause(self, test_failure: TestFailure, error_type: str) -> str:
        if error_type == 'assertion_failure':
            assertion_values = self._parse_assertion_values(test_failure.error_message)
            if assertion_values.get('expected') == '0' or assertion_values.get('actual') == '0':
                return 'method_returns_default_value'
            return 'logic_error'
        elif error_type == 'compile_error': return 'syntax_error'
        elif test_failure.error_type == 'null_reference': return 'null_reference'
        elif test_failure.error_type == 'not_implemented': return 'not_implemented'
        return 'unknown_cause'
    
    def _determine_fix_direction(self, root_cause: str, test_failure: TestFailure) -> str:
        # 1. 知識ベース(学習データ)からの統計的判断
        stats = self.knowledge_base.fix_stats.get(root_cause)
        if stats and stats['success'] > 0:
            # 最も成功率の高い修正方向を選択
            best_fix = max(stats['fixes'].items(), key=lambda x: x[1])[0]
            self.logger.info(f"Using learned fix direction for {root_cause}: {best_fix}")
            return best_fix

        # 2. ルールベースのフォールバック
        if root_cause == 'logic_error' or root_cause == 'logic_mismatch_with_branch': 
            return 'self_healing_test'
        fix_directions = {
            'method_returns_default_value': 'implement_method_logic',
            'not_implemented': 'implement_method_logic',
            'missing_test_data': 'fix_test_arrange',
            'null_reference': 'add_null_validation',
            'syntax_error': 'fix_syntax_error'
        }
        return fix_directions.get(root_cause, 'manual_investigation_required')

    def _analyze_stack_trace(self, stack_trace: str) -> Dict[str, Any]:
        lines = stack_trace.split('\n')
        matches = []
        for line in lines:
            line = line.strip()
            # Handle formats like: "at ... in C:\path\file.cs:line 12" or "... in /path/file.cs:line 12"
            location = self._parse_stack_trace_location(line)
            if location:
                matches.append(location)
        return {'stack_depth': len(lines), 'file_locations': matches, 'primary_location': matches[0] if matches else None}

    def _extract_failed_test_names(self, output: str) -> List[str]:
        names: List[str] = []
        for line in output.splitlines():
            stripped = line.strip()
            name = None
            if '[FAIL]' in stripped:
                before_marker = stripped.split('[FAIL]', 1)[0].strip()
                if ']' in before_marker:
                    before_marker = before_marker.rsplit(']', 1)[-1].strip()
                name = before_marker.split()[-1] if before_marker.split() else None
            elif stripped.startswith('Failed '):
                payload = stripped[len('Failed '):].strip()
                name = payload.split()[0] if payload.split() else None
            elif stripped.startswith('失敗 '):
                payload = stripped[len('失敗 '):].strip()
                name = payload.split()[0] if payload.split() else None

            if name and '.' in name and name not in names:
                names.append(name)
        return names

    def _extract_dotnet_error_block(self, output: str, test_name: str) -> Dict[str, str]:
        lines = output.splitlines()
        start_index = None
        for index, line in enumerate(lines):
            if test_name in line:
                start_index = index
                break
        if start_index is None:
            return {'error_message': '', 'stack_trace': ''}

        error_lines: List[str] = []
        stack_lines: List[str] = []
        destination = error_lines
        for line in lines[start_index + 1:]:
            stripped = line.strip()
            if self._is_next_test_result_line(stripped):
                break
            if stripped in {'Error Message:', 'エラー メッセージ:'}:
                destination = error_lines
                continue
            if stripped in {'Stack Trace:', 'スタック トレース:'}:
                destination = stack_lines
                continue
            destination.append(line)

        return {
            'error_message': '\n'.join(error_lines).strip(),
            'stack_trace': '\n'.join(stack_lines).strip(),
        }

    @staticmethod
    def _is_next_test_result_line(line: str) -> bool:
        return (
            '[FAIL]' in line
            or '[PASS]' in line
            or line.startswith('Failed ')
            or line.startswith('Passed ')
            or line.startswith('失敗 ')
            or line.startswith('成功 ')
        )

    @staticmethod
    def _extract_count_after_marker(line: str, marker: str) -> Optional[int]:
        marker_index = line.find(marker)
        if marker_index < 0:
            return None
        payload = line[marker_index + len(marker):].strip()
        first_token = payload.replace(',', ' ').split()[0] if payload.split() else ''
        return int(first_token) if first_token.isdigit() else None

    @staticmethod
    def _is_integer_literal(value: str) -> bool:
        stripped = value.strip()
        if not stripped:
            return False
        if stripped.startswith('-'):
            return stripped[1:].isdigit()
        return stripped.isdigit()

    def _extract_type_pair_from_compiler_message(self, message: str) -> Optional[tuple]:
        quoted = self._extract_quoted_segments(message)
        if len(quoted) >= 2:
            return quoted[0].strip(), quoted[1].strip()

        marker_start = message.find('型')
        marker_middle = message.find('を', marker_start + 1)
        marker_end = message.find('に', marker_middle + 1)
        if marker_start >= 0 and marker_middle > marker_start and marker_end > marker_middle:
            source = message[marker_start + len('型'):marker_middle].strip()
            target = message[marker_middle + len('を'):marker_end].strip()
            if source and target:
                return source, target
        return None

    def _extract_first_quoted_segment(self, message: str) -> Optional[str]:
        segments = self._extract_quoted_segments(message)
        return segments[0] if segments else None

    @staticmethod
    def _extract_quoted_segments(message: str) -> List[str]:
        segments: List[str] = []
        current: List[str] = []
        in_quote = False
        for char in message:
            if char == "'":
                if in_quote:
                    segments.append(''.join(current))
                    current = []
                    in_quote = False
                else:
                    current = []
                    in_quote = True
                continue
            if in_quote:
                current.append(char)
        return segments

    @staticmethod
    def _parse_assertion_values(message: str) -> Dict[str, str]:
        values: Dict[str, str] = {}
        for key, marker in (('expected', 'Expected:'), ('actual', 'Actual:')):
            marker_index = message.find(marker)
            if marker_index < 0:
                continue
            payload = message[marker_index + len(marker):].strip()
            for delimiter in (',', '\n', '\r'):
                delimiter_index = payload.find(delimiter)
                if delimiter_index >= 0:
                    payload = payload[:delimiter_index].strip()
            values[key] = payload.strip('"').strip("'").strip()
        return values

    @staticmethod
    def _parse_stack_trace_location(line: str) -> Optional[Dict[str, Any]]:
        separator = ' in '
        separator_index = line.find(separator)
        if separator_index < 0:
            return None
        payload = line[separator_index + len(separator):]

        line_markers = (':line ', ':line:', ':行 ')
        marker_index = -1
        marker = ''
        for candidate in line_markers:
            marker_index = payload.find(candidate)
            if marker_index >= 0:
                marker = candidate
                break
        if marker_index < 0:
            return None

        file_path = payload[:marker_index].strip()
        line_payload = payload[marker_index + len(marker):].strip()
        digits = []
        for char in line_payload:
            if not char.isdigit():
                break
            digits.append(char)
        if not file_path or not digits:
            return None
        return {'file': file_path, 'line': int(''.join(digits))}

    def _detect_semantic_mismatch(
        self,
        expected_intent: str,
        analysis_context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """明示された正規化済みの役割同士を比較する。"""
        executed_role = analysis_context.get('executed_role')
        if not isinstance(executed_role, str) or not executed_role:
            return None
        if executed_role == expected_intent:
            return None
        return {
            "expected_intent": expected_intent,
            "executed_role": executed_role,
            "message": (
                f"期待された役割 '{expected_intent}' と、"
                f"実行された役割 '{executed_role}' が一致しません。"
            ),
        }

    
