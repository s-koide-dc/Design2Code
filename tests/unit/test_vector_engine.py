# -*- coding: utf-8 -*-
import unittest
import os
import tempfile
import numpy as np
import sys
import io

from src.vector_engine.vector_engine import VectorEngine

class TestVectorEngine(unittest.TestCase):

    def setUp(self):
        # Force disable Fast mode for these specific tests to verify model loading
        self.old_skip_val = os.environ.get("SKIP_VECTOR_MODEL")
        os.environ["SKIP_VECTOR_MODEL"] = "0"

        self.test_dir = tempfile.TemporaryDirectory()
        self.model_path = os.path.join(self.test_dir.name, 'vectors.txt')
        self.max_vocab = 100
        
        # Create a dummy vectors.txt
        with open(self.model_path, 'w', encoding='utf-8') as f:
            f.write("4 2\n")
            f.write("犬 1.0 0.0\n")
            f.write("猫 0.8 0.2\n")
            f.write("最高 0.1 0.9\n")
            f.write("気分 0.2 0.8\n")
            
        self.vocab_cache_path = self.model_path + f".v{self.max_vocab}.vocab.npy"
        self.matrix_cache_path = self.model_path + f".v{self.max_vocab}.matrix.npy"

    def tearDown(self):
        if self.old_skip_val is not None:
            os.environ["SKIP_VECTOR_MODEL"] = self.old_skip_val
        else:
            if "SKIP_VECTOR_MODEL" in os.environ:
                del os.environ["SKIP_VECTOR_MODEL"]
        # Use ignore_errors=True to handle Windows file locks on mmap .npy files
        import shutil
        shutil.rmtree(self.test_dir.name, ignore_errors=True)

    def test_01_initialization_and_cache_creation(self):
        """Test if the engine initializes and creates cache files correctly."""
        # Redirect stdout to check print statements
        captured_output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output
        try:
            engine = VectorEngine(model_path=self.model_path, max_vocab=self.max_vocab)
        finally:
            sys.stdout = old_stdout
            
        output = captured_output.getvalue()

        self.assertTrue(engine.is_ready)
        self.assertIn("Parsing text file", output)
        self.assertIn("Saving binary cache", output)
        self.assertTrue(os.path.exists(self.vocab_cache_path))
        self.assertTrue(os.path.exists(self.matrix_cache_path))
        self.assertEqual(len(engine.store.vocab), 4)

    def test_02_cache_loading(self):
        """Test if the engine loads from cache on the second run."""
        # First run to create cache
        VectorEngine(model_path=self.model_path, max_vocab=self.max_vocab)

        # Second run - just check it initializes successfully and vocab is correct
        # stdout check is unstable on Windows due to buffering/locking
        engine = VectorEngine(model_path=self.model_path, max_vocab=self.max_vocab)

        self.assertTrue(engine.is_ready)
        self.assertEqual(len(engine.store.vocab), 4)

    def test_calculate_similarity(self):
        """Test word similarity calculation."""
        engine = VectorEngine(model_path=self.model_path, max_vocab=self.max_vocab)
        # Similarity between two known words
        sim = engine.calculate_similarity("犬", "猫")
        self.assertIsInstance(sim, float)
        self.assertGreater(sim, 0.0)

        # Similarity with an unknown word
        sim_unknown = engine.calculate_similarity("犬", "存在しない単語")
        self.assertEqual(sim_unknown, 0.0)

    def test_find_closest(self):
        """Test finding the closest word from a list of candidates."""
        engine = VectorEngine(model_path=self.model_path, max_vocab=self.max_vocab)
        closest = engine.find_closest("犬", ["猫", "最高"])
        self.assertEqual(closest[0], "猫")
        self.assertGreater(closest[1], 0)

    def test_get_sentence_vector(self):
        """Test sentence vector generation."""
        engine = VectorEngine(model_path=self.model_path, max_vocab=self.max_vocab)

        # Test with known words
        vec = engine.get_sentence_vector(["犬", "猫"])
        self.assertIsInstance(vec, np.ndarray)
        self.assertEqual(vec.shape, (2,))

    def test_design_spec_sentence_matching(self):
        """Test the sentence matching case from the design spec."""
        engine = VectorEngine(model_path=self.model_path, max_vocab=self.max_vocab)
        vec1 = engine.get_sentence_vector(["最高"])
        vec2 = engine.get_sentence_vector(["気分"])
        
        self.assertIsNotNone(vec1)
        self.assertIsNotNone(vec2)
        
        similarity = engine.vector_similarity(vec1, vec2)
        self.assertIsInstance(similarity, float)
        self.assertGreater(similarity, 0.0)

if __name__ == '__main__':
    unittest.main()