# -*- coding: utf-8 -*-
import os
import sys
import numpy as np
import logging
from typing import List, Dict, Any, Optional
from src.semantic_search.light_vector_db import PretrainedVectorStore
import hashlib

class VectorEngine:
    """
    Embedding Generator for the pipeline.
    Uses PretrainedVectorStore for optimized mmap access to word vectors.
    """
    def __init__(self, model_path: str = None, max_vocab: int = 0):
        self.is_ready = False
        self.model_path = model_path
        self.store: Optional[PretrainedVectorStore] = None
        self._oov_cache: Dict[str, np.ndarray] = {}
        
        if os.environ.get("SKIP_VECTOR_MODEL") == "1":
            print("VectorEngine: Fast mode enabled (skipping model load).")
            self.is_ready = True
            return

        if not model_path:
             defaults = [
                 os.path.join(os.getcwd(), 'resources', 'vectors', 'chive-1.3-mc90.txt'),
                 os.path.join(os.getcwd(), 'resources', 'vectors', 'vectors.txt')
             ]
             for p in defaults:
                 if os.path.exists(p):
                     model_path = p
                     break
        
        if model_path and os.path.exists(model_path):
            self.load_with_cache(model_path, max_vocab=max_vocab)
        else:
            print(f"VectorEngine initialized but no model found at '{model_path}'.")

    def load_with_cache(self, path: str, max_vocab: int = 0):
        """Loads vectors using PretrainedVectorStore if cache available."""
        vocab_cache_path = path + f".v{max_vocab}.vocab.npy"
        matrix_cache_path = path + f".v{max_vocab}.matrix.npy"
        
        if os.path.exists(vocab_cache_path) and os.path.exists(matrix_cache_path):
            test_mode = bool(os.environ.get("PYTEST_CURRENT_TEST") or "unittest" in sys.modules)
            disable_mmap = os.environ.get("DISABLE_VECTOR_MMAP") == "1"
            use_mmap = not (test_mode or disable_mmap)
            self.store = PretrainedVectorStore(vocab_cache_path, matrix_cache_path, use_mmap=use_mmap)
            if self.store.matrix is not None:
                self.is_ready = True
                return

        allow_text_parse = os.environ.get("ALLOW_VECTOR_TEXT_PARSE") == "1"
        if not allow_text_parse:
            try:
                size_bytes = os.path.getsize(path)
                # Small test vectors can be parsed safely without explicit opt-in
                allow_text_parse = size_bytes <= 5 * 1024 * 1024
            except Exception:
                allow_text_parse = False
        if allow_text_parse:
            self.load_model_text(path, max_vocab)
            if self.is_ready:
                model_path_prefix = path + f".v{max_vocab}"
                self._save_cache(model_path_prefix)
                test_mode = bool(os.environ.get("PYTEST_CURRENT_TEST") or "unittest" in sys.modules)
                disable_mmap = os.environ.get("DISABLE_VECTOR_MMAP") == "1"
                use_mmap = not (test_mode or disable_mmap)
                # Re-load as store for fast access
                self.store = PretrainedVectorStore(
                    model_path_prefix + ".vocab.npy",
                    model_path_prefix + ".matrix.npy",
                    use_mmap=use_mmap
                )
            return

        print(f"Vector cache missing. Run scripts/data/convert_vectors.py for: {path}")

    def load_model_text(self, path: str, max_vocab: int):
        """Parsing text file and preparing for cache."""
        print(f"Parsing text file {path} for caching...")
        try:
            vocab = []
            vec_list = []
            count = 0
            with open(path, 'r', encoding='utf-8') as f:
                header = f.readline().strip().split()
                if len(header) != 2: f.seek(0)
                for line in f:
                    if count >= max_vocab: break
                    parts = line.strip().split()
                    if len(parts) < 2: continue
                    word = parts[0]
                    try:
                        vec = np.array([float(x) for x in parts[1:]], dtype=np.float32)
                        norm = np.linalg.norm(vec)
                        if norm > 0: vec /= norm
                        vec_list.append(vec)
                        vocab.append(word)
                        count += 1
                    except ValueError: continue
            
            self.temp_vocab = vocab
            self.temp_matrix = np.array(vec_list, dtype=np.float32)
            self.is_ready = True
        except Exception as e:
            print(f"Text load error: {e}")

    def _save_cache(self, model_path_prefix: str):
        vocab_cache_path = model_path_prefix + ".vocab.npy"
        matrix_cache_path = model_path_prefix + ".matrix.npy"
        print(f"Saving binary cache to {vocab_cache_path}...")
        np.save(vocab_cache_path, np.array(self.temp_vocab, dtype=object))
        np.save(matrix_cache_path, self.temp_matrix)
        del self.temp_vocab
        del self.temp_matrix

    def calculate_similarity(self, word1: str, word2: str) -> float:
        """Returns the cosine similarity between two words."""
        if not self.is_ready or not self.store: return 0.0
        v1 = self.store.get_vector(word1)
        v2 = self.store.get_vector(word2)
        if v1 is not None and v2 is not None:
            return float(np.dot(v1, v2))
        return 0.0

    def find_closest(self, query: str, candidates: list) -> tuple:
        """Finds the most similar word from candidates."""
        if not self.is_ready or not self.store: return (None, 0.0)
        q_vec = self.store.get_vector(query)
        if q_vec is None: return (None, 0.0)
        
        results = []
        for c in candidates:
            c_vec = self.store.get_vector(c)
            if c_vec is not None:
                sim = float(np.dot(q_vec, c_vec))
                results.append((c, sim))

        if not results: return (None, 0.0)
        return max(results, key=lambda x: x[1])

    def get_sentence_vector(self, words: list) -> Optional[np.ndarray]:
        if not self.is_ready or not words or not self.store:
            return None
        
        vecs = []
        for w in words:
            v = self.store.get_vector(w)
            if v is None:
                v = self._get_oov_vector(w)
            if v is not None: vecs.append(v)
            
        if not vecs: return None
        mean_vec = np.mean(vecs, axis=0)
        norm = np.linalg.norm(mean_vec)
        if norm > 0: mean_vec /= norm
        return mean_vec

    def vector_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        if v1 is None or v2 is None: return 0.0
        return float(np.dot(v1, v2))

    def _get_oov_vector(self, word: str) -> Optional[np.ndarray]:
        if not word or not self.store or self.store.matrix is None:
            return None
        cached = self._oov_cache.get(word)
        if cached is not None:
            return cached
        dim = int(self.store.matrix.shape[1])
        if dim <= 0:
            return None
        w = str(word)
        tokens = []
        if len(w) >= 2:
            tokens.extend(w[i:i+2] for i in range(len(w) - 1))
        tokens.extend(list(w))
        if not tokens:
            return None
        vec = np.zeros(dim, dtype=np.float32)
        for tok in tokens:
            h = hashlib.sha256((tok + "|" + w).encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "little") % dim
            sign = 1.0 if (h[4] & 1) == 0 else -1.0
            vec[idx] += sign
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        self._oov_cache[word] = vec
        return vec
