# StructuredDesignParser Design Document

## 1. Purpose

`StructuredDesignParser` は `.design.md` を読み込み、`StructuredSpec`（入力/出力/ステップ/データソース/テストケース/entity specs）へ変換する。設計書内の明示メタデータと `ops`/`semantic_roles` を優先し、ヒューリスティック抽出に依存しない決定的な変換を行う。

## 2. Structured Specification

### Input
- **Description**: `.design.md` のパスまたは Markdown 文字列。
- **Type/Format**: `str`
- **Example**: `"src/sample/sample.design.md"`

### Output
- **Description**: 構造化仕様 `StructuredSpec`。
- **Type/Format**: `Dict[str, Any]`
- **Example**:
  ```json
  {
    "module_name": "Sample",
    "purpose": "Example",
    "inputs": [],
    "outputs": [],
    "steps": [],
    "test_cases": [],
    "data_sources": []
  }
  ```

### Core Logic
1. `compact_step_expander` で短縮ステップ記法を標準の Core Logic 表現へ展開する。構文エラーがある場合は行番号と理由を含めて fail-closed で中断し、未展開のまま後続パーサーへ渡さない。
2. `DesignDocParser` で正規化済み Markdown を一次解析し、`module_name` / `purpose` / `specification` を取得する。
3. `specification.core_logic` から `[data_source|id|kind]` を抽出して `data_sources` に登録する。
   - `semantic_roles` の JSON に配列が含まれていても bracket 境界を壊さないよう、prefix 解析は `[` `]` のネストを考慮して行う。
4. 同じ Core Logic 行を `step_1 ... step_n` の構造化ステップへ変換する。
   - `[KIND|INTENT|TARGET|OUTPUT|SIDE_EFFECT|SOURCE_REF|SOURCE_KIND]` を解析し、`kind/intent/target_entity/output_type/side_effect/source_ref/source_kind` を生成する。  
   - `[refs:...]`/`[ops:...]`/`[semantic_roles:{...}]`/`[logic:[...]]` を順に解析し、`input_refs`、`semantic_roles`、明示 predicate goals に反映する。
   - `logic` は JSON object の配列だけを受理し、自然文から条件を補完・創作しない。
   - `logic` の JSON 構文不正、配列以外、object 以外の要素、重複タグは構造仕様エラーとして fail-closed に扱う。
   - `semantic_roles.ops` のような JSON array もそのまま保持する。
5. `source_ref` と `data_sources` を突合して `source_kind` を補完し、`FETCH` で未指定の場合は `file` を既定値とする。内部 semantic intent / node kind の既定語彙には `src.utils.semantic_intents` の共通定数を使う。
6. `### Entity Specs` / `### Entities` の箇条書きを明示 schema として読み、`entity_specs` に entity 名と property 型を保持する。
7. `test_cases` を `tc_1..` 形式の構造体に変換する。
8. `validate_structured_spec_or_raise` を実行し、形式・参照整合性を検証する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 明示メタデータ付き設計書の解析。
  - **Input**:
    ```markdown
    ## Core Logic
    1. [data_source|user_db|db] Users table
    2. [ACTION|DATABASE_QUERY|User|List<User>|DB|user_db|db] [semantic_roles:{"sql":"SELECT * FROM Users"}] fetch
    ```
  - **Expected Output**: `data_sources[0].id == "user_db"`、`steps[0].intent == "DATABASE_QUERY"`。
- **Edge Cases**:
  - **Scenario**: `[step|...]` の短縮記法を含む設計書を旧互換 API から解析する。
  - **Expected Output / Behavior**: 展開後の `step_n` が生成され、通常記法と同じ構造化仕様になる。
  - **Scenario**: `data_source` の kind が許可されていない。
  - **Input**: `[data_source|x|ftp] ...`
  - **Expected Output / Behavior**: `data_sources` に登録されず、バリデーションで不正として扱われる。

## 3. Dependencies
- **Internal**: `compact_step_expander`, `design_doc_parser`, `validator`
