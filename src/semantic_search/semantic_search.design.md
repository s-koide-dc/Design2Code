# semantic_search Design Document

## 1. Purpose

`semantic_search` は LightVectorDB を使ったセマンティック検索を提供する。  
JSON で管理されるメタデータをベクトル化して格納し、類似度検索で候補を返す。

## 2. Structured Specification

### Input
- **Description**: メタデータ JSON と検索クエリ文字列。
- **Type/Format**: `Dict[str, Any]` / `str`

### Output
- **Description**: 類似度順のアイテムとスコア。
- **Type/Format**: `List[Tuple[Dict[str, Any], float]]`

### Core Logic
1. `SemanticSearchBase` が `LightVectorDB` を初期化し、コレクションを取得する。
2. JSON メタデータが更新されていれば DB へ同期し、アイテムをベクトル化して保存する。
3. `hybrid_search` はクエリをベクトル化し、コレクションの類似度検索結果を返す。
4. `vector_engine` が無い場合は空配列を返し、警告ログのみを出力する。

### Test Cases
- **Happy Path**:
  - **Scenario**: メタデータが存在し、検索が成功する。
  - **Expected Output**: `top_k` 件の結果が返る。
- **Edge Cases**:
  - **Scenario**: `vector_engine` が未設定。
  - **Expected Output / Behavior**: 空の結果を返す。

## 3. Dependencies
- **Internal**: `light_vector_db`
- **External**: `numpy`, `json`, `os`
