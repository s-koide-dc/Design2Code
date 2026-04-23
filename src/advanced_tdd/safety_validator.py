# -*- coding: utf-8 -*-
import os
import re
import logging
from typing import Dict, List, Any, Optional
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
        self.risk_thresholds = {
            'low': 0.8,
            'medium': 0.6,
            'high': 0.3
        }
        
        # 危険なパターン (単語境界 \b を追加して System 名前空間などとの誤認を防ぐ)
        self.dangerous_patterns = [
            r'\bdelete\b|\bremove\b|\bdrop\b|\btruncate\b',
            r'\bformat\b|\bwipe\b|\bclear\b',
            r'\bexec\s*\(|\beval\s*\(|\bsystem\s*\(', # 関数呼び出し形式に限定
            r'\bunsafe\b|\bunmanaged\b'
        ]
    
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
                
                # 安全性情報を更新
                suggestion.safety_score = basic_safety['score']
                suggestion.impact_analysis = impact_analysis
                suggestion.risk_assessment = risk_assessment
                suggestion.approval_workflow = approval_workflow
                
                # 安全性基準を満たす場合のみ追加
                # 緩和: 構文エラー修正やテスト自動修復は、危険なパターンさえなければ通過させる
                is_remedial_fix = suggestion.type in ['syntax_fix', 'test_self_healing', 'logic_gap_fix']
                
                if (basic_safety['passed'] and risk_assessment['level'] != 'critical') or \
                   (is_remedial_fix and basic_safety['score'] > 0.4):
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
        score = 1.0
        issues = []
        
        # 危険なパターンのチェック
        suggested_code_lower = suggestion.suggested_code.lower()
        for pattern in self.dangerous_patterns:
            if re.search(pattern, suggested_code_lower):
                score *= 0.3
                issues.append(f"危険なパターンを検出: {pattern}")
        
        # 修正タイプによる安全性評価
        type_safety_scores = {
            'method_implementation': 0.9,
            'null_validation': 0.95,
            'calculation_fix': 0.7,
            'syntax_fix': 0.85,
            'variable_declaration': 0.9,
            'logic_gap_fix': 0.95
        }
        
        type_score = type_safety_scores.get(suggestion.type, 0.5)
        score *= type_score
        
        # コード変更量による調整
        current_lines = len(suggestion.current_code.split('\n'))
        suggested_lines = len(suggestion.suggested_code.split('\n'))
        change_ratio = abs(suggested_lines - current_lines) / max(current_lines, 1)
        
        if change_ratio > 0.5:  # 50%以上の変更
            score *= 0.7
            issues.append("大幅なコード変更")
        elif change_ratio > 0.2:  # 20%以上の変更
            score *= 0.85
            issues.append("中程度のコード変更")
        
        return {
            'score': max(0.0, min(1.0, score)),
            'passed': score >= self.risk_thresholds['high'],
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
            
        # 2. 危険な操作の検出 (DB削除、ファイル上書きなど)
        risky_ops = self._detect_risky_operations(suggestion.suggested_code)
        if risky_ops:
            impact['risk_factors'].extend(risky_ops)

        # 3. 依存関係の分析 (SemanticAnalyzer活用)
        dependencies = target_code.get('dependencies', [])
        impact['affected_methods'].extend(dependencies)
        
        if self.semantic_analyzer:
            try:
                # 提案コードの意味解析
                analysis = self.semantic_analyzer.analyze_text(suggestion.suggested_code)
                entities = analysis.get('entities', [])
                
                # エンティティに基づく影響クラスの推論
                for entity in entities:
                    if entity[0].isupper(): # 簡易的なクラス名判定
                         if entity not in impact['affected_classes']:
                             impact['affected_classes'].append(entity)
                             
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

        # 依存関係の変更チェック
        if 'using ' in suggestion.suggested_code or 'import ' in suggestion.suggested_code:
            impact['dependency_changes'] = True

        return impact
    
    def _detect_risky_operations(self, code: str) -> List[str]:
        """危険な操作を検出"""
        risks = []
        code_lower = code.lower()
        
        if 'drop table' in code_lower or 'delete from' in code_lower:
            risks.append('データベース削除操作')
        
        if 'open(' in code_lower and ('w' in code_lower or 'wb' in code_lower):
            risks.append('ファイル上書き操作')
            
        if 'os.system' in code_lower or 'subprocess' in code_lower:
            risks.append('外部プロセス実行')
            
        return risks

    def _assess_risk_level(self, suggestion: CodeFixSuggestion, impact_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """リスクレベルを評価"""
        risk_score = suggestion.safety_score
        
        # 影響範囲による調整
        if impact_analysis['breaking_changes']:
            risk_score *= 0.5
        
        if impact_analysis['dependency_changes']:
            risk_score *= 0.8
        
        if len(impact_analysis['affected_methods']) > 3:
            risk_score *= 0.7
        
        # リスクレベルの決定
        if risk_score >= self.risk_thresholds['low']:
            level = 'low'
        elif risk_score >= self.risk_thresholds['medium']:
            level = 'medium'
        elif risk_score >= self.risk_thresholds['high']:
            level = 'high'
        else:
            level = 'critical'
        
        return {
            'level': level,
            'score': risk_score,
            'factors': self._identify_risk_factors(suggestion, impact_analysis)
        }
    
    def _determine_approval_workflow(self, risk_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """承認ワークフローを決定"""
        level = risk_assessment['level']
        
        workflows = {
            'low': {
                'auto_applicable': True,
                'approval_required': False,
                'reviewers': [],
                'estimated_time': '即座'
            },
            'medium': {
                'auto_applicable': False,
                'approval_required': True,
                'reviewers': ['developer'],
                'estimated_time': '5分'
            },
            'high': {
                'auto_applicable': False,
                'approval_required': True,
                'reviewers': ['developer', 'senior_developer'],
                'estimated_time': '15分'
            },
            'critical': {
                'auto_applicable': False,
                'approval_required': True,
                'reviewers': ['developer', 'senior_developer', 'architect'],
                'estimated_time': '30分以上'
            }
        }
        
        return workflows.get(level, workflows['critical'])
    
    def _check_breaking_changes(self, suggestion: CodeFixSuggestion, language: str = 'generic') -> bool:
        """破壊的変更をチェック"""
        try:
            # 言語ごとの構造解析
            current_struct = self.ast_analyzer.analyze_code_structure(suggestion.current_code, language)
            suggested_struct = self.ast_analyzer.analyze_code_structure(suggestion.suggested_code, language)
            
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
                # 構造化データがない場合は簡易文字列比較にフォールバック
                return self._check_breaking_changes_fallback(suggestion)

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
            self.logger.warning(f"シグネチャ比較中にエラーが発生。フォールバックを使用: {e}")
            return self._check_breaking_changes_fallback(suggestion)

    def _check_breaking_changes_fallback(self, suggestion: CodeFixSuggestion) -> bool:
        """シグネチャ比較のフォールバック（文字列ベース）"""
        current_sig = self._extract_method_signature(suggestion.current_code)
        suggested_sig = self._extract_method_signature(suggestion.suggested_code)
        
        if not current_sig or not suggested_sig:
             return False
             
        return current_sig.strip() != suggested_sig.strip()
    
    def _identify_risk_factors(self, suggestion: CodeFixSuggestion, impact_analysis: Dict[str, Any]) -> List[str]:
        """リスク要因を特定"""
        factors = []
        
        if impact_analysis['breaking_changes']:
            factors.append('破壊的変更の可能性')
        
        if impact_analysis['dependency_changes']:
            factors.append('依存関係の変更')
        
        if len(impact_analysis['affected_methods']) > 1:
            factors.append('複数メソッドへの影響')
        
        if suggestion.safety_score < 0.7:
            factors.append('低い安全性スコア')
        
        return factors
    
    def _extract_method_signature(self, code: str) -> str:
        """メソッドシグネチャを抽出"""
        lines = code.split('\n')
        for line in lines:
            if 'public ' in line and '(' in line and ')' in line:
                return line.strip()
        return ''
    
    def _extract_return_type_from_code(self, code: str) -> str:
        """コードから戻り値の型を抽出"""
        signature = self._extract_method_signature(code)
        if signature:
            parts = signature.split()
            for i, part in enumerate(parts):
                if part in ['public', 'private', 'protected', 'static']:
                    continue
                return part
        return ''
    
    def _count_parameters(self, code: str) -> int:
        """パラメータ数をカウント"""
        match = re.search(r'\(([^)]*)\)', code)
        if match:
            params = match.group(1).strip()
            if not params:
                return 0
            return len([p.strip() for p in params.split(',') if p.strip()])
        return 0
