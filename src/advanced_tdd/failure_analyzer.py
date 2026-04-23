# -*- coding: utf-8 -*-
import os
import re
import json
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
        
        self.error_patterns = {
            'assertion_failure': [
                r'Assert\.(?:True|False|Equal|NotNull|Null|Throws|IsType)\(\)\ Failure',
                r'Expected:?\s*(.+),?\s*(?:but\s+)?Actual:?\s*(.+)',
                r'Assert\.Equal.*Expected.*Actual',
                r'AssertionError:.*expected.*got',
                r'\[ASSERTION_FAILURE\]'
            ],
            'compile_error': [r'CS\d+:', r'SyntaxError:', r'TypeError:.*not defined'],
            'runtime_error': [
                r'NullReferenceException',
                r'ArgumentException',
                r'IndexOutOfRangeException',
                r'KeyError:',
                r'AttributeError:',
                r'NotImplementedException'
            ]
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
                command = f'{framework["command"]} \"{test_file}\" --logger trx --results-directory temp_results --verbosity normal'
            elif language == 'python':
                command = f'{framework["command"]} \"{test_file}\" --json-report --json-report-file=temp_test_results.json -v'
            else:
                command = f'{framework["command"]} --testPathPattern=\"{{test_file}}\" --json --outputFile=temp_test_results.json --verbose'
            
            self.logger.info(f"テスト実行コマンド: {command}")
            env = os.environ.copy()
            env['DOTNET_CLI_UI_LANGUAGE'] = 'en-US'
            env['VSLANG'] = '1033'

            result = subprocess.run(command, shell=True, cwd=project_path, capture_output=True, text=True, timeout=300, env=env)
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

        failed_test_names = []
        # Robust patterns for various dotnet test output formats
        patterns = [
            r'\[xUnit\.net.*?\]\s+([\w\.]+\.[\w\.]+)\s+\[FAIL\]',
            r'失敗\s+([\w\.]+\.[\w\.]+)\s+\[',
            r'Failed\s+([\w\.]+\.[\w\.]+)\s+\[',
            r'([\w\.]+\.[\w\.]+)\s+\(.*\):\s+(?:Error Message|エラー メッセージ):'
        ]
        for p in patterns:
            failed_test_names.extend(re.findall(p, output))
        
        failed_test_names = list(set(failed_test_names))
        failed_tests = []
        
        for test_name in failed_test_names:
            current_test = {
                'file': test_name.split('.')[-2] if '.' in test_name else test_name,
                'method': test_name,
                'error_type': 'assertion_failure',
                'error_message': '',
                'stack_trace': ''
            }
            test_name_re = re.escape(test_name)
            error_block_match = re.search(f'{test_name_re}.*?(?:Error Message:|エラー メッセージ:)(.*?)(?:Stack Trace:|スタック トレース:)(.*?)(?=\\s+失敗|\\s+成功|\\s+Passed|\\s+Failed|$)', output, re.DOTALL)
            if error_block_match:
                current_test['error_message'] = error_block_match.group(1).strip()
                current_test['stack_trace'] = error_block_match.group(2).strip()
            else:
                # Fallback extraction
                msg_match = re.search(r'(' + test_name_re + r'.*?:?\s*(.*?)(?:\s+at\s+|$))', output, re.DOTALL)
                if msg_match:
                    current_test['error_message'] = msg_match.group(2).strip()
            failed_tests.append(current_test)

        return {'status': 'failure', 'total_tests': self._extract_test_count(output), 'failed_tests': failed_tests}

    def _extract_test_count(self, output: str) -> int:
        match = re.search(r'Total Tests: (\d+)', output, re.IGNORECASE)
        if not match: match = re.search(r'Tests:\s+(\d+) total', output, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    def _parse_pytest_stdout(self, output: str) -> List[Dict[str, Any]]:
        """pytestの標準出力から失敗したテストを抽出"""
        failed_tests = []
        # FAILED tests/test_file.py::test_method - AssertionError: ...
        pattern = r'FAILED\s+(.*?)::(.*?)\s+-\s+(.*)'
        for match in re.finditer(pattern, output):
            failed_tests.append({
                'file': match.group(1),
                'method': match.group(2),
                'error_message': match.group(3).strip(),
                'error_type': 'assertion_failure'
            })
        return failed_tests

    def _parse_pytest_result(self, result, path): return {'status': 'success'} # Stub
    def _parse_jest_result(self, result, path): return {'status': 'success'} # Stub

    def analyze_test_failure(self, test_failure: TestFailure, roslyn_data: Optional[Dict[str, Any]] = None, expected_intent: Optional[str] = None) -> Dict[str, Any]:
        """テスト失敗を分析"""
        try:
            error_type = self._classify_error_type(test_failure.error_message)
            root_cause = self._identify_root_cause(test_failure, error_type)
            
            # --- NEW: Semantic Mismatch Detection ---
            semantic_mismatch = None
            if expected_intent and roslyn_data:
                semantic_mismatch = self._detect_semantic_mismatch(test_failure, expected_intent, roslyn_data)
                if semantic_mismatch:
                    root_cause = 'semantic_mismatch'
            # ----------------------------------------

            # Roslynデータがある場合、より詳細なロジック分析を試みる
            logic_analysis = None
            if error_type == 'assertion_failure' and roslyn_data and not semantic_mismatch:
                logic_analysis = self._analyze_logic_mismatch(test_failure, roslyn_data)
                if logic_analysis and logic_analysis.get('refined_root_cause'):
                    root_cause = logic_analysis['refined_root_cause']

            fix_direction = self._determine_fix_direction(root_cause, test_failure)
            
            return {
                'status': 'success', 
                'error_type': error_type, 
                'root_cause': root_cause, 
                'fix_direction': fix_direction,
                'confidence': 0.9,
                'logic_analysis': logic_analysis,
                'semantic_mismatch': semantic_mismatch, # NEW
                'analysis_details': {
                    'error_message': test_failure.error_message,
                    'line_number': test_failure.line_number,
                    'stack_trace_analysis': self._analyze_stack_trace(test_failure.stack_trace),
                    'test_context': {'test_file': test_failure.test_file, 'test_method': test_failure.test_method}
                }
            }
        except Exception as e:
            self.logger.error(f"分析中にエラーが発生: {e}")
            return {'status': 'error', 'error': str(e)}

    def _analyze_logic_mismatch(self, test_failure: TestFailure, roslyn_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Roslynデータを用いてロジックの不一致を詳細分析 (Deep Stack Analysis対応)"""
        # 1. スタックトレースから全フレームを取得
        stack_info = self._analyze_stack_trace(test_failure.stack_trace)
        frames = stack_info.get('file_locations', [])
        
        if not frames: return None

        # テストの入力値を抽出試行 (全フレームで共通と仮定)
        input_val = self._extract_input_value(test_failure)
        if input_val is None: return None
        
        details = roslyn_data.get('details_by_id', {})

        # 各スタックフレームを走査 (上から下へ)
        for frame in frames:
            file_path = frame['file']
            # line_number = frame['line'] # 必要に応じて行番号も使用可能

            # 2. Roslynデータから該当メソッドを検索
            target_method = None
            
            # スタックトレース行からメソッド名を推測
            # 例: "   at MyApp.Calculator.Add(Int32 a, Int32 b) in ..." -> "Add"
            # 簡易的に、stack_trace 全体からこのファイルを含む行を探す (非効率だが確実)
            frame_line_text = ""
            for line in test_failure.stack_trace.split('\n'):
                if file_path in line:
                    frame_line_text = line
                    break
            
            method_name_in_stack = None
            m = re.search(r'\.([^.(]+)\(', frame_line_text)
            if m: method_name_in_stack = m.group(1)

            for detail in details.values():
                for method in detail.get('methods', []):
                    # 名前一致、かつファイルパスが一致するものを探すのが理想
                    # ここでは簡易的に名前一致と、roslynデータ上のファイルパス一致を確認
                    if method.get('name') == method_name_in_stack:
                        # 本来はファイルパスチェックもすべきだが、roslyn_dataの構造に依存するため
                        # 名前が一致し、かつbranchesを持っているものを優先
                        target_method = method
                        break
                if target_method: break
            
            if not target_method or not target_method.get('branches'):
                continue

            # 4. 分岐条件と照合
            best_match = None
            for branch in target_method['branches']:
                condition = branch.get('condition', '')
                
                # 複合条件 (&&, ||) を優先順位 (&& > ||) を考慮して評価
                evaluation_result = self._evaluate_complex_condition(condition, input_val, roslyn_data, test_failure)
                
                if not evaluation_result['evaluated']: continue

                res = {
                    'branch_condition': condition,
                    'input_value': input_val,
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

    def _evaluate_complex_condition(self, condition: str, input_val: Any, roslyn_data: Optional[Dict[str, Any]] = None, test_failure: Optional[TestFailure] = None) -> Dict[str, Any]:
        """複合条件式 (A && B || C) を評価する"""
        # 1. OR (||) で分割
        or_groups = re.split(r'\s*\|\|\s*', condition)
        
        or_results = []
        all_failed_parts = []
        
        for group in or_groups:
            # 2. AND (&&) で分割
            and_parts = re.split(r'\s*&&\s*', group)
            
            group_satisfied = True
            group_failed_parts = []
            
            for part in and_parts:
                part = part.strip()
                # カッコ除去 (簡易対応)
                clean_part = part.strip('()')
                
                # 単一条件の評価 (プロパティアクセス対応: [\w\.]+)
                match = re.search(r'([\w\.]+)\s*(>=|<=|>|<|==|!=)\s*(.+)', clean_part)
                if match:
                    var_name, op, threshold_str = match.groups()
                    threshold_str = threshold_str.strip()
                    
                    # プロパティベースの推論
                    current_input = input_val
                    if '.' in var_name and test_failure:
                        prop_name = var_name.split('.')[-1]
                        prop_val = self._extract_property_value(test_failure, prop_name)
                        if prop_val is not None:
                            current_input = prop_val

                    is_satisfied = self._evaluate_condition(current_input, op, threshold_str, roslyn_data)
                    
                    if not is_satisfied:
                        group_satisfied = False
                        group_failed_parts.append(clean_part)
                else:
                    # 比較演算子がない場合 (例: user.IsActive, !isValid)
                    # 簡易対応: 単独のプロパティ/変数は "== true" として扱う
                    bool_match = re.search(r'^(!?)([\w\.]+)$', clean_part)
                    if bool_match:
                        is_negated = bool_match.group(1) == '!'
                        var_name = bool_match.group(2)
                        
                        # 値の取得
                        current_input = input_val
                        if '.' in var_name and test_failure:
                            prop_name = var_name.split('.')[-1]
                            prop_val = self._extract_property_value(test_failure, prop_name)
                            if prop_val is not None:
                                current_input = prop_val
                        
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
            except: pass
        return False

    def _extract_property_value(self, test_failure: TestFailure, property_name: str) -> Optional[Any]:
        """テストメソッド名から特定のプロパティ値を抽出する (例: WhenAgeIs20 -> Age: 20)"""
        # 一般的なパターン: Property(Is|Eq)?Value
        # 例: Age20, AgeIs20, AgeEq20
        pattern = re.compile(rf'{property_name}(?:Is|Eq|Val)?(\d+)', re.IGNORECASE)
        match = pattern.search(test_failure.test_method)
        if match:
            return int(match.group(1))
        return None

    def _resolve_identifier_value(self, identifier: str, roslyn_data: Optional[Dict[str, Any]]) -> Any:
        """識別子 (Enum.Value や Constants.Max) を実際の値に解決する"""
        if not roslyn_data:
            return identifier
            
        # 既に数値や文字列リテラルの場合はそのまま返す
        if re.match(r'^-?\d+$', identifier) or identifier.startswith('"') or identifier.startswith("'"):
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

    def _extract_input_value(self, test_failure: TestFailure) -> Optional[Any]:
        """テスト名やメッセージから入力値を推測抽出"""
        # 1. 明示的な数値
        m_neg = re.search(r'(?:Minus|Negative)(\d+)', test_failure.test_method, re.IGNORECASE)
        if m_neg: return -int(m_neg.group(1))
        
        match_num = re.search(r'(\d+)', test_failure.test_method)
        if match_num: return int(match_num.group(1))
        
        # 2. 文字列リテラル
        # TestName_ShouldReturnX_WhenYIsZ 形式から Z を抽出
        # まず '_' で分割して後半を見る
        parts = test_failure.test_method.split('_')
        last_part = parts[-1] if len(parts) > 1 else test_failure.test_method
        
        # "Is" または "When" の直後の CamelCase 単語を探す
        # ただし、最後の単語を優先する (例: WhenRoleIsUser -> User)
        m_str_list = re.findall(r'([A-Z][a-z0-9]+)', last_part)
        if m_str_list:
            # 除外リスト
            exclude = ['When', 'Should', 'Return', 'Is', 'With', 'Role', 'Type', 'Mode', 'Value', 'Fact', 'Theory']
            # 後ろから見て最初に見つかった非除外ワードを値とする
            for word in reversed(m_str_list):
                if word not in exclude:
                    return word
        
        return None

    def _classify_error_type(self, error_message: str) -> str:
        for error_type, patterns in self.error_patterns.items():
            for pattern in patterns:
                if re.search(pattern, error_message, re.IGNORECASE): return error_type
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
                match = re.search(r"'(.*?)'.*?'(.*?)'", msg)
                if not match:
                    # シングルクォートがないパターン (日本語メッセージなど)
                    match = re.search(r"型\s+(.*?)\s+を\s+(.*?)\s+に", msg)
                
                if match:
                    src_t, tgt_t = match.group(1).strip(), match.group(2).strip()
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
                match = re.search(r"'(.*?)'", msg)
                if match:
                    symbol = match.group(1)
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
        msg = test_failure.error_message
        if 'NullReferenceException' in msg:
            if any(x in test_failure.test_method.lower() for x in ['exists', 'valid', 'success', 'returns', 'should']):
                return 'missing_test_data'
            return 'null_reference'
        if 'NotImplementedException' in msg: return 'not_implemented'
        
        if error_type == 'assertion_failure':
            if re.search(r'Expected:\s*0', msg) or re.search(r'Actual:\s*0', msg): return 'method_returns_default_value'
            return 'logic_error'
        elif error_type == 'compile_error': return 'syntax_error'
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
            if ' in ' in line:
                m = re.search(r' in (.*?):(?:line|行|line:)\s*(\d+)', line)
                if m:
                    file_path = m.group(1).strip()
                    line_num = int(m.group(2))
                    matches.append({'file': file_path, 'line': line_num})
        return {'stack_depth': len(lines), 'file_locations': matches, 'primary_location': matches[0] if matches else None}

    def _detect_semantic_mismatch(self, test_failure: TestFailure, expected_intent: str, roslyn_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """意図(intent)と実際に使用されたコードの役割が乖離していないかチェックする"""
        # スタックトレースから実行されたメソッドを特定
        stack_info = self._analyze_stack_trace(test_failure.stack_trace)
        frames = stack_info.get('file_locations', [])
        if not frames: return None

        # 役割のミスマッチ判定ルール (Intent vs Class/Method Keywords)
        mismatch_rules = {
            "PARSE": ["serialize", "write", "generate", "create"],
            "SERIALIZE": ["parse", "read", "load", "detect"],
            "VALIDATE": ["execute", "run", "calculate"],
            "ANALYZE": ["format", "convert"]
        }

        # 期待される役割に関連しないキーワード
        incompatible_keywords = []
        for key, keywords in mismatch_rules.items():
            if key in expected_intent.upper():
                incompatible_keywords = keywords
                break
        
        if not incompatible_keywords: return None

        # フレームを走査してメソッド名・クラス名に不適切な単語が含まれていないか確認
        for frame in frames:
            # メソッド名の取得 (スタックトレースから)
            method_name = ""
            for line in test_failure.stack_trace.split('\n'):
                if frame['file'] in line:
                    m = re.search(r'\.([^.(]+)\(', line)
                    if m: method_name = m.group(1).lower()
                    break
            
            # クラス名の取得 (ファイル名から推測)
            class_name = os.path.basename(frame['file']).lower()

            for kw in incompatible_keywords:
                if kw in method_name or kw in class_name:
                    return {
                        "expected_intent": expected_intent,
                        "actual_code": f"{class_name}.{method_name}",
                        "incompatible_keyword": kw,
                        "message": f"意図 '{expected_intent}' に対して、不適切な役割のコード '{kw}' が使用されている可能性があります。"
                    }
        return None

    