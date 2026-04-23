# LightVectorDB Design Document

## 1. Purpose

`LightVectorDB` は軽量なベクトル保存と類似度検索を提供する。  
コレクション単位でメタデータとベクトルを永続化し、コサイン類似度で検索する。

## 2. Structured Specification

### Input
- **Description**: ベクトル、メタデータ、クエリベクトル。
- **Type/Format**: `List[np.ndarray]`, `List[Dict[str, Any]]`

### Output
- **Description**: 類似度順の検索結果。
- **Type/Format**: `List[Dict[str, Any]]`

### Core Logic
1. `LightVectorCollection` はメタデータ JSON と `.npy` ベクトルをロードする（Windows のロック回避のため mmap を使わずにロード）。
2. メタデータとベクトルの件数が不一致な場合は安全な件数に切り詰め、再保存する。
3. `upsert` で ID をキーにメタデータとベクトルを更新・追加する。
4. `query` は内積を計算し、上位 `top_k` 件を返す（正規化済みベクトル前提）。
5. `remove` で指定 ID を削除し、インデックスを再構築する。
6. `PretrainedVectorStore` は語彙と行列を mmap または通常ロードで読み込み、単語ベクトルを返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: `upsert` 後に `query` が結果を返す。
  - **Expected Output**: 結果件数が `top_k` 以下。
- **Edge Cases**:
  - **Scenario**: メタデータとベクトルの件数が一致しない。
  - **Expected Output / Behavior**: 安全な件数に切り詰めて保存する。

## 3. Dependencies
- **External**: `numpy`, `json`, `os`, `logging`
