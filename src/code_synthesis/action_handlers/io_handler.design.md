# io_handler Design Document

## 1. Purpose

`io_handler` は IO 系ノードに対して候補を評価し、合成またはフォールバックを実行する。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、対象ノード、パス。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: IO 処理後のパス配列。
- **Type/Format**: `List[Dict[str, Any]]`

### Core Logic
1. `gather_candidates` で候補を取得する。
2. `steps` を持つ候補は HTN として `_process_htn_plan` に渡す。
3. 通常候補は `_synthesize_single_method` で合成する。
4. 結果が空の場合は `apply_fallbacks` を試す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 候補が存在する。
  - **Expected Output**: 合成結果が返る。
- **Edge Cases**:
  - **Scenario**: 候補が空でフォールバックが有効。
  - **Expected Output / Behavior**: フォールバック結果が返る。

## 3. Dependencies
- **Internal**: `code_synthesis`
