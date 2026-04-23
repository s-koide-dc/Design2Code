# vector_engine 設計ドキュメント

## 1. Purpose
`vector_engine`は、単語埋め込み（ベクトル）を使用して意味的類似性計算を提供します。堅牢な意図照合のために、単語レベルの計算と文レベルのベクトル集約（平均プーリング）の両方をサポートします。

## 2. 仕様 (Specification)

### 主なメソッドとI/O

#### `get_sentence_vector(words: list)`
- **Input**: 単語トークンのリスト (e.g., `["犬", "が", "歩く"]`)。
- **Output**: 文全体を代表する正規化された `np.ndarray`。語彙に単語が見つからない場合は `None`。

#### `calculate_similarity(word1: str, word2: str)`
- **Input**: 2つの単語文字列。
- **Output**: 2つの単語間のコサイン類似度スコア (`float`)。

#### `vector_similarity(v1: np.ndarray, v2: np.ndarray)`
- **Input**: 2つの事前に計算された正規化済みベクトル。
- **Output**: 2つのベクトル間のコサイン類似度スコア (`float`)。

#### `find_closest(query: str, candidates: list)`
- **Input**: クエリ単語 (`str`) と、候補単語のリスト (`list`)。
- **Output**: 最も類似度が高い候補単語とそのスコアのタプル (e.g., `("猫", 0.85)`)。

### Core Logic

このモジュールの主な特徴は、大規模な単語ベクトルモデルを効率的に処理するための**PretrainedVectorStore による構造分離**です。

1.  **初期化とモデル読み込み (`load_with_cache`)**:
    -   環境変数 `SKIP_VECTOR_MODEL=1` が設定されている場合、モデルロードをスキップする高速起動モードで動作し、`is_ready=True` を返す。
    -   `model_path` 未指定時は `resources/vectors/chive-1.3-mc90.txt` → `resources/vectors/vectors.txt` の順で既定パスを探索する。
    -   バイナリキャッシュ（`.v{max_vocab}.vocab.npy` / `.v{max_vocab}.matrix.npy`）があれば `PretrainedVectorStore` で読み込む。
    -   テストモードや `DISABLE_VECTOR_MMAP=1` の場合は mmap を無効化する。
    -   キャッシュがない場合は警告を出し、`scripts/data/convert_vectors.py` で事前変換を要求する。
    -   例外的に `ALLOW_VECTOR_TEXT_PARSE=1`、または 5MB 以下の小規模ベクトルの場合のみテキストをパースしてキャッシュを生成する。

2.  **文ベクトル計算 (`get_sentence_vector`)**:
    -   単語トークンのリストを受け取り、`PretrainedVectorStore` から各単語のベクトルを取得する。
    -   未知語はハッシュベースの OOV ベクトルを生成し、キャッシュする。
    -   **平均プーリング**（要素ごとの平均）を実行し、単位ベクトルに正規化して返却する。

3.  **類似度計算**:
    -   `calculate_similarity` / `find_closest`: `PretrainedVectorStore` からベクトルを取得し、内積（ドット積）による類似度計算を実行する。
    -   `vector_similarity` は正規化済みベクトルの内積を返す。

### Test Cases
- **文のマッチング**:
  - **Input**: `["最高", "だ"]`, `["気分", "が", "いい"]`
  - **Expected**: それらの文ベクトル間で高い類似度スコア（>0.7）。
- **語彙にない単語**:
  - **Input**: `["未知の単語"]`
  - **Expected**: `get_sentence_vector`が`None`を返す。

## 4. Consumers
- **pipeline_core**: エンジンの初期化とライフサイクル管理。
- **semantic_analyzer / intent_detector**: 意図の意味的照合。
- **method_store**: メソッドの意味的検索。

## 3. 依存関係 (Dependencies)
- **内部**: `src/semantic_search/light_vector_db.py` (PretrainedVectorStore)
- **External**: `numpy`, `hashlib`, `os`, `sys`
