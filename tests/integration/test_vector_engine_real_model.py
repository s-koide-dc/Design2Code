# -*- coding: utf-8 -*-
import os
import unittest
import numpy as np

from src.config.config_manager import ConfigManager
from src.vector_engine.vector_engine import VectorEngine


class TestVectorEngineRealModel(unittest.TestCase):
    def setUp(self):
        self._orig_skip = os.environ.pop("SKIP_VECTOR_MODEL", None)
        self._orig_disable_mmap = os.environ.pop("DISABLE_VECTOR_MMAP", None)

    def tearDown(self):
        if self._orig_skip is not None:
            os.environ["SKIP_VECTOR_MODEL"] = self._orig_skip
        if self._orig_disable_mmap is not None:
            os.environ["DISABLE_VECTOR_MMAP"] = self._orig_disable_mmap

    def test_vector_engine_loads_real_model(self):
        config = ConfigManager()
        model_path = config.vector_model_path
        max_vocab = 0
        vocab_cache = f"{model_path}.v{max_vocab}.vocab.npy"
        matrix_cache = f"{model_path}.v{max_vocab}.matrix.npy"

        self.assertTrue(os.path.exists(model_path), f"model missing: {model_path}")
        self.assertTrue(os.path.exists(vocab_cache), f"vocab cache missing: {vocab_cache}")
        self.assertTrue(os.path.exists(matrix_cache), f"matrix cache missing: {matrix_cache}")

        engine = VectorEngine(model_path=model_path, max_vocab=max_vocab)
        self.assertTrue(engine.is_ready, "VectorEngine should be ready with real model caches")
        self.assertIsNotNone(engine.store, "VectorEngine store should be initialized")
        self.assertIsNotNone(engine.store.matrix, "VectorEngine matrix should be loaded")
        self.assertGreater(engine.store.matrix.shape[0], 0)
        self.assertGreater(engine.store.matrix.shape[1], 0)

        vocab = np.load(vocab_cache, allow_pickle=True)
        self.assertGreater(len(vocab), 0, "vocab cache is empty")
        sample_word = str(vocab[0])
        vec = engine.store.get_vector(sample_word)
        self.assertIsNotNone(vec, f"vector missing for sample word: {sample_word}")
        self.assertEqual(vec.shape[0], engine.store.matrix.shape[1])


if __name__ == "__main__":
    unittest.main()
