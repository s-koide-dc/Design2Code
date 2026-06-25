# StructuredSpec Validator Design Document

## 1. Purpose

`validate_structured_spec` / `validate_structured_spec_or_raise` は `StructuredSpec` の形式・参照整合性を検証する。  
必須キー、ID 形式、`source_ref` と `data_sources` の整合、意図別の必須属性などをチェックし、問題があればエラーを返す。

## 2. Structured Specification

### Input
- **Description**: `StructuredSpec` 辞書。
- **Type/Format**: `Dict[str, Any]`
- **Example**:
  ```json
  {
    "module_name": "Sample",
    "purpose": "Example",
    "inputs": [],
    "outputs": [],
    "steps": [],
    "constraints": [],
    "test_cases": [],
    "data_sources": []
  }
  ```

### Output
- **Description**: 検証結果。`validate_structured_spec` はエラー文字列の配列、`validate_structured_spec_or_raise` は例外送出。
- **Type/Format**: `List[str]` または例外
- **Example**:
  ```json
  ["missing top-level key: module_name"]
  ```

### Core Logic
1. 必須トップレベルキー（`module_name`/`purpose`/`inputs`/`outputs`/`steps`/`constraints`/`test_cases`/`data_sources`）の存在を検証する。
2. `data_sources` の `id` 形式（英数字と `_`）と `kind` を検証し、`source_kind_map` を構築する。
3. `steps` の必須キー、`kind`・`side_effect`・`source_kind` の許可値、`id` 形式を検証する。
4. `input_refs`/`depends_on` の参照先が `steps` に存在するか検証する。
5. `intent=FETCH` の場合は `source_ref` と `source_kind` が有効であることを検証し、`source_kind=file` のときは `source_ref(kind=file)` または `semantic_roles.path` のどちらかが必須であることを検証する。
6. `intent=DATABASE_QUERY` の場合は `source_ref(kind=db)` と `semantic_roles.sql` が必須であることを検証する。
7. `intent=HTTP_REQUEST` の場合は `source_ref(kind=http)` と `source_kind=http`、および `semantic_roles.url` が必須であることを検証する。
8. `intent=PERSIST` のうち DB 保存として解釈されるものは、`source_kind=db` と `semantic_roles.sql` が必須であることを検証する。
9. `test_cases` の ID 形式と必須キーを検証する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 形式と参照が正しい `StructuredSpec` を検証。
  - **Expected Output**: エラーリストが空。
- **Edge Cases**:
  - **Scenario**: `data_sources` の ID が `a.b` のように不正。
  - **Expected Output / Behavior**: `data_sources id format is invalid` を含むエラー。
  - **Scenario**: `DATABASE_QUERY` で `semantic_roles.sql` が欠落。
  - **Expected Output / Behavior**: `intent=DATABASE_QUERY requires semantic_roles.sql` を含むエラー。
  - **Scenario**: file 向け `FETCH` で `semantic_roles.path` と file source の両方が欠落。
  - **Expected Output / Behavior**: `intent=FETCH source_kind=file requires source_ref(kind=file) or semantic_roles.path` を含むエラー。
  - **Scenario**: `HTTP_REQUEST` で `semantic_roles.url` が欠落。
  - **Expected Output / Behavior**: `intent=HTTP_REQUEST requires semantic_roles.url` を含むエラー。
  - **Scenario**: DB 向け `PERSIST` で `semantic_roles.sql` が欠落。
  - **Expected Output / Behavior**: `intent=PERSIST source_ref(kind=db) requires semantic_roles.sql` を含むエラー。

## 3. Dependencies
- **Internal**: なし（標準ライブラリのみ）
