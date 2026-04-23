# linq_handler Design Document

## 1. Purpose

`linq_handler` は LINQ フィルタノードの処理を ActionSynthesizer に委譲する。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、LINQ ノード、パス。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: LINQ 変換後のパス配列。
- **Type/Format**: `List[Dict[str, Any]]`

### Core Logic
1. `_process_linq_filter_block` を呼び出して結果を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: LINQ フィルタノード。
  - **Expected Output**: `Where` 等の式を含むパスが返る。
- **Edge Cases**:
  - **Scenario**: ノードが不完全。
  - **Expected Output / Behavior**: 内部処理結果に従う。

## 3. Dependencies
- **Internal**: `code_synthesis`
