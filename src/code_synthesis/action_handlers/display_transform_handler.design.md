# display_transform_handler Design Document

## 1. Purpose

`display_transform_handler` は DISPLAY/TRANSFORM 系ノードを処理し、専用変換処理に委譲する。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、対象ノード、パス。
- **Type/Format**: `Dict[str, Any]`
- **Example**: `node={"intent":"DISPLAY"}`

### Output
- **Description**: 変換結果パス、または `None`。
- **Type/Format**: `List[Dict[str, Any]] | None`
- **Example**: `[{"statements":[{"type":"raw","code":"Console.WriteLine(...);"}]}]`

### Core Logic
1. `process_display_transform_specialized` を呼ぶ。
2. 結果がある場合、`rank_tuple` を加点して優先度を上げる。
3. 結果が無い場合は `None` を返す。

## 4. Review Notes
- 2026-03-31: `display_transform_ops` の join-based 出力に追随するためレビュー済み。

### Test Cases
- **Happy Path**:
  - **Scenario**: DISPLAY ノードが処理される。
  - **Expected Output**: パスが返り `rank_tuple` が加点される。
- **Edge Cases**:
  - **Scenario**: 変換対象が無い。
  - **Expected Output / Behavior**: `None` が返る。

## 3. Dependencies
- **Internal**: `code_synthesis`
