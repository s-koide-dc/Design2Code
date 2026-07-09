# design_ops_resolver Design Document

## 1. Purpose

`design_ops_resolver` は Core Logic の自然言語記述から、サービス/リポジトリ用のステップキーを推定する補助モジュール。

### 1.1 Implementation Sync Notes (2026-07-08)
- 候補探索は `UnifiedKnowledgeBase` を優先し、vector engine が利用可能な場合だけ action patterns / canonical templates の semantic candidate search を補助的に使う。
- candidate score は候補の安定ソートと呼び出し元への metadata に使い、score だけで不適合な intent を採用しない。
- `filename` / `url` / JSON topic など、解析済み entity と topic から intent hint を作り、allowed / preferred / disallowed intent で候補を絞る。
- `infer_step_with_score_excluding_intents` は呼び出し元が除外した intent を再導入しない。
- メソッド名から create/update/delete/list をキーワード推定しない。`_map_execute_by_method` は明示された fallback を保持するだけにする。

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
2. topic と構文項からクエリ文字列を作成し、`UnifiedKnowledgeBase` で候補検索する。曖昧候補例外が返った場合は候補 ID から実体を取得する。
3. vector engine がある場合、action patterns と canonical templates を vectorize し、semantic candidate search を補助探索として使う。
4. entity / topic から intent hints を導出し、候補を allowed / preferred / disallowed intent で絞る。preferred がある探索では、preferred を満たさない候補を採用しない。
5. 候補の `id/intent/return_type/capabilities` からステップキーにマッピングする。
6. `infer_steps` はリポジトリ向け、`infer_service_steps` はサービス向けのマッピングを行う。
7. 解析回数/検索回数などの統計を `get_stats` で取得できる。

### Test Cases
- **Happy Path**:
  - **Scenario**: DB系の Core Logic を入力。
  - **Expected Output**: `repo.fetch_all` または `repo.update` が返る。
- **Edge Cases**:
  - **Scenario**: 解析結果に候補が無い。
  - **Expected Output / Behavior**: 空配列が返る。
  - **Scenario**: URL entity がある。
  - **Expected Output / Behavior**: `HTTP_REQUEST` 以外の候補を採用しない。
  - **Scenario**: filename entity がある。
  - **Expected Output / Behavior**: `HTTP_REQUEST` を除外し、`FILE_IO` / `FETCH` を優先する。
  - **Scenario**: 呼び出し元が除外 intent を指定する。
  - **Expected Output / Behavior**: fallback 探索でも除外 intent は返さない。

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
