# SemanticSearchBase Design Document

## 1. Purpose

`SemanticSearchBase` はメタデータ JSON を LightVectorDB に同期し、ベクトル検索を行う基底クラスである。

## 2. Structured Specification

### Input
- **Description**: メタデータパス、クエリ文字列。
- **Type/Format**: `str`

### Output
- **Description**: 類似度結果の一覧。
- **Type/Format**: `List[Tuple[Dict[str, Any], float]]`

### Core Logic
1. `metadata_path` を `kwargs` / `config` / 既定値の順で解決する（`method_store` は専用パスも考慮）。
2. `load` で JSON の更新時刻と DB を比較し、必要なら同期する。
3. 同期時は JSON のキー候補（`{name}s`, `methods`, `patterns`, `components`, `items`）から配列を解決し、各アイテムをベクトル化して upsert する。
4. ベクトル化に失敗した場合は 300 次元のゼロベクトルを使用する。
5. `hybrid_search` はクエリをベクトル化し、DB へ問い合わせる。

### Test Cases
- **Happy Path**:
  - **Scenario**: JSON が新しく、同期が実行される。
  - **Expected Output**: DB にアイテムが登録される。
- **Edge Cases**:
  - **Scenario**: `vector_engine` が無い。
  - **Expected Output / Behavior**: 空の結果を返す。
  - **Scenario**: `morph_analyzer` のトークンが dict 形式。
  - **Expected Output / Behavior**: `surface` を抽出してベクトル化する。

## 3. Dependencies
- **Internal**: `light_vector_db`
- **External**: `numpy`, `json`, `os`, `logging`
