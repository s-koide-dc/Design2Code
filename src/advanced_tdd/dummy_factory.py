# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional
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

    def learn_from_failure(self, failure: TestFailure) -> bool:
        """非構造化エラーメッセージからは型情報を推測しない。"""
        return False

    def register_property(
        self,
        type_name: str,
        property_name: str,
        property_type: str,
    ) -> bool:
        """Roslyn等で解決済みのプロパティ情報を登録する。"""
        if not type_name or not property_name or not property_type:
            return False
        value = self._default_for_type(property_type)
        if value is None:
            return False
        if type_name not in self.learned_rules:
            self.learned_rules[type_name] = {}
        self.learned_rules[type_name][property_name] = value
        self.property_types[property_name] = property_type

        if self.kb and hasattr(self.kb, 'add_type_mapping'):
            self.kb.add_type_mapping(type_name, property_name, value)
        return True

    def register_accessed_properties(
        self,
        type_name: str,
        accessed_symbol_ids,
    ) -> int:
        """Roslynのsymbol IDで参照された対象型プロパティを登録する。"""
        if not self.analysis_results or not type_name:
            return 0
        manifest = self.analysis_results.get("manifest", {})
        details_by_id = self.analysis_results.get("details_by_id", {})
        normalized_type = type_name.replace("global::", "").strip()
        target_object = next(
            (
                item
                for item in manifest.get("objects", [])
                if item.get("fullName") == normalized_type
                or item.get("fullName", "").endswith(f".{normalized_type}")
            ),
            None,
        )
        if not target_object:
            return 0
        detail = details_by_id.get(target_object.get("id"), {})
        accessed_ids = {
            str(symbol_id)
            for symbol_id in accessed_symbol_ids or []
            if symbol_id
        }
        registered = 0
        for prop in detail.get("properties", []):
            if str(prop.get("id")) not in accessed_ids:
                continue
            if self.register_property(
                normalized_type.rsplit(".", 1)[-1],
                prop.get("name"),
                prop.get("type"),
            ):
                registered += 1
        return registered

    def _default_for_type(self, type_name: str) -> Optional[str]:
        normalized = type_name.strip().replace("global::", "")
        aliases = {
            "System.String": '""',
            "string": '""',
            "System.Boolean": "false",
            "bool": "false",
            "System.Int16": "0",
            "short": "0",
            "System.Int32": "0",
            "int": "0",
            "System.Int64": "0L",
            "long": "0L",
            "System.Single": "0.0f",
            "float": "0.0f",
            "System.Double": "0.0d",
            "double": "0.0d",
            "System.Decimal": "0.0m",
            "decimal": "0.0m",
            "System.DateTime": "default(DateTime)",
            "DateTime": "default(DateTime)",
        }
        if normalized in aliases:
            return aliases[normalized]
        if normalized.endswith("[]"):
            element_type = normalized[:-2].strip()
            return f"System.Array.Empty<{element_type}>()"
        if "<" in normalized and normalized.endswith(">"):
            outer, inner = normalized.split("<", 1)
            inner = inner[:-1].strip()
            collection_types = {
                "List",
                "System.Collections.Generic.List",
                "IEnumerable",
                "System.Collections.Generic.IEnumerable",
                "ICollection",
                "System.Collections.Generic.ICollection",
                "IReadOnlyList",
                "System.Collections.Generic.IReadOnlyList",
            }
            if outer in collection_types:
                return f"new System.Collections.Generic.List<{inner}>()"
        if normalized.endswith("?"):
            return None
        simple_name = normalized.rsplit(".", 1)[-1]
        return f"new {simple_name}()"

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
            inner = t.split("<", 1)[1].rsplit(">", 1)[0].split('.')[-1]
            return f"new List<{inner}>()"

        # 2. モック化の判定
        is_interface = t_clean.startswith('I') and len(t_clean) > 1 and t_clean[1].isupper()
        if is_interface:
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
