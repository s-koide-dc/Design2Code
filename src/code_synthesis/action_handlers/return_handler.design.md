# return_handler Design Document

## 1. Purpose

`return_handler` は return ノードの処理を ActionSynthesizer に委譲する。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、return ノード、パス。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: return 処理後のパス配列。
- **Type/Format**: `List[Dict[str, Any]]`

### Core Logic
1. `_process_return_node` を呼び出して結果を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: return ノード。
  - **Expected Output**: `return` 文を含むパスが返る。
- **Edge Cases**:
  - **Scenario**: return 生成失敗。
  - **Expected Output / Behavior**: 内部処理結果に従う。

## 3. Dependencies
- **Internal**: `code_synthesis`
