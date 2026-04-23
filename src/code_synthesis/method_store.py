import os
import json
import shutil
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from src.symbol_matching.symbol_matcher import SymbolMatcher
from src.semantic_search.semantic_search_base import SemanticSearchBase

class MethodStore(SemanticSearchBase):
    """
    メソッド部品のメタデータを管理し、指示文に基づいた意味検索を行うクラス。
    HybridSearch (Vector + Keyword) と定義済みの Scoring Rules を統合する。
    """
    def __init__(self, config, morph_analyzer=None, vector_engine=None):
        self._migrate_legacy_vector_store_files(config)
        if vector_engine is None:
            try:
                from src.vector_engine.vector_engine import VectorEngine
                model_path = getattr(config, "vector_model_path", None)
                if isinstance(model_path, str) and os.path.exists(model_path):
                    vector_engine = VectorEngine(model_path=model_path)
                else:
                    vector_engine = None
            except Exception:
                vector_engine = None
        if vector_engine is not None and hasattr(vector_engine, "is_ready") and not getattr(vector_engine, "is_ready", False):
            vector_engine = None
        super().__init__("method_store", config.storage_dir, vector_engine=vector_engine, morph_analyzer=morph_analyzer, config=config)
        self.config_manager = config
        self.matcher = SymbolMatcher(config_manager=config, morph_analyzer=morph_analyzer, vector_engine=vector_engine)
        
        root = getattr(config, 'workspace_root', getattr(config, 'root_dir', os.getcwd()))
        
        # Load Scoring Rules
        self.scoring_rules = {}
        rules_path = os.path.join(root, "config", "scoring_rules.json")
        if os.path.exists(rules_path):
            with open(rules_path, 'r', encoding='utf-8') as f:
                self.scoring_rules = json.load(f)
        
        self.metadata_by_id = {}
        self.load()

    def _migrate_legacy_vector_store_files(self, config):
        """旧配置の method_store ベクトルDBファイルを storage_dir へ統一する。"""
        workspace_root = getattr(config, "workspace_root", None)
        # テスト用の簡易Config等で workspace_root がない場合は移行しない。
        if not workspace_root:
            return

        target_dir = str(getattr(config, "storage_dir", "") or "")
        if not target_dir:
            return
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception:
            return

        root = str(workspace_root)
        legacy_dirs = [
            root,
            os.path.join(root, "resources"),
            os.path.join(root, "cache"),
        ]
        target_meta = os.path.join(target_dir, "method_store_meta.json")
        target_vec = os.path.join(target_dir, "method_store_vectors.npy")

        for legacy_dir in legacy_dirs:
            legacy_meta = os.path.join(legacy_dir, "method_store_meta.json")
            legacy_vec = os.path.join(legacy_dir, "method_store_vectors.npy")
            try:
                if os.path.exists(legacy_meta):
                    if not os.path.exists(target_meta):
                        shutil.move(legacy_meta, target_meta)
                    else:
                        if os.path.getmtime(legacy_meta) > os.path.getmtime(target_meta):
                            shutil.copy2(legacy_meta, target_meta)
                        os.remove(legacy_meta)
                if os.path.exists(legacy_vec):
                    if not os.path.exists(target_vec):
                        shutil.move(legacy_vec, target_vec)
                    else:
                        if os.path.getmtime(legacy_vec) > os.path.getmtime(target_vec):
                            shutil.copy2(legacy_vec, target_vec)
                        os.remove(legacy_vec)
            except Exception:
                # 移行失敗は初期化を止めない
                pass

    @property
    def methods(self) -> Dict[str, Any]:
        """Backward compatibility property for metadata_by_id."""
        return self.metadata_by_id

    @methods.setter
    def methods(self, value):
        """Backward compatibility setter to support legacy tests."""
        if isinstance(value, dict):
            self.metadata_by_id = value
            self.items = list(value.values())
        elif isinstance(value, list):
            self.items = value
            self.metadata_by_id = {str(item.get("id", item.get("name"))): item for item in value if isinstance(item, dict)}
        else:
            self.items = []
            self.metadata_by_id = {}
        if hasattr(self, "collection") and hasattr(self.collection, "items"):
            self.collection.items = list(self.items)

    def load(self):
        """メタデータをロードし、正当なシンボルのみをインデックスする"""
        super().load()
        # SemanticSearchBase.load() によって self.items に読み込まれたデータを検証
        valid_items = []
        for item in self.items:
            m_name = item.get("name", "")
            m_class = item.get("class", "")
            
            # 内部シンボル、ジェネリックメタ表記、特殊なアクセサを排除 (Synthesizable Member Policy)
            if '`' in m_name or '`' in m_class or '$' in m_name:
                continue
            if m_name.startswith('get_') or m_name.startswith('set_'):
                continue
            
            valid_items.append(item)
            
        self.items = valid_items
        self.metadata_by_id = {str(item.get("id", item.get("name"))): item for item in self.items}

    def add_method(self, method_data: Dict[str, Any], overwrite: bool = True):
        """新しいメソッドをストアに追加する (ベクトル化込み)"""
        m_id = str(method_data.get("id", method_data.get("name")))
        
        if m_id in self.metadata_by_id:
            if not overwrite: return
            # 既存メタデータの継承 (Tier等の手動設定を保護)
            existing = self.metadata_by_id[m_id]
            for field in ["tier", "capability", "role", "intent"]:
                if field in existing and field not in method_data:
                    method_data[field] = existing[field]
        
        # ベクトル化用のテキスト
        text = method_data.get("name", "") + " " + " ".join(method_data.get("tags", []))
        if "summary" in method_data:
            text += " " + method_data["summary"]
        if "class" in method_data:
            text += " " + method_data["class"]
            
        vec = self.vectorize_text(text)
        if vec is None:
            vec = np.zeros(300) # Fallback
            
        self.add_item(method_data, vec)
        self.metadata_by_id[m_id] = method_data

    def save(self):
        """現在の状態をベクトルDBとソースJSONの両方に保存する"""
        # 1. ベクトルDB (cache/) の保存
        super().save()
        
        # 2. ソースJSON (resources/method_store.json) の保存
        try:
            # 常に最新の self.items を書き出す
            output_data = {"methods": self.items}
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved {len(self.items)} methods to {self.metadata_path}")
        except Exception as e:
            self.logger.error(f"Failed to save method_store.json: {e}")

    def get_method_by_id(self, m_id: str) -> Optional[Dict[str, Any]]:
        return self.metadata_by_id.get(str(m_id))

    def search(self, query: str, limit: int = 5, intent: str = None, role: str = None, cardinality: str = None, input_type: str = None, target_entity: str = None) -> List[Dict[str, Any]]:
        """
        メソッド部品を検索する。
        基本検索のみを行い、詳細なランク付けは UnifiedKnowledgeBase に委ねる。
        """
        if not query: return []
        # Vector engine unavailable: fall back to deterministic, metadata-only selection.
        if not self.vector_engine:
            if not self.items:
                self.load()
            candidates = list(self.items)
            filtered = []
            for item in candidates:
                item_copy = item.copy()
                # If intent is provided but metadata lacks intent/role/capabilities, tag with intent to allow ranking.
                if intent and not item_copy.get("intent") and not item_copy.get("role") and not item_copy.get("capabilities"):
                    item_copy["intent"] = intent
                    item_copy["capabilities"] = [intent]

                # Optional intent-based filtering when explicit metadata exists.
                if intent:
                    item_intent = item_copy.get("intent")
                    item_caps = item_copy.get("capabilities", [])
                    if item_intent or item_caps:
                        if item_intent != intent and intent not in item_caps:
                            continue

                # Anti-pattern exclusion
                name_low = item_copy.get("name", "").lower()
                if name_low in ["gettype", "gethashcode", "tostring", "equals"]:
                    continue

                item_copy["score"] = 0.0
                filtered.append(item_copy)

            def _priority(item: Dict[str, Any]) -> int:
                tags = item.get("tags") or []
                if not isinstance(tags, list):
                    return 0
                return 1 if any(t in ["project_internal", "reuse"] for t in tags) else 0

            filtered.sort(key=lambda x: (-_priority(x), str(x.get("name", "")), str(x.get("id", ""))))
            return filtered[:limit]
        # 1. 候補の絞り込み (意図による事前フィルタリング)
        # 実行速度向上のため、明らかに不適合なものを除外するヒントとして活用
        candidates_to_rank = []
        
        # 2. 基本検索
        raw_results = self.hybrid_search(query, top_k=limit * 20, semantic_weight=1.0)
        
        ranked_results = []
        for item, score in raw_results:
            item_id = item.get("id")
            meta = self.metadata_by_id.get(item_id, item)
            
            # アンチパターン排除
            name_low = item.get("name", "").lower()
            if name_low in ["gettype", "gethashcode", "tostring", "equals"]:
                continue

            # 基本的な類似度と情報を保持して UnifiedKnowledgeBase へ渡す
            item_copy = item.copy()
            for field in ["tier", "capability", "capabilities", "role", "intent", "params", "return_type"]:
                if field in meta:
                    item_copy[field] = meta[field]
            
            name_sim = 0.0
            try:
                name_sim = float(self.matcher.calculate_semantic_similarity(query, item.get("name", "")))
            except Exception:
                name_sim = 0.0
            item_copy["score"] = score
            item_copy["name_similarity"] = name_sim
            ranked_results.append(item_copy)

        ranked_results.sort(key=lambda x: (x.get("name_similarity", 0.0), x.get("score", 0.0)), reverse=True)
        return ranked_results[:limit]

