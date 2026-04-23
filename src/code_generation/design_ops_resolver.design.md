# design_ops_resolver Design Document

## 1. Purpose

`design_ops_resolver` は Core Logic の自然言語記述から、サービス/リポジトリ用のステップキーを推定する補助モジュール。

## 2. Structured Specification

### Input
- **Description**: Core Logic の行配列とメソッド名（サービス系では fallback 操作を任意指定）。
- **Type/Format**: `List[str]`, `str`, `Optional[str]`
- **Example**: `["DBから一覧取得", "結果を返す"], "GetOrders"`

### Output
- **Description**: 推定されたステップキー配列（例: `repo.fetch_all` / `service.list`）。
- **Type/Format**: `List[str]`
- **Example**: `["service.list", "repo.fetch_all"]`

### Core Logic
1. 各行に対して `MorphAnalyzer → SyntacticAnalyzer → SemanticAnalyzer` の順で解析する。
2. トピック・構文語からクエリ文字列を作成し、`UnifiedKnowledgeBase` で候補検索する。
3. 候補の `intent/return_type/capabilities` からステップキーにマッピングする。
4. `infer_steps` はリポジトリ向け、`infer_service_steps` はサービス向けのマッピングを行う。
5. 解析回数/検索回数などの統計を `get_stats` で取得できる。

### Test Cases
- **Happy Path**:
  - **Scenario**: DB系の Core Logic を入力。
  - **Expected Output**: `repo.fetch_all` または `repo.update` が返る。
- **Edge Cases**:
  - **Scenario**: 解析結果に候補が無い。
  - **Expected Output / Behavior**: 空配列が返る。

## 3. Dependencies
- **Internal**:
  - `config_manager`
  - `morph_analyzer`
  - `syntactic_analyzer`
  - `semantic_analyzer`
  - `method_store`
  - `unified_knowledge_base`
  - `structural_memory`
  - `vector_engine`
