# StructuredDesignParser Design Document

## 1. Purpose

`StructuredDesignParser` は `.design.md` を読み込み、`StructuredSpec`（入力/出力/ステップ/データソース/テストケース）へ変換する。設計書内の明示メタデータと `ops`/`semantic_roles` を優先し、ヒューリスティック抽出に依存しない決定的な変換を行う。

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
1. `DesignDocParser` で Markdown を一次解析し、`module_name` / `purpose` / `specification` を取得する。
2. `specification.core_logic` から `[data_source|id|kind]` を抽出して `data_sources` に登録する。
3. 同じ Core Logic 行を `step_1 ... step_n` の構造化ステップへ変換する。  
   - `[KIND|INTENT|TARGET|OUTPUT|SIDE_EFFECT|SOURCE_REF|SOURCE_KIND]` を解析し、`kind/intent/target_entity/output_type/side_effect/source_ref/source_kind` を生成する。  
   - `[refs:...]`/`[ops:...]`/`[semantic_roles:{...}]` を順に解析し、`input_refs` と `semantic_roles` に反映する。  
4. `source_ref` と `data_sources` を突合して `source_kind` を補完し、`FETCH` で未指定の場合は `file` を既定値とする。
5. `test_cases` を `tc_1..` 形式の構造体に変換する。
6. `validate_structured_spec_or_raise` を実行し、形式・参照整合性を検証する。

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
  - **Scenario**: `data_source` の kind が許可されていない。
  - **Input**: `[data_source|x|ftp] ...`
  - **Expected Output / Behavior**: `data_sources` に登録されず、バリデーションで不正として扱われる。

## 3. Dependencies
- **Internal**: `design_doc_parser`, `validator`
