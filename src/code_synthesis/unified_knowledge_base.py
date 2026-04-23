# -*- coding: utf-8 -*-
import os
import json
import copy
import numpy as np
from typing import List, Dict, Any, Optional

from src.code_synthesis.method_store import MethodStore
from src.autonomous_learning.structural_memory import StructuralMemory
from src.code_synthesis.type_system import TypeSystem

class UnifiedKnowledgeBase:
    """
    MethodStore (External/Standard Libs) と StructuralMemory (Internal Project Code) を
    統合的に検索・管理するファサードクラス。
    """
    
    # 意図（Intent）と能力（Capability）の論理的整合性マップ
    INTENT_CAPABILITY_MAP = {
        "FETCH": ["DATA_FETCH", "FETCH", "READ", "FILE_IO", "HTTP_REQUEST", "DATABASE_ACCESS", "DATABASE_QUERY", "JSON_DESERIALIZE"],
        "PERSIST": ["DATA_PERSIST", "PERSIST", "WRITE", "FILE_IO", "DATABASE_ACCESS", "DATABASE_QUERY"],
        "DATABASE_QUERY": ["DATABASE_ACCESS", "DATABASE_QUERY", "DATA_FETCH", "FETCH", "PERSIST"],
        "HTTP_REQUEST": ["HTTP_REQUEST", "DATA_FETCH", "FETCH"],
        "FILE_IO": ["FILE_IO", "READ", "WRITE", "PERSIST", "FETCH"],
        "TRANSFORM": ["TRANSFORM", "TRANSFORMATION", "SERIALIZATION", "JSON_DESERIALIZE", "LINQ"],
        "LINQ": ["LINQ", "TRANSFORM", "TRANSFORMATION"],
        "DISPLAY": ["DISPLAY", "LOGGING", "USER_INTERFACE"],
        "EXISTS": ["EXISTS", "FILE_IO"],
        "CALC": ["CALCULATION", "CALC"],
        "RETURN": ["RETURN"]
    }

    def __init__(self, config_manager, method_store: MethodStore, structural_memory: StructuralMemory):
        self.config = config_manager
        self.method_store = method_store
        self.structural_memory = structural_memory
        self.type_system = TypeSystem()
        self.patterns = self._load_patterns()
        self.canonical_data = self._load_canonical_knowledge()
        # Disable keyword-based ontology boosting by default
        self.DOMAIN_ONTOLOGY = {}
        
    def _load_patterns(self) -> List[Dict[str, Any]]:
        """定石パターンをロードする"""
        path = os.path.join(getattr(self.config, 'workspace_root', os.getcwd()), "resources", "action_patterns.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("patterns", [])
            except Exception as e:
                print(f"Error loading action patterns: {e}")
        return []

    def _load_canonical_knowledge(self) -> Dict[str, Any]:
        """プロジェクト共通の知識ベースをロードする"""
        root = getattr(self.config, 'workspace_root', os.getcwd())
        path = os.path.join(root, "resources", "canonical_knowledge.json")
        if not os.path.exists(path):
            fallback_root = os.getcwd()
            if fallback_root != root:
                fallback_path = os.path.join(fallback_root, "resources", "canonical_knowledge.json")
                if os.path.exists(fallback_path):
                    path = fallback_path
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading canonical knowledge: {e}")
        return {}

    def get(self, key: str, default: Any = None) -> Any:
        """知識ベースから情報を取得する"""
        return self.canonical_data.get(key, default)

    def get_method_by_id(self, m_id: str) -> Optional[Dict[str, Any]]:
        """ID でメソッド定義を直接取得する。内部・外部・テンプレートの両方を探索する"""
        # 1. Check templates (canonical knowledge)
        if self.canonical_data:
            for t in self.canonical_data.get("templates", []):
                if t.get("id") == m_id:
                    t_copy = copy.deepcopy(t)
                    t_copy['origin'] = 'template'
                    return t_copy

        # 2. External methods
        m = self.method_store.methods.get(m_id)
        if m: 
            m_copy = copy.deepcopy(m)
            m_copy['origin'] = 'external'
            return m_copy
        
        # 3. Internal components (AST memory)
        for comp in self.structural_memory.components:
            if comp.get('id') == m_id or comp.get('full_name') == m_id:
                m_copy = copy.deepcopy(comp)
                m_copy['origin'] = 'internal'
                return m_copy
        return None

    def search(self, query: str, limit: int = 10, 
               intent: str = None, 
               target_entity: str = None, 
               return_type: str = None,
               input_type: str = None,
               exclude_patterns: bool = False,
               requested_role: str = None) -> List[Dict[str, Any]]:
        """
        統合検索を実行する。
        """
        # 1. 各ストアからの候補取得
        external_candidates = self.method_store.search(
            query, limit=limit * 10, intent=intent, input_type=input_type
        )
        
        internal_candidates = self.structural_memory.search_component(
            query, top_k=limit * 2, semantic_weight=0.7
        )
        
        # 2. パターンのマッチング
        pattern_candidates = []
        if intent and not exclude_patterns:
            # LINQ と CALC は定石パターンよりも個別のメソッド（および SemanticBinder）を優先すべき
            if intent not in ["LINQ", "CALC"]:
                for p in self.patterns:
                    match = (p.get("intent") == intent or any(cap in (self.INTENT_CAPABILITY_MAP.get(intent, [])) for cap in p.get("capabilities", [])))
                    if match:
                        p_copy = copy.deepcopy(p)
                        p_copy['origin'] = 'pattern'
                        p_copy['score'] = 1.0 # インテントが合致すれば高スコア
                        pattern_candidates.append(p_copy)

        # 2.5: テンプレートのマッチング (canonical_knowledge.json)
        canonical_candidates = []
        if intent and self.canonical_data:
            for t in self.canonical_data.get("templates", []):
                t_intent = t.get("intent")
                t_caps = t.get("capabilities", [])
                if t_intent == intent or any(cap in (self.INTENT_CAPABILITY_MAP.get(intent, [])) for cap in t_caps):
                    t_copy = copy.deepcopy(t)
                    t_copy['origin'] = 'template'
                    t_copy['score'] = 0.9
                    canonical_candidates.append(t_copy)

        # 3. 候補の統合
        unified_candidates = []
        unified_candidates.extend(pattern_candidates)
        unified_candidates.extend(canonical_candidates)

        for item in external_candidates:
            item['origin'] = 'external'
            unified_candidates.append(item)
            
        for item in internal_candidates:
            item['origin'] = 'internal'
            if 'return_type' not in item and 'returnType' in item:
                item['return_type'] = item['returnType']
            if 'capabilities' not in item:
                item['capabilities'] = [] 
            unified_candidates.append(item)
            
        # 4. 統合ランキング
        scored_results = self._rank_candidates(unified_candidates, query, intent, target_entity, return_type, input_type, requested_role=requested_role)
        
        return scored_results[:limit]

    def _rank_candidates(self, candidates: List[Dict[Any, Any]], 
                         query: str, intent: str, target_entity: str, 
                         expected_return_type: str,
                         input_type: str = None,
                         requested_role: str = None) -> List[Dict[Any, Any]]:
        """
        決定論的なランク付けを行う。
        (ノイズ排除, テンプレート優先, 階層優先, 意図一致, エンティティ一致, 型適合)
        """
        results = []
        allowed_caps = self.INTENT_CAPABILITY_MAP.get(intent, []) if intent else []
        # 27.285: Method Blacklist - Methods that cause known regressions or loops
        blacklist = ["Enumerable.ToList", "List.Add", "GenericAction"]

        for item in candidates:
            m_name = str(item.get('name', ''))
            m_class = str(item.get('class', ''))
            m_id = str(item.get('id', ''))
            
            # --- Blacklist Check ---
            if any(b in m_id or (b in m_name and b in m_class) for b in blacklist):
                continue

            # --- 0. ノイズ排除 (Internal Namespace Exclusion) ---
            # 開発者が直接触るべきでない内部用・メタデータ用名前空間を排除
            noise_namespaces = [".Serialization.Metadata", ".Internal.", ".Reflection.", "IJsonOn", "JsonMetadataServices", "NonValidated", "IJsonSerializable"]
            if any(ns in m_class or ns in m_name for ns in noise_namespaces):
                continue
            
            # 27.19: Exclude internal methods starting with underscore from ranking
            if m_name.startswith("_"):
                continue

            # 識別子の妥当性チェック
            if '`' in m_name or '`' in m_class or '<' in m_name or '$' in m_name:
                continue
            if m_name.startswith('get_') or m_name.startswith('set_'):
                continue

            # --- 1. テンプレート優先 (Template Prioritization) ---
            # Explicit templates/patterns only (no keyword/class-name inference).
            template_priority = 0
            if item.get('origin') == 'pattern':
                template_priority = 25 # 定石パターンを最優先にする
            elif item.get('origin') == 'template':
                template_priority = 20

            # --- 2. Capability による厳格なフィルタリング ---
            item_caps = item.get('capabilities', [])
            is_internal = item.get('origin') == 'internal'
            m_role = item.get('role') or item.get('intent')

            if intent and intent != "GENERAL" and allowed_caps:
                if not item_caps:
                    # No keyword-based inference; require explicit role match if capabilities are missing.
                    if m_role not in allowed_caps:
                        continue
                elif not any(cap in allowed_caps for cap in item_caps):
                    continue

            # --- 3. アーキテクチャ階層（Tier）優先 ---
            tier = item.get('tier', 3)
            tier_priority = 0
            if intent in ["HTTP_REQUEST", "DATABASE_QUERY", "FILE_IO"]:
                if tier == 3: tier_priority = 3 
                elif tier == 2: tier_priority = 2
                else: tier_priority = 1
            else:
                if tier == 1: tier_priority = 2
                elif tier == 2: tier_priority = 1
                else: tier_priority = 0
            if is_internal: tier_priority = 4

            # --- 4. 意図の完全一致ブースト ---
            intent_priority = 0
            if intent and (m_role == intent or item.get('intent') == intent):
                intent_priority = 2
            elif intent and m_role in self.INTENT_CAPABILITY_MAP.get(intent, []):
                intent_priority = 1
            
            # 27.430: Role-based prioritization boost
            role_priority = 0
            if item.get('role') == item.get('requested_role'): # ActionSynthesizer needs to pass this
                role_priority = 5
            elif item.get('role') in ["WRITE", "PERSIST"] and item.get('requested_role') == "WRITE":
                role_priority = 4
            elif item.get('role') in ["READ", "FETCH"] and item.get('requested_role') == "READ":
                role_priority = 4

            # --- 5. エンティティ一致 ---
            entity_match = 0
            if target_entity:
                target_low = target_entity.lower()
                # 27.98: If target is a primitive type, templates matching the intent get a small boost
                is_primitive = target_low in ["string", "int", "bool", "decimal", "double", "float", "object", "void"]
                
                if target_low in m_name.lower() or target_low in m_class.lower(): entity_match = 2
                elif is_primitive and item.get('origin') == 'template': entity_match = 1
                elif '<T>' in item.get('definition', '') or 'T ' in item.get('return_type', '') or item.get('requires_generic'): entity_match = 1
                
            # --- 6. 型適合性 ---
            input_match = 1
            if input_type:
                params = item.get('params', [])
                if params:
                    p0_type = params[0].get('type', '')
                    is_compat, _, _ = self.type_system.is_compatible(p0_type, input_type)
                    input_match = 2 if is_compat else 0
                else: input_match = 1

            type_match = 1 
            if expected_return_type:
                ret_type = item.get('return_type') or item.get('returnType') or "void"
                is_compat, score, _ = self.type_system.is_compatible(expected_return_type, ret_type)
                if is_compat:
                    type_match = 3 if score >= 100 else 2
                else:
                    # 27.23: Explicit skip for return type mismatch when expected is known
                    continue
            
            # ランクタプル (最優先: 役割 > テンプレート > 階層 > 意図 > エンティティ > 型)
            item['rank_tuple'] = (role_priority, template_priority, tier_priority, intent_priority, entity_match, input_match, type_match)
            results.append(item)
            
        results.sort(key=lambda x: x['rank_tuple'], reverse=True)
        return results
