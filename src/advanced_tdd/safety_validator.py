# -*- coding: utf-8 -*-
import os
import logging
from typing import Dict, List, Any
from .models import CodeFixSuggestion
from .ast_analyzer import ASTAnalyzer

class SafetyValidator:
    """修正案の安全性評価を担当するクラス"""
    
    def __init__(self, config: Dict[str, Any], semantic_analyzer=None, ast_analyzer=None):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.semantic_analyzer = semantic_analyzer
        self.ast_analyzer = ast_analyzer or ASTAnalyzer()
        
        # 安全性評価の設定
        self.safety_config = config.get('code_fix', {})
    
    def validate_fix_safety(self, suggestions: List[CodeFixSuggestion], target_code: Dict[str, Any]) -> List[CodeFixSuggestion]:
        """修正提案の安全性を検証"""
        validated_suggestions = []
        
        for suggestion in suggestions:
            try:
                # 1. 基本安全性チェック
                basic_safety = self._check_basic_safety(suggestion)
                
                # 2. 影響範囲分析
                impact_analysis = self._analyze_impact_scope(suggestion, target_code)
                
                # 3. リスク評価
                risk_assessment = self._assess_risk_level(suggestion, impact_analysis)
                
                # 4. 承認ワークフロー判定
                approval_workflow = self._determine_approval_workflow(risk_assessment)
                
                # 安全性情報を更新。safety_score は既存 API 互換の表示値として保持し、
                # 適用可否の根拠には使わない。
                suggestion.impact_analysis = impact_analysis
                suggestion.risk_assessment = risk_assessment
                suggestion.approval_workflow = approval_workflow
                
                if basic_safety['passed'] and risk_assessment['decision'] != 'reject':
                    validated_suggestions.append(suggestion)
                    self.logger.info(f"修正提案 {suggestion.id} が安全性検証を通過 (Type: {suggestion.type})")
                else:
                    self.logger.warning(f"修正提案 {suggestion.id} が安全性検証で却下: {basic_safety.get('reason', 'リスクレベルが高すぎます')}")
                    
            except Exception as e:
                self.logger.error(f"修正提案 {suggestion.id} の安全性検証中にエラー: {e}")
                continue
        
        return validated_suggestions
    
    def _check_basic_safety(self, suggestion: CodeFixSuggestion) -> Dict[str, Any]:
        """基本的な安全性チェック"""
        evidence = self._get_safety_evidence(suggestion)
        issues = self._normalise_evidence_list(evidence.get('blocking_risks', []))
        
        return {
            'score': suggestion.safety_score,
            'passed': len(issues) == 0,
            'issues': issues,
            'reason': '; '.join(issues) if issues else 'OK'
        }
    
    def _analyze_impact_scope(self, suggestion: CodeFixSuggestion, target_code: Dict[str, Any]) -> Dict[str, Any]:
        """影響範囲を詳細に分析"""
        impact = {
            'affected_methods': [],
            'affected_classes': [],
            'breaking_changes': False,
            'test_impact': 'unknown',
            'performance_impact': 'minimal',
            'maintainability_impact': 'neutral',
            'dependency_changes': False,
            'risk_factors': []
        }
        impact.update(suggestion.impact_analysis or {})
        
        # 言語の特定
        target_file = target_code.get('file', '')
        language = 'generic'
        if target_file.endswith('.cs'):
            language = 'csharp'
        elif target_file.endswith('.py'):
            language = 'python'
        elif target_file.endswith(('.js', '.ts')):
            language = 'javascript'

        # 1. 破壊的変更の検出 (シグネチャ変更)
        if self._check_breaking_changes(suggestion, language):
            impact['breaking_changes'] = True
            impact['risk_factors'].append('APIシグネチャの変更')
            
        # 2. リスク要因は上流の構造化 evidence のみ採用する。
        evidence = self._get_safety_evidence(suggestion)
        impact['risk_factors'].extend(self._normalise_evidence_list(evidence.get('risk_factors', [])))
        if evidence.get('dependency_changes') is not None:
            impact['dependency_changes'] = bool(evidence['dependency_changes'])

        # 3. 依存関係の分析 (SemanticAnalyzer活用)
        dependencies = target_code.get('dependencies', [])
        impact['affected_methods'].extend(dependencies)
        
        if self.semantic_analyzer:
            try:
                # 提案コードの意味解析結果は参考情報として保存する。
                # ここからクラス名やリスクを推定しない。
                analysis = self.semantic_analyzer.analyze_text(suggestion.suggested_code)
                impact['semantic_analysis'] = analysis
            except Exception as e:
                 self.logger.warning(f"SemanticAnalyzerによる影響分析に失敗: {e}")

        # 対象メソッドの特定
        target_method = target_code.get('method', 'unknown')
        if target_method != 'unknown':
            impact['affected_methods'].append(target_method)
        
        # 対象ファイルからクラス名を推定
        if target_file:
            class_name = os.path.splitext(os.path.basename(target_file))[0]
            if class_name not in impact['affected_classes']:
                impact['affected_classes'].append(class_name)
        
        # 修正タイプによる影響評価の微調整
        if suggestion.type == 'method_implementation':
            impact['test_impact'] = 'positive'
            impact['maintainability_impact'] = 'positive'
        elif suggestion.type == 'null_validation':
            impact['test_impact'] = 'positive'
            impact['performance_impact'] = 'minimal'
            impact['maintainability_impact'] = 'positive'
        elif suggestion.type == 'calculation_fix':
            impact['test_impact'] = 'positive'

        return impact

    def _assess_risk_level(self, suggestion: CodeFixSuggestion, impact_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """リスクレベルを評価"""
        evidence = self._get_safety_evidence(suggestion)
        factors = self._identify_risk_factors(suggestion, impact_analysis)
        blocking_risks = self._normalise_evidence_list(evidence.get('blocking_risks', []))

        explicit_level = evidence.get('risk_level') or impact_analysis.get('risk_level')
        level = explicit_level if explicit_level in {'low', 'medium', 'high', 'critical'} else 'unclassified'

        if blocking_risks:
            decision = 'reject'
            if level == 'unclassified':
                level = 'critical'
            factors.extend(blocking_risks)
        elif bool(evidence.get('requires_approval')):
            decision = 'review'
        else:
            decision = 'accept'
        
        return {
            'level': level,
            'score': suggestion.safety_score,
            'decision': decision,
            'requires_approval': bool(evidence.get('requires_approval')),
            'factors': self._deduplicate_preserving_order(factors)
        }
    
    def _determine_approval_workflow(self, risk_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """承認ワークフローを決定"""
        if risk_assessment['decision'] == 'accept':
            return {
                'auto_applicable': True,
                'approval_required': False,
                'reviewers': [],
                'estimated_time': '即座'
            }

        if risk_assessment['decision'] == 'review':
            return {
                'auto_applicable': False,
                'approval_required': True,
                'reviewers': ['developer'],
                'estimated_time': '5分'
            }
        
        return {
            'auto_applicable': False,
            'approval_required': True,
            'reviewers': ['developer', 'senior_developer', 'architect'],
            'estimated_time': '30分以上'
        }
    
    def _check_breaking_changes(self, suggestion: CodeFixSuggestion, language: str = 'generic') -> bool:
        """破壊的変更をチェック"""
        try:
            # 言語ごとの構造解析
            current_struct = self.ast_analyzer.analyze_code_structure(suggestion.current_code, language)
            suggested_struct = self.ast_analyzer.analyze_code_structure(suggestion.suggested_code, language)
            if (
                language == 'csharp'
                and (
                    current_struct.get('status') == 'structural_analysis_required'
                    or suggested_struct.get('status') == 'structural_analysis_required'
                )
            ):
                return False
            
            # 1. クラス名の変更チェック
            current_classes = [c['name'] for c in current_struct.get('structure', {}).get('classes', [])]
            suggested_classes = [c['name'] for c in suggested_struct.get('structure', {}).get('classes', [])]
            
            if current_classes and suggested_classes:
                if current_classes[0] != suggested_classes[0]:
                    return True
            
            # 2. メソッドシグネチャの比較
            current_methods = current_struct.get('structure', {}).get('methods', [])
            suggested_methods = suggested_struct.get('structure', {}).get('methods', [])
            
            if not current_methods or not suggested_methods:
                return False

            # 最初のメソッド同士を比較（単一メソッド修正を想定）
            curr = current_methods[0]
            sugg = suggested_methods[0]
            
            # 名前の不一致
            if curr.get('name') != sugg.get('name'):
                return True
                
            # 引数の不一致
            if curr.get('parameters') != sugg.get('parameters'):
                return True
                
            # 戻り値型の不一致
            if curr.get('return_type') != sugg.get('return_type'):
                # dynamic 同士なら許容
                if curr.get('return_type') != 'dynamic' or sugg.get('return_type') != 'dynamic':
                    return True

            return False
            
        except Exception as e:
            self.logger.warning(f"シグネチャ比較中にエラーが発生: {e}")
            return False

    def _identify_risk_factors(self, suggestion: CodeFixSuggestion, impact_analysis: Dict[str, Any]) -> List[str]:
        """リスク要因を特定"""
        factors = []
        
        if impact_analysis['breaking_changes']:
            factors.append('破壊的変更の可能性')
        
        if impact_analysis['dependency_changes']:
            factors.append('依存関係の変更')
        
        if len(impact_analysis['affected_methods']) > 1:
            factors.append('複数メソッドへの影響')
        
        factors.extend(self._normalise_evidence_list(impact_analysis.get('risk_factors', [])))
        return self._deduplicate_preserving_order(factors)

    def _get_safety_evidence(self, suggestion: CodeFixSuggestion) -> Dict[str, Any]:
        """提案に付与された構造化された安全性根拠を取得する"""
        impact = suggestion.impact_analysis or {}
        evidence = impact.get('safety_evidence', {})
        if isinstance(evidence, dict):
            return evidence
        return {}

    def _normalise_evidence_list(self, raw_items: Any) -> List[str]:
        """構造化 evidence のリスト表現を表示用の文字列リストへ正規化する"""
        if not raw_items:
            return []
        if not isinstance(raw_items, list):
            raw_items = [raw_items]

        items: List[str] = []
        for item in raw_items:
            if isinstance(item, dict):
                code = item.get('code') or item.get('id') or item.get('description')
                if code is not None:
                    items.append(str(code))
            elif item is not None:
                items.append(str(item))
        return self._deduplicate_preserving_order(items)

    def _deduplicate_preserving_order(self, items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result
