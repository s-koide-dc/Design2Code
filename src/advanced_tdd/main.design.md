# AdvancedTDDSupport Design Document

## 1. Purpose

`AdvancedTDDSupport` は高度 TDD 支援の入口であり、失敗分析と目標駆動の合成を提供する。

## 2. Structured Specification

### Input
- **Description**: `test_failure_data` または `goal_data`。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: 分析結果と修正提案、または合成結果。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. 設定を読み込み、`TestFailureAnalyzer` と `CodeFixSuggestionEngine` を初期化する。
2. `analyze_and_fix_test_failure` は失敗情報を構造化して分析し、修正提案を返す。
3. `execute_goal_driven_tdd` は `AutonomousSynthesizer` を使って合成を実行する。

### Test Cases
- **Happy Path**:
  - **Scenario**: テスト失敗データが正しく解析される。
  - **Expected Output**: `fix_suggestions` が返る。
- **Edge Cases**:
  - **Scenario**: 例外発生。
  - **Expected Output / Behavior**: `status == "error"`。

## 3. Dependencies
- **Internal**: `failure_analyzer`, `fix_engine`, `autonomous_synthesizer`
