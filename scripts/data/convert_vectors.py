import argparse
import os
import sys
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert vector text file to cached .npy files.")
    parser.add_argument(
        "--input",
        default=os.path.join(os.getcwd(), "resources", "vectors", "chive-1.3-mc90.txt"),
        help="Path to vector text file (e.g., chive-1.3-mc90.txt).",
    )
    parser.add_argument(
        "--max-vocab",
        type=int,
        default=0,
        help="Maximum number of vocab entries to load. 0 means no limit.",
    )
    return parser.parse_args()


def load_vectors_text(path: str, max_vocab: int) -> tuple[list[str], np.ndarray]:
    vocab: list[str] = []
    vec_list: list[np.ndarray] = []
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline().strip().split()
        if len(header) != 2:
            f.seek(0)
        for line in f:
            if max_vocab > 0 and count >= max_vocab:
                break
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            word = parts[0]
            try:
                vec = np.array([float(x) for x in parts[1:]], dtype=np.float32)
            except ValueError:
                continue
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            vocab.append(word)
            vec_list.append(vec)
            count += 1
    if not vec_list:
        return [], np.array([], dtype=np.float32)
    return vocab, np.array(vec_list, dtype=np.float32)


def save_cache(path: str, max_vocab: int, vocab: list[str], matrix: np.ndarray) -> None:
    prefix = path + f".v{max_vocab}"
    vocab_cache_path = prefix + ".vocab.npy"
    matrix_cache_path = prefix + ".matrix.npy"
    os.makedirs(os.path.dirname(vocab_cache_path), exist_ok=True)
    np.save(vocab_cache_path, np.array(vocab, dtype=object))
    np.save(matrix_cache_path, matrix)
    print(f"Saved vocab cache: {vocab_cache_path}")
    print(f"Saved matrix cache: {matrix_cache_path}")


def main() -> int:
    args = parse_args()
    if not os.path.exists(args.input):
        print(f"Error: input file not found: {args.input}")
        return 1
    print(f"Loading vectors from {args.input} (max_vocab={args.max_vocab})...")
    vocab, matrix = load_vectors_text(args.input, args.max_vocab)
    if len(vocab) == 0 or matrix.size == 0:
        print("Error: no vectors loaded.")
        return 1
    save_cache(args.input, args.max_vocab, vocab, matrix)
    print(f"Done. Loaded {len(vocab)} vectors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
