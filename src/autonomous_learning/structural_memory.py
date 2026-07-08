# -*- coding: utf-8 -*-
import os
import json
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from src.advanced_tdd.ast_analyzer import ASTAnalyzer
from src.semantic_search.semantic_search_base import SemanticSearchBase
from src.utils.stdout_guard import debug_print

class StructuralMemory(SemanticSearchBase):
    """
    プロジェクトの構造情報（クラス・メソッドの役割）を保持し、
    セマンティック検索を可能にするクラス。
    """
    
    def __init__(self, storage_dir: str, config_manager=None, vector_engine=None, morph_analyzer=None, index_on_init: bool = True):
        root = config_manager.workspace_root if config_manager else os.getcwd()
        super().__init__("structural_memory", storage_dir, vector_engine, morph_analyzer, workspace_root=root)
        self.workspace_root = root
        self.ast_analyzer = ASTAnalyzer()
        self.load()
        if index_on_init:
            # 25.3: Ensure we have the latest project structure indexed
            self.index_project()

    @property
    def components(self):
        return self.items

    def save_memory(self):
        self.is_dirty = True
        self.save()

    def index_project(self):
        """プロジェクト内のソースコードをスキャンしてインデックスを作成"""
        self.logger.info("Starting project-wide structural indexing...")

        def _normalize_id(value, fallback: str) -> str:
            if isinstance(value, str) and value:
                return value
            if value is None:
                return fallback
            if isinstance(value, (dict, list)):
                try:
                    return json.dumps(value, ensure_ascii=False, sort_keys=True)
                except Exception:
                    return fallback
            try:
                return str(value)
            except Exception:
                return fallback
        
        workspace_path = Path(self.workspace_root)
        src_dir = workspace_path / 'src'
        if not src_dir.exists():
            # Avoid noisy warnings for non-project or temp workspaces.
            config_marker = workspace_path / "config" / "config.json"
            if config_marker.exists():
                self.logger.warning(f"Source directory {src_dir} not found.")
            else:
                self.logger.info(f"Source directory {src_dir} not found (skipped indexing).")
            return

        # 既存のインデックスを完全にクリアしてから再構築する (Zombieデータ根絶)
        self.items = []
        self.id_to_index = {}
        if self.collection:
            self.collection.items = []
            self.collection.vectors = None
            self.collection.id_to_index = {}
            # Remove stale persisted files to avoid size mismatches
            if os.path.exists(self.collection.metadata_path):
                try:
                    os.remove(self.collection.metadata_path)
                except (FileNotFoundError, PermissionError):
                    pass
            if os.path.exists(self.collection.vector_path):
                try:
                    os.remove(self.collection.vector_path)
                except (FileNotFoundError, PermissionError):
                    pass
        
        batch_ids = []
        batch_vectors = []
        batch_items = []

        # 再帰的にファイルを探索
        for root, dirs, files in os.walk(src_dir):
            # 27.320: Exclude directories that cause logical pollution or noise
            dirs[:] = [d for d in dirs if d not in ["tests", "scenarios", "obj", "bin", ".git", ".venv"]]
            
            for file in files:
                if file.endswith(('.py', '.cs')):
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(workspace_path)
                    
                    try:
                        ext = os.path.splitext(file)[1].lower()
                        lang = 'python' if ext == '.py' else 'csharp'
                        
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        analysis_res = self.ast_analyzer.analyze_code_structure(content, language=lang)
                        if analysis_res.get('status') != 'success':
                            continue
                            
                        structure = analysis_res.get('structure', {})
                        
                        for cls in structure.get('classes', []):
                            if not isinstance(cls, dict): continue
                            cls_name = _normalize_id(cls.get('name', 'Unknown'), "Unknown")
                            summary = f"Class {cls_name} in {rel_path}. "
                            if cls.get('docstring'):
                                summary += f"Description: {cls['docstring']} "
                            
                            methods = cls.get('methods', [])
                            properties = cls.get('properties', [])
                            if methods:
                                method_names = []
                                for m in methods:
                                    if isinstance(m, dict):
                                        name_val = m.get("name")
                                    else:
                                        name_val = m
                                    name_val = _normalize_id(name_val, "UnknownMethod")
                                    method_names.append(name_val)
                                summary += f"Contains methods: {', '.join(method_names)}. "
                            if properties:
                                prop_names = []
                                for p in properties:
                                    if not isinstance(p, dict):
                                        continue
                                    p_name = p.get("name")
                                    if not isinstance(p_name, str) or not p_name:
                                        continue
                                    prop_names.append(p_name)
                                if prop_names:
                                    summary += f"Contains properties: {', '.join(prop_names)}. "
                            
                            vec = self.vectorize_text(summary)
                            if vec is None: vec = np.zeros(300)

                            class_symbol_id = f"{rel_path}::{cls_name}"
                            batch_ids.append(class_symbol_id)
                            batch_vectors.append(vec)
                            prop_map = {}
                            for p in properties:
                                if not isinstance(p, dict):
                                    continue
                                p_name = p.get("name")
                                if not isinstance(p_name, str) or not p_name:
                                    continue
                                prop_map[p_name] = p.get("type")
                            batch_items.append({
                                'id': class_symbol_id,
                                'symbol_id': class_symbol_id,
                                'type': 'class',
                                'name': cls_name,
                                'file': str(rel_path),
                                'summary': summary,
                                'properties': prop_map
                            })

                            # Index individual methods
                            for m in methods:
                                if not isinstance(m, dict): continue
                                m_name = _normalize_id(m.get('name'), "UnknownMethod")
                                full_m_name = f"{cls_name}.{m_name}"
                                m_summary = f"Method {m_name} of class {cls_name}. "
                                if m.get('docstring'): m_summary += f"Description: {m.get('docstring')}"
                                
                                m_vec = self.vectorize_text(m_summary)
                                if m_vec is None: m_vec = np.zeros(300)

                                method_symbol_id = f"{rel_path}::{full_m_name}"
                                batch_ids.append(method_symbol_id)
                                batch_vectors.append(m_vec)
                                batch_items.append({
                                    'id': method_symbol_id,
                                    'symbol_id': method_symbol_id,
                                    'type': 'method',
                                    'name': full_m_name,
                                    'short_name': m_name,
                                    'class': cls_name,
                                    'file': str(rel_path),
                                    'summary': m_summary,
                                    'role': m.get('role'),
                                    'capabilities': list(m.get('capabilities') or []),
                                    'return_type': (
                                        m.get('return_type')
                                        or m.get('returnType')
                                        or m.get('returns')
                                    ),
                                    'parameters': (
                                        m.get('parameters')
                                        or m.get('args')
                                        or []
                                    ),
                                    'start_line': (
                                        m.get('start_line')
                                        or m.get('startLine')
                                        or m.get('line')
                                    ),
                                    'end_line': (
                                        m.get('end_line')
                                        or m.get('endLine')
                                    ),
                                    'structural_fingerprint': m.get(
                                        'structural_fingerprint'
                                    ),
                                })
                        
                        for func in structure.get('functions', []):
                            if not isinstance(func, dict): continue
                            func_name = _normalize_id(func.get('name', 'Unknown'), "Unknown")
                            summary = f"Function {func_name} in {rel_path}. "
                            if func.get('docstring'):
                                summary += f"Description: {func['docstring']}"
                            
                            vec = self.vectorize_text(summary)
                            if vec is None: vec = np.zeros(300)
                            
                            function_symbol_id = f"{rel_path}::{func_name}"
                            batch_ids.append(function_symbol_id)
                            batch_vectors.append(vec)
                            batch_items.append({
                                'id': function_symbol_id,
                                'symbol_id': function_symbol_id,
                                'type': 'function',
                                'name': func_name,
                                'file': str(rel_path),
                                'summary': summary,
                                'role': func.get('role'),
                                'capabilities': list(func.get('capabilities') or []),
                                'return_type': (
                                    func.get('return_type')
                                    or func.get('returnType')
                                    or func.get('returns')
                                ),
                                'parameters': (
                                    func.get('parameters')
                                    or func.get('args')
                                    or []
                                ),
                                'start_line': (
                                    func.get('start_line')
                                    or func.get('startLine')
                                    or func.get('line')
                                ),
                                'end_line': (
                                    func.get('end_line')
                                    or func.get('endLine')
                                ),
                                'structural_fingerprint': func.get(
                                    'structural_fingerprint'
                                ),
                            })
                                
                    except Exception as e:
                        self.logger.warning(f"Failed to index {file_path}: {e}")

        if batch_ids:
            self.collection.upsert(batch_ids, batch_vectors, batch_items)
            self.items = self.collection.items
            self.save_memory()
        
        self.logger.info(f"Indexed {len(self.items)} components.")

    def search_component(
        self,
        query: str,
        top_k: int = 3,
        semantic_weight: float = 0.8,
        *,
        component_type: Optional[str] = None,
        role: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        symbol_id: Optional[str] = None,
        return_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """明示された構造条件で候補を絞り、利用可能なら意味距離で並べる。"""
        del semantic_weight  # 後方互換引数。固定重み合成は行わない。
        constraints = {
            'component_type': component_type,
            'role': role,
            'capabilities': capabilities,
            'symbol_id': symbol_id,
            'return_type': return_type,
        }
        has_constraints = any(value is not None for value in constraints.values())
        matching_items = [
            item for item in self.items
            if self._matches_constraints(item, **constraints)
        ]

        if symbol_id is not None or not self.vector_engine:
            if not has_constraints:
                return []
            return [
                {**item, 'similarity': None}
                for item in sorted(
                    matching_items,
                    key=lambda candidate: candidate.get('symbol_id', ''),
                )[:top_k]
            ]

        results_with_scores = self.hybrid_search(
            query,
            top_k=max(len(self.items), top_k),
        )
        allowed_ids = {item.get('symbol_id') for item in matching_items}
        final_results = []
        for item, score in results_with_scores:
            if item.get('symbol_id') not in allowed_ids:
                continue
            comp = item.copy()
            comp['similarity'] = score
            final_results.append(comp)
            if len(final_results) == top_k:
                break
        return final_results[:top_k]

    @staticmethod
    def _role_matches(actual_role: Optional[str], requested_role: Optional[str]) -> bool:
        if requested_role is None:
            return True
        if actual_role == requested_role:
            return True
        compatible_roles = {
            'FETCH': {'READ'},
            'READ': {'FETCH'},
            'PERSIST': {'WRITE'},
            'WRITE': {'PERSIST'},
        }
        return actual_role in compatible_roles.get(requested_role, set())

    @staticmethod
    def _matches_constraints(
        item: Dict[str, Any],
        *,
        component_type: Optional[str],
        role: Optional[str],
        capabilities: Optional[List[str]],
        symbol_id: Optional[str],
        return_type: Optional[str],
    ) -> bool:
        if component_type is not None and item.get('type') != component_type:
            return False
        if not StructuralMemory._role_matches(item.get('role'), role):
            return False
        if symbol_id is not None and item.get('symbol_id') != symbol_id:
            return False
        if return_type is not None and item.get('return_type') != return_type:
            return False
        required_capabilities = set(capabilities or [])
        actual_capabilities = set(item.get('capabilities') or [])
        return required_capabilities.issubset(actual_capabilities)

    def find_duplicates(
        self,
        structural_fingerprint: str,
        threshold: float = 0.85,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """解析器が生成した同一fingerprintを持つコンポーネントだけを返す。"""
        del threshold  # 後方互換引数。類似度閾値は使用しない。
        if not structural_fingerprint:
            return []
        duplicates = [
            item.copy()
            for item in self.items
            if item.get('structural_fingerprint') == structural_fingerprint
        ][:top_k]
        debug_print(
            f"[DEBUG] Found {len(duplicates)} components with exact structural fingerprint."
        )
        return duplicates

    def get_class_properties(self, class_name: str) -> Optional[Dict[str, str]]:
        """指定されたクラス名のプロパティ定義を返す。プロジェクト内の既存定義を優先する。"""
        # Exact match first
        for item in self.items:
            if item.get("type") == "class" and item.get("name") == class_name:
                return item.get("properties")
        
        return None

    def get_method_code(self, item: Dict[str, Any]) -> Optional[str]:
        """指定されたアイテム（メソッド）の実際のソースコードを取得する"""
        file_rel_path = item.get("file")
        if not file_rel_path: return None
        
        abs_path = os.path.join(self.workspace_root, file_rel_path)
        if not os.path.exists(abs_path): return None
        
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            start_line = item.get('start_line')
            end_line = item.get('end_line')
            if not isinstance(start_line, int) or not isinstance(end_line, int):
                return None
            if start_line < 1 or end_line < start_line:
                return None
            lines = content.splitlines()
            if end_line > len(lines):
                return None
            return "\n".join(lines[start_line - 1:end_line])
            
        except Exception as e:
            self.logger.error(f"Failed to get code for {item.get('name')}: {e}")
        
        return None
