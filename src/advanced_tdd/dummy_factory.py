# -*- coding: utf-8 -*-
import re
from typing import Dict, Any, Optional, Set
from .models import TestFailure

class DummyDataFactory:
    """C#ダミーデータ生成ファクトリ (完全汎用・解析データ駆動版)"""
    
    def __init__(self, analysis_results: Optional[Dict[str, Any]] = None, knowledge_base: Any = None):
        # 型名 -> {プロパティ名: 推奨値}
        self.learned_rules: Dict[str, Dict[str, str]] = {}
        # 永続化用の知識ベース
        self.kb = knowledge_base
        if self.kb and hasattr(self.kb, 'type_mappings'):
            # 既存の知識を読み込み
            self.learned_rules.update(self.kb.type_mappings)
            
        # 解析結果 (ナレッジグラフ) を保持して動的な型解決に使用
        self.analysis_results = analysis_results
        self.property_types: Dict[str, str] = {}

    def learn_from_failure(self, failure: TestFailure) -> None:
        """テスト失敗から必要なプロパティや型を学習"""
        msg = failure.error_message
        
        # Pattern 1: CS1061 'Type' does not contain a definition for 'Member'
        m1 = re.search(r"'([^']+)' does not contain a definition for '([^']+)'", msg)
        
        # Pattern 2: "user.Profile is null" -> 変数名から型を推測
        m2 = re.search(r"(\w+)\.(\w+) is null", msg)
        
        # Pattern 3: "Property 'Amount' not found on type 'Order'"
        m3 = re.search(r"Property '(\w+)' not found on type '(\w+)'", msg)

        if m1:
            type_name, prop_name = m1.groups()
            self._add_learned_prop(type_name, prop_name)
        elif m2:
            var_name, prop_name = m2.groups()
            # 変数名から型名を推測 (簡易的に、先頭大文字に)
            type_name = var_name[0].upper() + var_name[1:]
            self._add_learned_prop(type_name, prop_name)
        elif m3:
            prop_name, type_name = m3.groups()
            self._add_learned_prop(type_name, prop_name)

    def _add_learned_prop(self, type_name: str, prop_name: str):
        if type_name not in self.learned_rules:
            self.learned_rules[type_name] = {}
        
        val = self._guess_value_for_prop(prop_name)
        self.learned_rules[type_name][prop_name] = val
        
        # ナレッジベースにも保存
        if self.kb and hasattr(self.kb, 'add_type_mapping'):
            self.kb.add_type_mapping(type_name, prop_name, val)

    def _guess_value_for_prop(self, prop_name: str) -> str:
        """プロパティ名から適切な値を推測 (テスト期待値に準拠)"""
        name_low = prop_name.lower()
        if 'email' in name_low: return '"test@example.com"'
        if 'firstname' in name_low: return '"John"'
        if 'name' in name_low: return '"Test User"'
        if 'age' in name_low: return '25'
        if 'amount' in name_low: return '10'
        if 'price' in name_low: return '1000'
        if 'createdat' in name_low or 'date' in name_low: return 'DateTime.Now'
        
        # デフォルトのオブジェクト生成
        if prop_name[0].isupper():
            return f"new {prop_name}()"
        return '"test_data"'

    def generate_instantiation(self, type_name: str) -> str:
        """型名からインスタンス化コードを生成"""
        t = type_name.strip()
        
        # 3. 基本型
        t_low = t.lower()
        if t_low in ['int', 'int32', 'long']: return '0'
        if t_low in ['string']: return '""'
        if t_low in ['bool', 'boolean']: return 'true'
        if t_low in ['decimal']: return '1.0m'
        if t_low in ['double', 'float']: return '1.0'
        if t == 'void': return ''

        # 名前空間の正規化
        t_clean = t.replace('System.Collections.Generic.', '').replace('System.', '').split('.')[-1]
        
        # 学習したプロパティがある場合、オブジェクト初期化子を使用
        if t_clean in self.learned_rules:
            props = self.learned_rules[t_clean]
            if props:
                assignments = [f"{k} = {v}" for k, v in props.items()]
                return f"new {t_clean} {{ {', '.join(assignments)} }}"

        # 1. 配列・リストの処理
        if '[]' in t:
            base_type = t_clean.replace('[]', '').strip()
            return f"new {base_type}[0]"
        if 'List<' in t or 'IEnumerable<' in t:
            inner_match = re.search(r'<(.*)>', t)
            inner = inner_match.group(1).split('.')[-1] if inner_match else "object"
            return f"new List<{inner}>()"

        # 2. モック化の判定
        is_interface = t_clean.startswith('I') and len(t_clean) > 1 and t_clean[1].isupper()
        abstract_hints = ['Model', 'Node', 'Symbol', 'Context', 'Provider', 'Service', 'Converter', 'Client']
        if is_interface or any(hint in t_clean for hint in abstract_hints):
            return f"Substitute.For<{t_clean}>()"
        
        # 3. 特殊なシステム型
        if t_clean == 'CancellationToken': return "CancellationToken.None"
        if t_clean == 'DateTime': return "DateTime.Now"
        
        # 4. 解析データに基づく動的生成
        if self.analysis_results:
            objects = self.analysis_results.get('manifest', {}).get('objects', [])
            target_obj = next((obj for obj in objects if obj['fullName'].endswith(t)), None)
            if target_obj:
                details = self.analysis_results.get('details_by_id', {}).get(target_obj['id'], {})
                ctors = details.get('constructors', [])
                if ctors:
                    public_ctors = [c for c in ctors if c.get('accessibility') == 'Public']
                    best_ctor = min(public_ctors or ctors, key=lambda c: len(c.get('parameters', [])))
                    args = [self.generate_instantiation(p['type']) if p['type'] != t else "null" for p in best_ctor.get('parameters', [])]
                    return f"new {t_clean}({', '.join(args)})"

        # 6. フォールバック
        return f"new {t_clean}()"