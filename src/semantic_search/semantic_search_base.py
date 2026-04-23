# -*- coding: utf-8 -*-
import os
import json
import numpy as np
import logging
from typing import List, Dict, Any, Optional, Tuple

class SemanticSearchBase:
    """セマンティック検索エンジンの基底クラス"""

    def __init__(self, name: str, storage_dir: str, vector_engine=None, morph_analyzer=None, **kwargs):
        self.name = name
        self.storage_dir = storage_dir
        self.vector_engine = vector_engine
        self.morph_analyzer = morph_analyzer
        self.logger = logging.getLogger(f"SemanticSearch.{name}")
        
        from src.semantic_search.light_vector_db import LightVectorDB
        self.db = LightVectorDB(storage_dir)
        self.collection = self.db.get_collection(name)
        self.items = []
        
        # metadata_path の解決順序:
        # 1. kwargs["metadata_path"]
        # 2. kwargs["config"].{name}_path
        # 3. kwargs["config"].method_store_path (if name is method_store)
        # 4. デフォルト (resources/{name}.json)
        
        config = kwargs.get("config") or kwargs.get("config_manager")
        
        if "metadata_path" in kwargs and kwargs["metadata_path"]:
            self.metadata_path = kwargs["metadata_path"]
        elif config and hasattr(config, f"{name}_path"):
            self.metadata_path = getattr(config, f"{name}_path")
        elif config and hasattr(config, "method_store_path") and name == "method_store":
            self.metadata_path = config.method_store_path
        else:
            self.metadata_path = os.path.join(os.getcwd(), "resources", f"{name}.json")
            
        self.old_vector_path = os.path.join(storage_dir, f"{name}_vectors.pkl")

    def load(self):
        """メタデータとベクトルをロードする"""
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)
        
        # DBファイルのパス
        db_meta_path = os.path.join(self.storage_dir, f"{self.name}_meta.json")
        
        # 1. JSONマスタの更新確認
        should_sync = False
        if os.path.exists(self.metadata_path):
            json_mtime = os.path.getmtime(self.metadata_path)
            db_mtime = 0
            if os.path.exists(db_meta_path):
                db_mtime = os.path.getmtime(db_meta_path)
            
            # JSONの方が新しい、またはDBがない場合は同期フラグをON
            if json_mtime > db_mtime:
                self.logger.info(f"Metadata JSON is newer than DB. Syncing {self.name}...")
                should_sync = True

        # 2. データのロード
        if self.collection.items and not should_sync:
            self.items = self.collection.items
            self.logger.info(f"Loaded {len(self.items)} items from LightVectorDB collection '{self.name}'.")
            return

        # 3. 同期または初期移行
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    new_items = []
                    if isinstance(data, dict):
                        potential_keys = ['methods', 'patterns', 'components', 'items']
                        name_key = self.name.replace("_store", "s") if "_store" in self.name else self.name + "s"
                        potential_keys.insert(0, name_key)
                        for key in potential_keys:
                            if key in data:
                                new_items = data[key]
                                break
                    else:
                        new_items = data
                
                if new_items:
                    self.logger.info(f"Syncing {len(new_items)} items from JSON to LightVectorDB.")
                    
                    ids, vectors, metadatas = [], [], []
                    for item in new_items:
                        item_id = str(item.get("id", item.get("name")))
                        text = item.get("name", "") + " " + " ".join(item.get("tags", []))
                        if "description" in item: text += " " + item["description"]
                        
                        vec = None
                        if self.vector_engine:
                            raw_tokens = self.morph_analyzer.tokenize(text) if self.morph_analyzer else list(text)
                            tokens = [t["surface"] if isinstance(t, dict) else str(t) for t in raw_tokens]
                            vec = self.vector_engine.get_sentence_vector(tokens)
                        
                        if vec is None:
                            # フォールバック: ベクトルエンジンがない場合や失敗した場合はゼロベクトルを使用
                            vec = np.zeros(300)
                            
                        ids.append(item_id)
                        vectors.append(vec)
                        metadatas.append(item)
                    
                    if ids:
                        self.collection.upsert(ids, vectors, metadatas)
                    
                    self.items = self.collection.items
                    self.logger.info(f"Sync complete. {len(self.items)} items indexed.")
            except Exception as e:
                self.logger.error(f"Failed to sync {self.name}: {e}")

    def vectorize_text(self, text: str) -> Optional[np.ndarray]:
        """文字列をベクトル化するヘルパーメソッド"""
        if not self.vector_engine:
            return None
        if self.morph_analyzer:
            raw_tokens = self.morph_analyzer.tokenize(text)
            tokens = [t["surface"] if isinstance(t, dict) else str(t) for t in raw_tokens]
        else:
            tokens = list(text)
        return self.vector_engine.get_sentence_vector(tokens)

    def add_item(self, item: Dict[str, Any], vector: np.ndarray):
        """アイテムをインデックスに追加（メモリ上の items も更新）"""
        item_id = str(item.get("id", item.get("name")))
        self.collection.upsert([item_id], [vector], [item])
        # メモリ上の items を同期
        self.items = self.collection.items

    def save(self):
        """コレクションの状態を永続化する（LightVectorCollection は upsert 時に自動保存するが、明示的な呼び出し用）"""
        self.collection._save()

    def hybrid_search(self, query: str, top_k: int = 5, keyword_fn=None, semantic_weight: float = 0.7) -> List[Tuple[Dict[str, Any], float]]:
        """ベクトル検索のみを行う（キーワードマッチは行わない）"""
        if not self.items:
            self.load()
        if not self.vector_engine:
            if os.environ.get("SUPPRESS_VECTOR_WARNINGS") != "1":
                self.logger.warning("Vector engine is not available; returning empty semantic search results.")
            return []

        raw_tokens = self.morph_analyzer.tokenize(query) if self.morph_analyzer else list(query)
        tokens = [t["surface"] if isinstance(t, dict) else str(t) for t in raw_tokens]
        query_vec = self.vector_engine.get_sentence_vector(tokens)
        if query_vec is None:
            return []

        results = self.collection.query(query_vec, top_k=top_k)
        return [(res["item"], res["score"]) for res in results]

    def get_semantic_distance(self, str1: str, str2: str) -> float:
        """
        2つの文字列間の意味的な距離（正規化された非類似度）を計算する。
        0.0 (同一) ～ 1.0 (完全に無関係) の範囲。
        """
        if not self.vector_engine: return 1.0
        vec1 = self.vector_engine.get_sentence_vector(list(str1))
        vec2 = self.vector_engine.get_sentence_vector(list(str2))
        
        if vec1 is None or vec2 is None: return 1.0
        sim = self.vector_engine.vector_similarity(vec1, vec2)
        return 1.0 - sim
