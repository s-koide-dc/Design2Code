# -*- coding: utf-8 -*-
from unittest.mock import patch
import numpy as np
import hashlib

def mock_vector_engine():
    """
    Globally mocks VectorEngine to prevent heavy model loading during unit tests.
    """
    class DummyVectorEngine:
        def __init__(self, *args, **kwargs):
            self.is_ready = True
            self._dim = 64

        def get_sentence_vector(self, words):
            if not words:
                return None
            vec = np.zeros(self._dim, dtype=np.float32)
            for w in words:
                token = str(w)
                h = hashlib.sha256(token.encode("utf-8")).digest()
                idx = int.from_bytes(h[:4], "little") % self._dim
                sign = 1.0 if (h[4] & 1) == 0 else -1.0
                vec[idx] += sign
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            return vec

        def vector_similarity(self, v1, v2):
            if v1 is None or v2 is None:
                return 0.0
            return float(np.dot(v1, v2))
    
    # Return a patcher that can be started/stopped
    return patch('src.vector_engine.vector_engine.VectorEngine', DummyVectorEngine)

def fast_test_setup():
    """
    Applies common mocks for fast unit testing.
    """
    # Disable background loading in pipeline_core for tests
    patch('src.pipeline_core.pipeline_core.Pipeline._start_vector_engine_loading', return_value=None).start()
