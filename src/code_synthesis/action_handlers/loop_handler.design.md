# loop_handler Design Document

## 1. Purpose

`loop_handler` はループノードの処理を ActionSynthesizer に委譲する。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、ループノード、パス、消費済みID集合。
- **Type/Format**: `Dict[str, Any]`, `set | None`

### Output
- **Description**: ループ処理後のパス配列。
- **Type/Format**: `List[Dict[str, Any]]`

### Core Logic
1. `_process_loop_node` に委譲し、結果を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: コレクションのループ。
  - **Expected Output**: `foreach` を含むパスが返る。
- **Edge Cases**:
  - **Scenario**: ループ対象が無い。
  - **Expected Output / Behavior**: 空配列となる。

## 3. Dependencies
- **Internal**: `code_synthesis`
