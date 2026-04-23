# -*- coding: utf-8 -*-
import os
import unittest
from src.config.config_manager import ConfigManager


class TestVectorCacheRequired(unittest.TestCase):
    def test_chive_cache_exists(self):
        config = ConfigManager()
        model_path = config.vector_model_path
        max_vocab = 0
        vocab_cache = f"{model_path}.v{max_vocab}.vocab.npy"
        matrix_cache = f"{model_path}.v{max_vocab}.matrix.npy"

        missing = [p for p in [vocab_cache, matrix_cache] if not os.path.exists(p)]
        if missing:
            self.fail(f"chiVe cache missing: {', '.join(missing)}")


if __name__ == "__main__":
    unittest.main()
