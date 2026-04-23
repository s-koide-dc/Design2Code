# -*- coding: utf-8 -*-
import os
import json
import re
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from src.advanced_tdd.ast_analyzer import ASTAnalyzer
from src.semantic_search.semantic_search_base import SemanticSearchBase

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

                            batch_ids.append(cls_name)
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
                                
                                batch_ids.append(full_m_name)
                                batch_vectors.append(m_vec)
                                batch_items.append({
                                    'type': 'method',
                                    'name': full_m_name,
                                    'short_name': m_name,
                                    'class': cls_name,
                                    'file': str(rel_path),
                                    'summary': m_summary
                                })
                        
                        for func in structure.get('functions', []):
                            if not isinstance(func, dict): continue
                            func_name = _normalize_id(func.get('name', 'Unknown'), "Unknown")
                            summary = f"Function {func_name} in {rel_path}. "
                            if func.get('docstring'):
                                summary += f"Description: {func['docstring']}"
                            
                            vec = self.vectorize_text(summary)
                            if vec is None: vec = np.zeros(300)
                            
                            batch_ids.append(func_name)
                            batch_vectors.append(vec)
                            batch_items.append({
                                'type': 'function',
                                'name': func_name,
                                'file': str(rel_path),
                                'summary': summary
                            })
                                
                    except Exception as e:
                        self.logger.warning(f"Failed to index {file_path}: {e}")

        if batch_ids:
            self.collection.upsert(batch_ids, batch_vectors, batch_items)
            self.items = self.collection.items
            self.save_memory()
        
        self.logger.info(f"Indexed {len(self.items)} components.")

    def search_component(self, query: str, top_k: int = 3, semantic_weight: float = 0.8) -> List[Dict[str, Any]]:
        """意味的に関連するコンポーネントを検索 (Hybrid Search対応)"""
        
        # クラス名、関数名、およびサマリとのマッチングをキーワードスコアとする
        def kw_fn(item, query_keywords):
            score = 0.0
            name_lower = item.get('name', '').lower()
            summary_lower = item.get('summary', '').lower()
            
            for kw in query_keywords:
                kw_l = kw.lower()
                if kw_l in name_lower:
                    score += 0.5
                if kw_l in summary_lower:
                    score += 0.3 # サマリ一致は名前一致より低め
                    
            return min(1.0, score)

        results_with_scores = self.hybrid_search(query, top_k=max(top_k, 300), keyword_fn=kw_fn, semantic_weight=semantic_weight)
        
        final_results = []
        for item, score in results_with_scores:
            comp = item.copy()
            comp['similarity'] = score
            final_results.append(comp)
            
        return final_results[:top_k]

    def find_duplicates(self, summary_or_code: str, threshold: float = 0.85, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        指定されたサマリやコード片と意味的に重複する可能性が高いコンポーネントを検索する。
        """
        # ベクトルエンジンが準備完了ならセマンティック検索を優先
        has_engine = self.vector_engine is not None and getattr(self.vector_engine, 'is_ready', False)
        weight = 0.8 if has_engine else 0.0
        
        print(f"[DEBUG] find_duplicates called. Engine Ready: {has_engine}, Weight: {weight}, Items: {len(self.items)}")
        
        # ターゲットの個別スコア調査 (デバッグ)
        target_item = next((it for it in self.items if "InventoryUtils.CalculateAveragePrice" in it['name']), None)
        if target_item:
            q_keywords = []
            if self.morph_analyzer:
                res = self.morph_analyzer.analyze({"original_text": summary_or_code})
                q_keywords = [t["base"].lower() for t in res.get("analysis", {}).get("tokens", [])]
            
            # 手動でキーワードスコア計算
            name_lower = target_item.get('name', '').lower()
            summary_lower = target_item.get('summary', '').lower()
            k_score = 0.0
            for kw in q_keywords:
                if kw.lower() in name_lower: k_score += 0.5
                if kw.lower() in summary_lower: k_score += 0.3
            k_score = min(1.0, k_score)
            print(f"[DEBUG] Targeted Item 'InventoryUtils.CalculateAveragePrice' Keyword Score: {k_score}, Keywords: {q_keywords}")

        candidates = self.search_component(summary_or_code, top_k=top_k, semantic_weight=weight)
        
        # DEBUGログ: 全候補のスコアを出力
        for c in candidates:
            print(f"[DEBUG] Duplicate candidate: {c['name']}, Similarity: {c.get('similarity', 0.0):.4f}")

        duplicates = [c for c in candidates if c.get('similarity', 0.0) >= threshold]
        if duplicates:
            print(f"[DEBUG] Found {len(duplicates)} duplicates above threshold {threshold}")
        return duplicates

    def get_class_properties(self, class_name: str) -> Optional[Dict[str, str]]:
        """指定されたクラス名のプロパティ定義を返す。プロジェクト内の既存定義を優先する。"""
        # Exact match first
        for item in self.items:
            if item.get("type") == "class" and item.get("name") == class_name:
                return item.get("properties")
        
        # Semantic match second (if class_name is slightly different)
        candidates = self.search_component(f"Class {class_name}", top_k=1, semantic_weight=0.5)
        if candidates and candidates[0].get("similarity", 0) > 0.8:
            if candidates[0].get("type") == "class":
                return candidates[0].get("properties")
        
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
            
            # メソッド名 (ClassName.MethodName か単体名)
            full_name = item.get("name", "")
            method_name = item.get("short_name") or full_name.split('.')[-1]
            class_name = item.get("class") or (full_name.split('.')[0] if '.' in full_name else None)

            # ASTAnalyzer を使って抽出
            ext = os.path.splitext(abs_path)[1].lower()
            lang = 'python' if ext == '.py' else 'csharp'
            
            # 簡易的な正規表現抽出 (ASTより確実な場合がある)
            # public ... MethodName(...) { ... }
            if lang == 'csharp':
                # 非常に簡易的な実装。本来は AST で取るべき。
                pattern = fr"(public\s+[\s\w<>,\[\]]+\s+{re.escape(method_name)}\s*\(.*?\)\s*\{{(?:[^{{}}]*|\{{[^{{}}]*\}})*\}})"
                match = re.search(pattern, content, re.DOTALL)
                if match: return match.group(1)
            
            # フォールバック: ASTAnalyzer (実装されている場合)
            res = self.ast_analyzer.analyze_code_structure(content, language=lang)
            # ... (中略: ASTからコード片を特定して返す) ...
            
        except Exception as e:
            self.logger.error(f"Failed to get code for {item.get('name')}: {e}")
        
        return None
