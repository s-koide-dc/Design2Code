# action_utils Design Document

## 1. Purpose

`action_utils` は文字列リテラル生成、ノードの複製、意図タグ付けなどの補助関数を提供する。

## 2. Structured Specification

### Input
- **Description**: 文字列、ノード辞書、ステートメント配列など。
- **Type/Format**: `str`, `Dict[str, Any]`, `List[Dict[str, Any]]`

### Output
- **Description**: 変換済み文字列や複製ノード、タグ付け済みステートメント。
- **Type/Format**: `str` / `Dict[str, Any]` / `None`

### Core Logic
1. `to_csharp_string_literal` は文字列を C# リテラルとしてエスケープする。
2. `safe_copy_node` はノードを深いコピーで複製する。
3. `is_known_state_property` は状態系プロパティ名を判定する。
4. `tag_intent_for_node` は `node_id` 一致のステートメントに intent を付与する。

### Test Cases
- **Happy Path**:
  - **Scenario**: `"hello"` をリテラル変換する。
  - **Expected Output**: `"\"hello\""` が返る。
- **Edge Cases**:
  - **Scenario**: `node_id` が一致しない。
  - **Expected Output / Behavior**: 変更されない。

## 3. Dependencies
- **Internal**: `code_synthesis`
