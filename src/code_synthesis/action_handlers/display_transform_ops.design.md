# display_transform_ops Design Document

## 1. Purpose

`display_transform_ops` は DISPLAY/TRANSFORM ノード向けの具体的な変換ロジックを実装する。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、対象ノード、パス、ops 配列。
- **Type/Format**: `Dict[str, Any]`, `List[str]`
- **Example**: `ops=["trim_upper","split_lines"]`

### Output
- **Description**: 変換ステートメントを含むパス配列、または `None`。
- **Type/Format**: `List[Dict[str, Any]] | None`

### Core Logic
1. `semantic_roles.ops` がある場合は ops 設定に基づいて変換を行う。
   - source 選択は `transform_source_resolution` を優先する。
   - `source_var` は explicit source として扱う。
   - `input_link_var` は exact upstream node id から var を引き、`active_scope_item` より優先する。
   - 生成した raw ステートメントには `consumes` に入力変数を付与し、到達性監査の正確性を確保する。
2. `DISPLAY` で明示メッセージがある場合は `Console.WriteLine` を生成する。
   - `property` / `display_property_resolution` がある場合は property-backed display を優先する。
3. `DISPLAY` + `display_names` の場合、コレクションを `string.Join` + `Select` で連結し、単一の `Console.WriteLine` にまとめる。
4. 通知系 DISPLAY はプリミティブ型なら値を出力し、そうでなければ定型文を出力する。
5. コレクション出力では `string.Join` を優先し、逐次 `foreach` 出力は避ける。
6. `TRANSFORM` は非文字列型を `ToString` で変換する。
7. loop item continuity と property-backed display が揃っている場合、`名前を表示する` のような child display は `Console.WriteLine(item.Name)` に落ちる。
8. `DISPLAY` / `TRANSFORM` の高頻度分岐は `src.utils.semantic_intents` の共通定数を使う。

### Test Cases
- **Happy Path**:
  - **Scenario**: `ops:trim_upper` を含む。
  - **Expected Output**: 変換コードが生成される。
  - **Scenario**: `transform_source_node_id` があり current `active_scope_item` と異なる。
  - **Expected Output**: exact upstream var が使われる。
- **Edge Cases**:
  - **Scenario**: 変換に必要な入力が無い。
  - **Expected Output / Behavior**: `None` が返る。

## 3. Dependencies
- **Internal**:
  - `code_synthesis`
  - `action_utils`
  - `text_parser`

## 4. Review Notes
- 2026-06-04: `DISPLAY` / `TRANSFORM` の specialized 分岐を `src.utils.semantic_intents` の共通語彙へ寄せた。
