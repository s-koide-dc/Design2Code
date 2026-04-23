# replanner Design Document

## 1. Purpose

`Replanner` は合成失敗の原因を解析し、IR をパッチして再合成を試みる。  
`ReasonAnalyzer` がヒントを生成し、`IRPatcher` が修正を適用する。

## 2. Structured Specification

### Input
- **Description**: `structured_spec` / `ir_tree` / `synthesis_result` / `verification_result` / `semantic_issues`。
- **Type/Format**: `Dict[str, Any]` / `List[str]`

### Output
- **Description**: パッチ済み IR とヒント一覧。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. `ReasonAnalyzer.analyze` で失敗理由を抽出する。
2. `analyze_logic_mismatch` で論理不一致の追加ヒントを収集する。
3. 同一ヒントの繰り返しを履歴で検出し、無限ループを防ぐ。
4. `IRPatcher.apply_patches` で IR を修正し、`patched_ir` を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 修正可能なヒントが生成される。
  - **Expected Output**: `status == "REPLANNED"`。
- **Edge Cases**:
  - **Scenario**: ヒントが空。
  - **Expected Output / Behavior**: `status == "FAILED"`。
  - **Scenario**: 同一ヒントが繰り返される。
  - **Expected Output / Behavior**: 収束エラーとして失敗。

## 3. Dependencies
- **Internal**: `reason_analyzer`, `ir_patcher`
