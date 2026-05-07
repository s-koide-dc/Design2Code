# data_source_utils Design Document

## 1. Purpose

`data_source_utils` は Core Logic 行に埋め込まれた `[data_source|id|kind]` タグを決定的に解析し、`StructuredSpec.data_sources` の最小構造へ変換する。

## 2. Structured Specification

### Input
- **Description**: 1 行の Core Logic テキストと、許可される `data_source.kind` 集合。
- **Type/Format**: `str`, `set[str]`
- **Example**: `"[data_source|user_db|db] Users table"`

### Output
- **Description**: `id` と `kind` を持つ辞書。条件を満たさない場合は空辞書。
- **Type/Format**: `Dict[str, str]`
- **Example**: `{"id":"user_db","kind":"db"}`

### Core Logic
1. 入力行を文字列化し、先頭の Markdown 箇条書き `- ` を除去する。
2. `[data_source|` で始まらない場合は空辞書を返す。
3. 最初の `]` までをタグ本体として取り出し、`|` 区切りで分解する。
4. `source_id` または `source_kind` が空なら空辞書を返す。
5. `source_kind` を小文字化し、`allowed_kinds` に含まれない場合は空辞書を返す。
6. 条件を満たした場合のみ `{"id": source_id, "kind": source_kind}` を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 許可済み `db` data_source を含む。
  - **Expected Output**: `id` と `kind` を返す。
- **Edge Cases**:
  - **Scenario**: 閉じ bracket が無い。
  - **Expected Output / Behavior**: 空辞書を返す。
  - **Scenario**: `kind` が許可されていない。
  - **Expected Output / Behavior**: 空辞書を返す。

## 3. Dependencies
- **Internal**: なし
- **External**: なし
