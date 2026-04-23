# calc_handler Design Document

## 1. Purpose

`calc_handler` は CALC ノードの処理を委譲し、意図タグ付けと優先度調整を行う。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、対象ノード、現在のパス状態。
- **Type/Format**: `Dict[str, Any]`, `Dict[str, Any]`
- **Example**: `node={"intent":"CALC","id":"step_1"}`

### Output
- **Description**: CALC 処理済みのパス配列。
- **Type/Format**: `List[Dict[str, Any]]`
- **Example**: `[{"statements":[...],"rank_tuple":(...)}]`

### Core Logic
1. `process_calc_node` を呼び出して CALC ノードを処理する。
2. 生成された各パスの `statements` に対して `CALC` の intent をタグ付けする。
3. `rank_tuple` のスコアを加点して優先度を上げる。

### Test Cases
- **Happy Path**:
  - **Scenario**: CALC ノードが正常処理される。
  - **Expected Output**: 返却パスに `CALC` intent が付与され、rank が加点される。
- **Edge Cases**:
  - **Scenario**: `process_calc_node` が空配列を返す。
  - **Expected Output / Behavior**: 空配列が返る。

## 3. Dependencies
- **Internal**: `code_synthesis`

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.

