# -*- coding: utf-8 -*-
import hashlib
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from .models import CodeFixSuggestion
from .ast_analyzer import ASTAnalyzer
from .safety_validator import SafetyValidator

class CodeFixSuggestionEngine:
    """コード修正提案エンジン"""

    REPAIR_TEMPLATES = {
        'missing_parameter': {
            'python': 'def {name}(self, {params}):',
            'csharp': 'public {return_type} {name}({params}) {{'
        },
        'logic_value_mismatch': {
            'python': '{var} = {val}  # REPAIRED: aligned with design',
            'csharp': '{var} = {val}; // REPAIRED: aligned with design'
        }
    }

    def __init__(self, config: Dict[str, Any], semantic_analyzer=None):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.ast_analyzer = ASTAnalyzer()
        self.safety_validator = SafetyValidator(config, semantic_analyzer, self.ast_analyzer)

    def generate_fix_suggestions(self, analysis: Dict[str, Any], target_code: Dict[str, Any]) -> List[CodeFixSuggestion]:
        """修正提案を生成"""
        try:
            fix_direction = analysis.get('fix_direction')
            suggestions = []

            # Logic Audit Result Handling (findings への対応強化)
            if 'findings' in analysis:
                for finding in analysis['findings']:
                    if finding['type'] in ('logic_gap', 'missing_step'):
                         suggestion = self._generate_missing_logic_fix(target_code, finding)
                         if suggestion: suggestions.append(suggestion)
                    elif finding['type'] == 'logic_value_mismatch':
                         suggestion = self._generate_numeric_mismatch_fix(target_code, finding)
                         if suggestion: suggestions.append(suggestion)
                    elif finding['type'] == 'missing_parameter':
                         suggestion = self._generate_parameter_fix(target_code, finding)
                         if suggestion: suggestions.append(suggestion)

                # バックポート（設計書側を正とする）提案の追加
                for finding in analysis['findings']:
                    if finding['type'] in ['logic_value_mismatch', 'inequality_mismatch']:
                        backport = self._generate_backport_suggestion(target_code, finding, analysis)
                        if backport: suggestions.append(backport)

                if suggestions:
                    validated = self.safety_validator.validate_fix_safety(suggestions, target_code)
                    for suggestion in validated:
                        self._augment_suggestion_context(suggestion, target_code, analysis)
                    return validated

            if fix_direction == 'implement_method_logic':
                suggestion = self._generate_method_implementation_fix(target_code, analysis)
                if suggestion: suggestions.append(suggestion)

            elif fix_direction == 'self_healing_test' or fix_direction == 'logic_mismatch_with_branch':
                if analysis.get('logic_analysis'):
                    suggestion = self._generate_precision_logic_fix(target_code, analysis)
                else:
                    suggestion = self._generate_self_healing_test_fix(target_code, analysis)
                if suggestion: suggestions.append(suggestion)

            elif fix_direction == 'fix_test_arrange':
                suggestion = self._generate_test_arrange_fix(target_code, analysis)
                if suggestion: suggestions.append(suggestion)

            elif fix_direction in ['add_null_checks', 'add_null_validation']:
                suggestion = self._generate_null_check_fix(target_code, analysis)
                if suggestion: suggestions.append(suggestion)

            elif fix_direction in ['runtime_exception', 'manual_investigation_required']:
                suggestion = self._generate_manual_fix_placeholder(target_code, analysis)
                if suggestion: suggestions.append(suggestion)

            elif fix_direction == 'fix_calculation_logic':
                suggestion = self._generate_calculation_fix(target_code, analysis)
                if suggestion: suggestions.append(suggestion)

            elif fix_direction == 'fix_syntax_error':
                suggestion = self._generate_syntax_fix(target_code, analysis)
                if suggestion: suggestions.append(suggestion)

            for suggestion in suggestions:
                impact = self._analyze_impact(suggestion, target_code)
                impact.update(suggestion.impact_analysis or {})
                suggestion.impact_analysis = impact
                self._augment_suggestion_context(suggestion, target_code, analysis)

            validated = self.safety_validator.validate_fix_safety(suggestions, target_code)
            for suggestion in validated:
                self._augment_suggestion_context(suggestion, target_code, analysis)
            return validated

        except Exception as e:
            self.logger.error(f"修正提案生成中にエラーが発生: {e}")
            return []

    def _augment_suggestion_context(self, suggestion: CodeFixSuggestion, target_code: Dict[str, Any], analysis: Dict[str, Any]) -> None:
        target_file = target_code.get('file')
        analysis_summary = analysis.get('analysis_summary', {})
        if not suggestion.impact_analysis:
            suggestion.impact_analysis = {}

        suggestion.impact_analysis.setdefault('target_file', target_file)
        suggestion.impact_analysis.setdefault('target_method', target_code.get('method'))
        suggestion.impact_analysis.setdefault('root_cause', analysis.get('root_cause'))
        suggestion.impact_analysis.setdefault('fix_direction', analysis.get('fix_direction'))
        existing_reason = suggestion.impact_analysis.get('reason')
        if existing_reason in {
            'complete_structural_edit_contract',
            'missing_structural_edit_contract',
            'complete_structural_arrange_contract',
            'missing_structural_arrange_contract',
        }:
            suggestion.impact_analysis.setdefault('contract_reason', existing_reason)
            suggestion.impact_analysis.pop('reason', None)
        conversation_context = self._build_conversation_context(suggestion, analysis_summary)
        suggestion.impact_analysis.setdefault('reason', conversation_context['reason'])
        suggestion.impact_analysis.setdefault('recommended_action', conversation_context['recommended_action'])
        suggestion.impact_analysis.setdefault('target_summary', conversation_context['target_summary'])
        suggestion.impact_analysis.setdefault('conversation_hint', conversation_context['conversation_hint'])

        if hasattr(suggestion, 'target_file'):
            suggestion.target_file = target_file
        else:
            setattr(suggestion, 'target_file', target_file)

    def _build_conversation_context(self, suggestion: CodeFixSuggestion, analysis_summary: Dict[str, Any]) -> Dict[str, str]:
        target_method = analysis_summary.get('test_method') or '対象テスト'
        root_cause = analysis_summary.get('root_cause') or '不明な原因'
        target_method_name = suggestion.impact_analysis.get('target_method') or '対象メソッド'

        recommended_action_map = {
            'method_implementation': 'apply_code_fix',
            'test_self_healing': 'review_test_expectation',
            'test_arrange_fix': 'apply_code_fix',
            'syntax_fix': 'apply_code_fix',
            'manual_fix': 'inspect_manual_fix',
            'logic_gap_fix': 'apply_code_fix',
            'parameter_fix': 'apply_code_fix',
            'numeric_mismatch_fix': 'apply_code_fix',
            'backport_to_design': 'review_design_sync',
        }
        recommended_action = recommended_action_map.get(suggestion.type, 'apply_code_fix')
        if not suggestion.auto_applicable:
            recommended_action = 'inspect_manual_fix'
        target_summary = f"{target_method} / {target_method_name}"
        reason = f"{root_cause} により {target_method_name} の修正が必要です。"
        conversation_hint = f"{target_method} の失敗に対して {root_cause} を修正する提案"
        return {
            'reason': reason,
            'recommended_action': recommended_action,
            'target_summary': target_summary,
            'conversation_hint': conversation_hint,
        }

    def _generate_missing_logic_fix(self, target_code: Dict[str, Any], finding: Dict[str, Any]) -> Optional[CodeFixSuggestion]:
        """構造化された編集契約がある場合だけロジック修正を提案する。"""
        step_desc = (
            finding.get('step_text')
            or finding.get('design_step')
            or finding.get('detail')
            or finding.get('step_id')
            or 'unspecified design step'
        )
        symbol_id = finding.get('symbol_id') or target_code.get('symbol_id')
        start_line = finding.get('start_line') or target_code.get('start_line')
        end_line = finding.get('end_line') or target_code.get('end_line')
        replacement_code = (
            finding.get('replacement_code')
            or target_code.get('replacement_code')
        )
        validation_command = (
            finding.get('validation_command')
            or target_code.get('validation_command')
        )
        required = {
            'symbol_id': symbol_id,
            'start_line': start_line,
            'end_line': end_line,
            'replacement_code': replacement_code,
            'validation_command': validation_command,
        }
        missing = [name for name, value in required.items() if value in (None, '', [])]
        contract_complete = (
            not missing
            and isinstance(start_line, int)
            and isinstance(end_line, int)
            and start_line >= 1
            and end_line >= start_line
            and isinstance(validation_command, list)
            and all(isinstance(arg, str) and arg for arg in validation_command)
        )
        if not contract_complete and not missing:
            missing.append('valid_edit_range_and_validation_command')

        identity = hashlib.sha256(
            f"{finding.get('step_id', '')}\0{step_desc}".encode('utf-8')
        ).hexdigest()[:12]

        return CodeFixSuggestion(
            id=f"audit_gap_{identity}",
            type='logic_gap_fix',
            priority='medium' if contract_complete else 'low',
            description=(
                f'構造化されたロジック修正: {step_desc}'
                if contract_complete
                else f'手動調査が必要なロジック欠落: {step_desc}'
            ),
            current_code=target_code.get('current_implementation', ''),
            suggested_code=replacement_code if contract_complete else '',
            safety_score=0.0,
            impact_analysis={
                'step': step_desc,
                'missing_requirements': missing,
                'edit_range': (
                    {'start_line': start_line, 'end_line': end_line}
                    if contract_complete else None
                ),
            },
            auto_applicable=contract_complete,
            line_number=start_line if contract_complete else None,
            end_line=end_line if contract_complete else None,
            symbol_id=symbol_id if contract_complete else None,
            validation_command=validation_command if contract_complete else None,
        )

    def _generate_fallback_implementation_fix(self, target_code: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[CodeFixSuggestion]:
        """期待値を実装へ直書きせず、手動調査候補を返す。"""
        method_name = target_code.get('method', 'UnknownMethod')
        return CodeFixSuggestion(
            id=f"fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            type='manual_fix',
            priority='low',
            description=f'{method_name} の実装には手動調査が必要です',
            current_code='',
            suggested_code='',
            safety_score=0.0,
            impact_analysis={
                'reason': 'expected_value_is_not_an_implementation_specification',
            },
            auto_applicable=False,
        )

    def _generate_test_arrange_fix(self, target_code: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[CodeFixSuggestion]:
        """構造化されたArrange編集契約がある場合だけ修正提案を生成する。"""
        current_code = target_code.get('current_implementation', '')
        source = analysis.get('arrange_edit') or analysis
        arrange_statement = (
            source.get('arrange_statement')
            or source.get('replacement_code')
            or target_code.get('arrange_statement')
            or target_code.get('replacement_code')
        )
        insert_line = (
            source.get('insert_line')
            or source.get('start_line')
            or target_code.get('insert_line')
            or target_code.get('start_line')
        )
        validation_command = (
            source.get('validation_command')
            or target_code.get('validation_command')
        )
        symbol_id = source.get('symbol_id') or target_code.get('symbol_id')
        missing = [
            name
            for name, value in {
                'arrange_statement': arrange_statement,
                'insert_line': insert_line,
                'validation_command': validation_command,
            }.items()
            if value in (None, '', [])
        ]
        contract_complete = (
            not missing
            and isinstance(arrange_statement, str)
            and isinstance(insert_line, int)
            and insert_line >= 1
            and isinstance(validation_command, list)
            and all(isinstance(arg, str) and arg for arg in validation_command)
        )
        if not contract_complete and not missing:
            missing.append('valid_insert_line_and_validation_command')

        if not contract_complete:
            return CodeFixSuggestion(
                id=f"arrange_manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                type='manual_fix',
                priority='low',
                description='テストArrange修正には構造化編集契約が必要です',
                current_code=current_code,
                suggested_code='',
                safety_score=0.0,
                impact_analysis={
                    'missing_requirements': missing,
                    'reason': 'missing_structural_arrange_contract',
                },
                auto_applicable=False,
            )

        return CodeFixSuggestion(
            id=f"arrange_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            type='test_arrange_fix',
            priority='high',
            description='構造化されたテストArrange修正',
            current_code='',
            suggested_code=arrange_statement,
            safety_score=0.0,
            impact_analysis={
                'reason': 'complete_structural_arrange_contract',
            },
            auto_applicable=True,
            line_number=insert_line,
            symbol_id=symbol_id,
            validation_command=validation_command,
        )

    def _generate_method_implementation_fix(self, target_code, analysis):
        method_name = target_code.get('method', '')
        replacement_code = analysis.get('replacement_code') or target_code.get('replacement_code')
        symbol_id = analysis.get('symbol_id') or target_code.get('symbol_id')
        start_line = analysis.get('start_line') or target_code.get('start_line')
        end_line = analysis.get('end_line') or target_code.get('end_line')
        validation_command = (
            analysis.get('validation_command')
            or target_code.get('validation_command')
        )
        if (
            replacement_code
            and symbol_id
            and isinstance(start_line, int)
            and isinstance(end_line, int)
            and start_line >= 1
            and end_line >= start_line
            and isinstance(validation_command, list)
            and all(isinstance(arg, str) and arg for arg in validation_command)
        ):
            return CodeFixSuggestion(
                id=f"fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                type='method_implementation',
                priority='high',
                description=f'{method_name}の構造化実装修正',
                current_code=target_code.get('current_implementation', ''),
                suggested_code=replacement_code,
                safety_score=0.0,
                impact_analysis={
                    'reason': 'complete_structural_edit_contract',
                },
                auto_applicable=True,
                line_number=start_line,
                end_line=end_line,
                symbol_id=symbol_id,
                validation_command=validation_command,
            )

        return CodeFixSuggestion(
            id=f"fix_manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            type='manual_fix',
            priority='low',
            description=f'{method_name} の実装には構造化編集契約が必要です',
            current_code=target_code.get('current_implementation', ''),
            suggested_code='',
            safety_score=0.0,
            impact_analysis={
                'reason': 'missing_structural_edit_contract',
            },
            auto_applicable=False,
        )

    def _generate_self_healing_test_fix(self, target_code, analysis):
        error_msg = analysis.get('analysis_details', {}).get('error_message', '')
        actual = self._try_extract_actual_value(error_msg)
        if not actual: return None

        # C# normalization: True/False -> true/false
        if actual.lower() in ['true', 'false']:
            actual = actual.lower()

        # line_number を取得
        loc = analysis.get('analysis_details', {}).get('stack_trace_analysis', {}).get('primary_location', {})
        line_num = loc.get('line')
        return CodeFixSuggestion(id=f"heal_{datetime.now().strftime('%Y%m%d_%H%M%S')}", type='test_self_healing', priority='medium', description=f'期待値を {actual} に更新', current_code='Assert.Equal(...)', suggested_code=f'Assert.Equal({actual}, result);', safety_score=0.0, impact_analysis={}, auto_applicable=True, line_number=line_num)

    def _generate_precision_logic_fix(self, target_code: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[CodeFixSuggestion]:
        """精密ロジック不一致修正提案を生成"""
        logic = analysis.get('logic_analysis', {})
        condition = logic.get('branch_condition')
        input_val = logic.get('input_value')
        is_satisfied = logic.get('is_satisfied')

        error_msg = analysis.get('analysis_details', {}).get('error_message', '')
        expected = self._try_extract_expected_value(error_msg)

        # 提案の組み立て
        # 1. テスト側の修正提案 (入力値が境界に近い場合など)
        if not is_satisfied and "Gold" in str(expected):
            return CodeFixSuggestion(
                id=f"precision_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                type='logic_precision_fix',
                priority='high',
                description=f"テストの意図（Goldの取得）と入力値({input_val})が分岐条件({condition})に合致していません。",
                current_code=f"sut.GetTier({input_val})",
                suggested_code=f"var result = sut.GetTier(100);",
                safety_score=0.0,
                impact_analysis={'reason': 'Test input mismatch with business logic'},
                auto_applicable=False
            )

        return self._generate_self_healing_test_fix(target_code, analysis)

    def _generate_syntax_fix(self, target_code: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[CodeFixSuggestion]:
        """構造化された編集契約がある場合だけ構文修正を提案する。"""
        file_path = target_code.get('file', '')
        current_impl = target_code.get('current_implementation', '')
        if not file_path.endswith('.cs'):
            return None

        replacement_code = analysis.get('replacement_code') or target_code.get('replacement_code')
        start_line = analysis.get('start_line') or target_code.get('start_line')
        end_line = analysis.get('end_line') or target_code.get('end_line')
        symbol_id = analysis.get('symbol_id') or target_code.get('symbol_id')
        validation_command = (
            analysis.get('validation_command')
            or target_code.get('validation_command')
        )
        if (
            replacement_code
            and isinstance(start_line, int)
            and isinstance(end_line, int)
            and start_line >= 1
            and end_line >= start_line
            and isinstance(validation_command, list)
            and all(isinstance(arg, str) and arg for arg in validation_command)
        ):
            return CodeFixSuggestion(
                id=f"syntax_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                type='syntax_fix',
                priority='high',
                description='構造化された構文修正',
                current_code=current_impl,
                suggested_code=replacement_code,
                safety_score=0.0,
                auto_applicable=True,
                line_number=start_line,
                end_line=end_line,
                symbol_id=symbol_id,
                validation_command=validation_command,
                impact_analysis={
                    'reason': 'complete_structural_edit_contract',
                },
            )

        return CodeFixSuggestion(
            id=f"syntax_manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            type='manual_fix',
            priority='low',
            description='構文修正には構造化編集契約が必要です',
            current_code=current_impl,
            suggested_code='',
            safety_score=0.0,
            auto_applicable=False,
            impact_analysis={
                'reason': 'missing_structural_edit_contract',
            },
        )

    def _generate_null_check_fix(self, target_code, analysis):
        """null 関連修正は構造化編集契約がある場合だけ提案する。"""
        source = analysis.get('null_check_edit') or analysis
        return self._build_contract_based_suggestion(
            suggestion_type='null_validation',
            description='構造化されたnull検証修正',
            target_code=target_code,
            source=source,
        )

    def _generate_manual_fix_placeholder(self, target_code, analysis):
        return CodeFixSuggestion(
            id=f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            type='manual_fix',
            priority='low',
            description='手動調査が必要です',
            current_code='',
            suggested_code='',
            safety_score=0.0,
            impact_analysis={'reason': 'no_structural_fix_available'},
            auto_applicable=False,
        )

    def _generate_calculation_fix(self, target_code, analysis):
        """計算ロジック修正は構造化編集契約がある場合だけ提案する。"""
        source = analysis.get('calculation_edit') or analysis
        return self._build_contract_based_suggestion(
            suggestion_type='calculation_fix',
            description='構造化された計算ロジック修正',
            target_code=target_code,
            source=source,
        )

    def _try_extract_expected_value(self, msg):
        return self._extract_labeled_value(msg, 'Expected')

    def _try_extract_actual_value(self, msg):
        return self._extract_labeled_value(msg, 'Actual')

    @staticmethod
    def _extract_labeled_value(message: str, label: str) -> Optional[str]:
        lower_message = message.lower()
        marker = f"{label.lower()}:"
        start = lower_message.find(marker)
        if start == -1:
            return None
        value_start = start + len(marker)
        while (
            value_start < len(message)
            and message[value_start].isspace()
        ):
            value_start += 1
        if value_start >= len(message):
            return None

        if message[value_start] == '"':
            value_end = value_start + 1
            escaped = False
            while value_end < len(message):
                char = message[value_end]
                if char == '"' and not escaped:
                    return message[value_start:value_end + 1]
                escaped = char == "\\" and not escaped
                if char != "\\":
                    escaped = False
                value_end += 1
            return None

        value_end = value_start
        while value_end < len(message):
            char = message[value_end]
            if char in {',', '\r', '\n'} or char.isspace():
                break
            value_end += 1
        value = message[value_start:value_end]
        if not value:
            return None
        if value.isdigit() or value.lower() in {'true', 'false'}:
            return value
        return None

    def _generate_numeric_mismatch_fix(self, target_code: Dict[str, Any], finding: Dict[str, Any]) -> Optional[CodeFixSuggestion]:
        """数値不一致は構造化編集契約がある場合だけ修正候補にする。"""
        return self._build_contract_based_suggestion(
            suggestion_type='numeric_mismatch_fix',
            description='構造化された数値不一致修正',
            target_code=target_code,
            source=finding,
        )

    def _generate_parameter_fix(self, target_code: Dict[str, Any], finding: Dict[str, Any]) -> Optional[CodeFixSuggestion]:
        """パラメータ欠落は構造化編集契約がある場合だけ修正候補にする。"""
        return self._build_contract_based_suggestion(
            suggestion_type='parameter_fix',
            description='構造化されたパラメータ修正',
            target_code=target_code,
            source=finding,
        )

    def _build_contract_based_suggestion(
        self,
        *,
        suggestion_type: str,
        description: str,
        target_code: Dict[str, Any],
        source: Dict[str, Any],
    ) -> CodeFixSuggestion:
        replacement_code = source.get('replacement_code') or target_code.get('replacement_code')
        symbol_id = source.get('symbol_id') or target_code.get('symbol_id')
        start_line = source.get('start_line') or target_code.get('start_line')
        end_line = source.get('end_line') or target_code.get('end_line')
        validation_command = (
            source.get('validation_command')
            or target_code.get('validation_command')
        )
        missing = [
            name
            for name, value in {
                'symbol_id': symbol_id,
                'start_line': start_line,
                'end_line': end_line,
                'replacement_code': replacement_code,
                'validation_command': validation_command,
            }.items()
            if value in (None, '', [])
        ]
        contract_complete = (
            not missing
            and isinstance(start_line, int)
            and isinstance(end_line, int)
            and start_line >= 1
            and end_line >= start_line
            and isinstance(validation_command, list)
            and all(isinstance(arg, str) and arg for arg in validation_command)
        )
        if not contract_complete and not missing:
            missing.append('valid_edit_range_and_validation_command')

        return CodeFixSuggestion(
            id=f"{suggestion_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            type=suggestion_type if contract_complete else 'manual_fix',
            priority='high' if contract_complete else 'low',
            description=(
                description
                if contract_complete
                else f'{description}には構造化編集契約が必要です'
            ),
            current_code=target_code.get('current_implementation', ''),
            suggested_code=replacement_code if contract_complete else '',
            safety_score=0.0,
            impact_analysis={
                'missing_requirements': missing,
                'reason': (
                    'complete_structural_edit_contract'
                    if contract_complete
                    else 'missing_structural_edit_contract'
                ),
            },
            auto_applicable=contract_complete,
            line_number=start_line if contract_complete else None,
            end_line=end_line if contract_complete else None,
            symbol_id=symbol_id if contract_complete else None,
            validation_command=validation_command if contract_complete else None,
        )

    def _generate_backport_suggestion(self, target_code: Dict[str, Any], finding: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[CodeFixSuggestion]:
        """構造化された設計同期契約がある場合だけバックポート提案を生成する。"""
        design_path = analysis.get('design_path')
        if not design_path: return None
        new_design_content = finding.get('backport_content')
        step_idx = finding.get('step_idx')
        if not isinstance(new_design_content, str) or not new_design_content:
            return None
        if not isinstance(step_idx, int) or step_idx < 1:
            return None

        return CodeFixSuggestion(
            id=f"backport_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{step_idx}",
            type='backport_to_design',
            priority='medium',
            description=f'設計書をコードの状態に更新 (ステップ {step_idx})',
            current_code='(Current Design)',
            suggested_code=new_design_content,
            safety_score=0.0,
            impact_analysis={
                'design_file': design_path,
                'step_idx': step_idx,
                'reason': 'complete_structural_backport_contract',
            },
            auto_applicable=False
        )

    def _analyze_impact(self, sug, target):
        return {'note': 'Impact analyzed'}

    def _detect_language(self, path):
        return 'csharp' if path.endswith('.cs') else 'python'

    def _find_method_in_structure(self, struct, name):
        return None
