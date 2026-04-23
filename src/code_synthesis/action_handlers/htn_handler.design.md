# htn_handler Design Document

## 1. Purpose

`htn_handler` は HTN プランを ActionSynthesizer に委譲して処理する。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、対象ノード、パス、HTN プラン配列。
- **Type/Format**: `Dict[str, Any]`, `list`
- **Example**: `htn_plan=["repo.fetch_all","service.list"]`

### Output
- **Description**: HTN 展開後のパス配列。
- **Type/Format**: `List[Dict[str, Any]]`

### Core Logic
1. `_process_htn_plan` に委譲し、その結果を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: HTN プランを処理する。
  - **Expected Output**: 展開済みパスが返る。
- **Edge Cases**:
  - **Scenario**: 空プラン。
  - **Expected Output / Behavior**: 空配列を返す。

## 3. Dependencies
- **Internal**: `code_synthesis`
