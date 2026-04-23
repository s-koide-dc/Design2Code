# -*- coding: utf-8 -*-
import os
import json
import numpy as np
import logging
from typing import Dict, List, Any, Optional, Tuple

class LightVectorCollection:
    """
    単一のベクトルコレクション（テーブル相当）を管理するクラス。
    """
    def __init__(self, name: str, storage_dir: str):
        self.name = name
        self.storage_dir = storage_dir
        self.metadata_path = os.path.join(storage_dir, f"{name}_meta.json")
        self.vector_path = os.path.join(storage_dir, f"{name}_vectors.npy")
        
        self.items: List[Dict[str, Any]] = []
        self.vectors: Optional[np.ndarray] = None
        self.id_to_index: Dict[str, int] = {}
        self._load()

    def _load(self):
        """データのロード"""
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    self.items = json.load(f)
                    self.id_to_index = {item["id"]: i for i, item in enumerate(self.items)}
            except Exception as e:
                logging.error(f"Failed to load metadata for {self.name}: {e}")

        if os.path.exists(self.vector_path):
            try:
                # Windowsでの共有ロック競合を避けるため、mmapを使用せずにロード
                self.vectors = np.load(self.vector_path)
            except Exception as e:
                logging.error(f"Failed to load vectors for {self.name}: {e}")
        
        # 整合性チェック
        if self.vectors is not None and len(self.items) != len(self.vectors):
            logging.warning(f"Collection {self.name} size mismatch: metadata={len(self.items)}, vectors={len(self.vectors)}. Truncating to safe limit.")
            safe_len = min(len(self.items), len(self.vectors))
            self.items = self.items[:safe_len]
            self.vectors = self.vectors[:safe_len]
            # Rebuild index and persist to prevent repeated mismatch warnings
            self.id_to_index = {item["id"]: i for i, item in enumerate(self.items)}
            self._save()

    def upsert(self, ids: List[str], vectors: List[np.ndarray], metadatas: List[Dict[str, Any]]):
        """アイテムの追加または更新"""
        current_vectors = self.vectors
        if current_vectors is not None:
            current_vectors = np.copy(current_vectors)
        
        for i, idx in enumerate(ids):
            vec = vectors[i]
            meta = metadatas[i]
            meta["id"] = idx
            
            if idx in self.id_to_index:
                pos = self.id_to_index[idx]
                if pos < len(self.items):
                    self.items[pos] = meta
                
                if current_vectors is not None and pos < len(current_vectors):
                    current_vectors[pos] = vec
                else:
                    if current_vectors is None:
                        current_vectors = np.array([vec])
                    else:
                        current_vectors = np.vstack([current_vectors, vec])
                    self.id_to_index[idx] = len(current_vectors) - 1
            else:
                self.id_to_index[idx] = len(self.items)
                self.items.append(meta)
                if current_vectors is None:
                    current_vectors = np.array([vec])
                else:
                    current_vectors = np.vstack([current_vectors, vec])
        
        self.vectors = current_vectors
        self._save()

    def remove(self, ids: List[str]):
        """アイテムの削除"""
        if not ids:
            return
            
        target_indices = []
        for idx in ids:
            if idx in self.id_to_index:
                target_indices.append(self.id_to_index[idx])
        
        if not target_indices:
            return
            
        # 削除対象を除去した新しいリストを作成
        new_items = []
        new_vectors_list = []
        
        seen_indices = set(target_indices)
        for i, item in enumerate(self.items):
            if i not in seen_indices:
                new_items.append(item)
                if self.vectors is not None:
                    new_vectors_list.append(self.vectors[i])
        
        self.items = new_items
        if new_vectors_list:
            self.vectors = np.array(new_vectors_list)
        else:
            self.vectors = None
            
        # インデックスの再構築
        self.id_to_index = {item["id"]: i for i, item in enumerate(self.items)}
        self._save()

    def _save(self):
        """永続化"""
        os.makedirs(self.storage_dir, exist_ok=True)
        try:
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.items, f, ensure_ascii=False, indent=2)
            
            if self.vectors is not None:
                np.save(self.vector_path, self.vectors)
        except Exception as e:
            logging.error(f"Failed to save {self.name}: {e}")

    def query(self, query_vector: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        """類似度検索（コサイン類似度）"""
        if self.vectors is None or len(self.items) == 0:
            return []
        
        # 内積計算（正規化済み前提）
        scores = np.dot(self.vectors, query_vector)
        
        # スコアの高い順にインデックスを取得
        top_indices = np.argsort(scores)[::-1]
        
        results = []
        for idx in top_indices:
            if idx < len(self.items):
                results.append({
                    "item": self.items[idx],
                    "score": float(scores[idx])
                })
                if len(results) >= top_k:
                    break
        return results

class LightVectorDB:
    """
    複数のコレクションを統合管理する軽量ベクトルDB。
    """
    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        self.collections: Dict[str, LightVectorCollection] = {}
        os.makedirs(storage_dir, exist_ok=True)

    def get_collection(self, name: str) -> LightVectorCollection:
        if name not in self.collections:
            self.collections[name] = LightVectorCollection(name, self.storage_dir)
        return self.collections[name]

    def upsert(self, collection_name: str, ids: List[str], vectors: List[np.ndarray], metadatas: List[Dict[str, Any]]):
        col = self.get_collection(collection_name)
        col.upsert(ids, vectors, metadatas)

    def query(self, collection_name: str, query_vector: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        col = self.get_collection(collection_name)
        return col.query(query_vector, top_k)

class PretrainedVectorStore:
    """
    chiVe などの巨大な事前学習済み単語ベクトルを管理するための専用クラス。
    ReadOnly で mmap を活用し、単語からベクトルへの高速な引き当てを提供。
    """
    def __init__(self, vocab_path: str, matrix_path: str, use_mmap: bool = True):
        self.vocab_path = vocab_path
        self.matrix_path = matrix_path
        self.use_mmap = use_mmap
        self.vocab: List[str] = []
        self.word_to_index: Dict[str, int] = {}
        self.matrix: Optional[np.ndarray] = None
        self._load()

    def _load(self):
        if os.path.exists(self.vocab_path) and os.path.exists(self.matrix_path):
            try:
                # 語彙のロード
                vocab_arr = np.load(self.vocab_path, allow_pickle=True)
                self.vocab = vocab_arr.tolist()
                self.word_to_index = {word: i for i, word in enumerate(self.vocab)}
                # 行列のロード（Windowsのロック回避のため mmap を切り替え可能にする）
                if self.use_mmap:
                    self.matrix = np.load(self.matrix_path, mmap_mode='r')
                else:
                    self.matrix = np.load(self.matrix_path)
                mode_label = "mmap" if self.use_mmap else "mem"
                logging.info(f"PretrainedVectorStore: Loaded {len(self.vocab)} vectors ({mode_label}).")
            except Exception as e:
                logging.error(f"Failed to load pretrained vectors: {e}")

    def get_vector(self, word: str) -> Optional[np.ndarray]:
        idx = self.word_to_index.get(word)
        if idx is not None and self.matrix is not None:
            return self.matrix[idx]
        return None
