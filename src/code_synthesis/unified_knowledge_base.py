# -*- coding: utf-8 -*-
import os
import json
import copy
import numpy as np
import logging
from typing import List, Dict, Any, Optional

from src.code_synthesis.method_store import MethodStore
from src.autonomous_learning.structural_memory import StructuralMemory
from src.code_synthesis.type_system import TypeSystem
from src.utils.semantic_intents import (
    INTENT_CALC,
    INTENT_DATABASE_QUERY,
    INTENT_DISPLAY,
    INTENT_EXISTS,
    INTENT_FETCH,
    INTENT_FILE_IO,
    INTENT_GENERAL,
    INTENT_HTTP_REQUEST,
    INTENT_JSON_DESERIALIZE,
    INTENT_LINQ,
    INTENT_PERSIST,
    INTENT_RETURN,
    INTENT_TRANSFORM,
    ROLE_FETCH,
    ROLE_PERSIST,
    ROLE_READ,
    ROLE_WRITE,
)


class AmbiguousMethodCandidatesError(Exception):
    def __init__(self, candidate_ids: List[str]):
        self.candidate_ids = candidate_ids
        super().__init__(
            "Multiple structural candidates remain without a decisive structural discriminator."
        )


class UnifiedKnowledgeBase:
    """
    MethodStore (External/Standard Libs) と StructuralMemory (Internal Project Code) を
    統合的に検索・管理するファサードクラス。
    """
    
    # 意図（Intent）と能力（Capability）の論理的整合性マップ
    INTENT_CAPABILITY_MAP = {
        INTENT_FETCH: ["DATA_FETCH", INTENT_FETCH, "READ", INTENT_FILE_IO, INTENT_HTTP_REQUEST, "DATABASE_ACCESS", INTENT_DATABASE_QUERY, INTENT_JSON_DESERIALIZE],
        INTENT_PERSIST: ["DATA_PERSIST", INTENT_PERSIST, "WRITE", INTENT_FILE_IO, "DATABASE_ACCESS", INTENT_DATABASE_QUERY],
        INTENT_DATABASE_QUERY: ["DATABASE_ACCESS", INTENT_DATABASE_QUERY, "DATA_FETCH", INTENT_FETCH, INTENT_PERSIST],
        INTENT_HTTP_REQUEST: [INTENT_HTTP_REQUEST, "DATA_FETCH", INTENT_FETCH],
        INTENT_FILE_IO: [INTENT_FILE_IO, "READ", "WRITE", INTENT_PERSIST, INTENT_FETCH],
        INTENT_TRANSFORM: [INTENT_TRANSFORM, "TRANSFORMATION", "SERIALIZATION", INTENT_JSON_DESERIALIZE, INTENT_LINQ],
        INTENT_LINQ: [INTENT_LINQ, INTENT_TRANSFORM, "TRANSFORMATION"],
        INTENT_DISPLAY: [INTENT_DISPLAY, "LOGGING", "USER_INTERFACE"],
        INTENT_EXISTS: [INTENT_EXISTS, INTENT_FILE_IO],
        INTENT_CALC: ["CALCULATION", INTENT_CALC],
        INTENT_RETURN: [INTENT_RETURN]
    }

    def __init__(self, config_manager, method_store: MethodStore, structural_memory: StructuralMemory):
        self.config = config_manager
        self.method_store = method_store
        self.structural_memory = structural_memory
        self.type_system = TypeSystem()
        self.logger = logging.getLogger(__name__)
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
                self.logger.error("Error loading action patterns: %s", e)
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
                self.logger.error("Error loading canonical knowledge: %s", e)
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
               requested_role: str = None,
               source_kind: str = None) -> List[Dict[str, Any]]:
        """
        統合検索を実行する。
        """
        # 1. 各ストアからの候補取得
        external_candidates = self.method_store.search(
            query,
            limit=limit * 10,
        )

        internal_role = requested_role
        internal_capabilities = None
        if not internal_role and intent and intent != INTENT_GENERAL:
            internal_capabilities = [intent]
        
        internal_candidates = self.structural_memory.search_component(
            query,
            top_k=limit * 2,
            role=internal_role,
            capabilities=internal_capabilities,
            return_type=return_type,
        )
        
        # 2. パターンのマッチング
        pattern_candidates = []
        if intent and not exclude_patterns:
            # LINQ と CALC は定石パターンよりも個別のメソッド（および SemanticBinder）を優先すべき
            if intent not in [INTENT_LINQ, INTENT_CALC]:
                for p in self.patterns:
                    p_copy = copy.deepcopy(p)
                    p_copy['origin'] = 'pattern'
                    pattern_candidates.append(p_copy)

        # 2.5: テンプレートのマッチング (canonical_knowledge.json)
        canonical_candidates = []
        if intent and self.canonical_data:
            for t in self.canonical_data.get("templates", []):
                t_copy = copy.deepcopy(t)
                t_copy['origin'] = 'template'
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
            
        filtered_results = self._filter_candidates(
            unified_candidates,
            intent=intent,
            target_entity=target_entity,
            expected_return_type=return_type,
            input_type=input_type,
            requested_role=requested_role,
            source_kind=source_kind,
        )
        deduplicated = {}
        for item in filtered_results:
            identity = str(item.get("id") or item.get("full_name") or item.get("name"))
            current = deduplicated.get(identity)
            if current is None or (
                isinstance(item.get("score"), (int, float))
                and not isinstance(current.get("score"), (int, float))
            ):
                deduplicated[identity] = item
        ordered = sorted(
            deduplicated.values(),
            key=lambda item: (
                0 if isinstance(item.get("score"), (int, float)) else 1,
                -(float(item.get("score"))) if isinstance(item.get("score"), (int, float)) else 0,
                str(item.get("id") or item.get("full_name") or item.get("name")),
            ),
        )
        if len(ordered) <= 1:
            return ordered[:limit]
        raise AmbiguousMethodCandidatesError([
            str(item.get("id") or item.get("full_name") or item.get("name"))
            for item in ordered
        ])

    @staticmethod
    def _role_matches(actual_role: Optional[str], requested_role: Optional[str]) -> bool:
        if not requested_role:
            return True
        if actual_role == requested_role:
            return True
        compatible_roles = {
            ROLE_FETCH: {ROLE_READ},
            ROLE_READ: {ROLE_FETCH},
            ROLE_PERSIST: {ROLE_WRITE},
            ROLE_WRITE: {ROLE_PERSIST},
        }
        return actual_role in compatible_roles.get(requested_role, set())

    @staticmethod
    def _terminal_type_name(type_name: Optional[str]) -> Optional[str]:
        if not type_name:
            return None
        clean_name = str(type_name).strip()
        if not clean_name:
            return None
        return clean_name.split(".")[-1]

    def _declared_target_entity(
        self,
        item: Dict[Any, Any],
        *,
        intent: Optional[str],
        source_kind: Optional[str],
    ) -> Optional[str]:
        declared_entity = item.get("target_entity")
        if declared_entity:
            return str(declared_entity)
        if source_kind is None and intent == INTENT_TRANSFORM:
            return self._terminal_type_name(item.get("class"))
        return None

    def _filter_candidates(
        self,
        candidates: List[Dict[Any, Any]],
        *,
        intent: Optional[str],
        target_entity: Optional[str],
        expected_return_type: Optional[str],
        input_type: Optional[str],
        requested_role: Optional[str],
        source_kind: Optional[str],
    ) -> List[Dict[Any, Any]]:
        """明示された構造制約をすべて満たす候補だけを返す。"""
        results = []

        for item in candidates:
            m_name = str(item.get('name', ''))
            m_class = str(item.get('class', ''))

            # 識別子の妥当性チェック
            if '`' in m_name or '`' in m_class or '<' in m_name or '$' in m_name:
                continue

            item_caps = set(item.get('capabilities') or [])
            m_role = item.get('role') or item.get('intent')
            if intent and intent != INTENT_GENERAL:
                intent_matches = (
                    item.get("intent") == intent
                    or intent in item_caps
                    or self._role_matches(m_role, intent)
                )
                if not intent_matches:
                    continue
            if not self._role_matches(m_role, requested_role):
                continue
            declared_source_kind = item.get("source_kind")
            if not declared_source_kind:
                structural_target_sources = {
                    "_dbConnection": "db",
                    "_httpClient": "http",
                }
                declared_source_kind = structural_target_sources.get(item.get("target"))
            if source_kind and declared_source_kind != source_kind:
                continue
            declared_entity = self._declared_target_entity(
                item,
                intent=intent,
                source_kind=source_kind,
            )
            if target_entity:
                if declared_entity and declared_entity != target_entity:
                    continue
                if intent == INTENT_TRANSFORM and source_kind is None and not declared_entity:
                    continue
            if input_type:
                params = item.get('params', [])
                parameter_types = [
                    parameter.get("type")
                    for parameter in params
                    if isinstance(parameter, dict) and parameter.get("type")
                ]
                if not parameter_types or not any(
                    self.type_system.is_compatible(parameter_type, input_type)[0]
                    for parameter_type in parameter_types
                ):
                    continue
            if expected_return_type:
                ret_type = item.get('return_type') or item.get('returnType') or "void"
                if not self.type_system.is_compatible(expected_return_type, ret_type)[0]:
                    continue
            results.append(item)
        return results
