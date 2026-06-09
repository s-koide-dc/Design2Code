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
2. `analyze_and_fix_test_failure` は失敗情報を構造化して分析し、`analysis_summary` と `reason` / `recommended_action` / `target_summary` を保持した修正提案を返す。
3. `execute_goal_driven_tdd` は `AutonomousSynthesizer` を使って合成を実行する。
4. `_suggestion_to_dict` は `CodeFixSuggestion` の `impact_analysis` に加え、`target_file`、`conversation_hint`、`reason`、`recommended_action`、`target_summary` を会話層向けに露出する。

### Test Cases
- **Happy Path**:
  - **Scenario**: テスト失敗データが正しく解析される。
  - **Expected Output**: `fix_suggestions` が返る。
- **Edge Cases**:
  - **Scenario**: 例外発生。
  - **Expected Output / Behavior**: `status == "error"`。

## 3. Dependencies
- **Internal**: `failure_analyzer`, `fix_engine`, `autonomous_synthesizer`

## 4. Operational Notes
- `execute_goal_driven_tdd` の補助診断と `__main__` のサンプル結果表示は `src.utils.stdout_guard.debug_print` を通す。
- 通常利用時の stdout 汚染を避けつつ、`NLP_DEBUG_STDOUT=1` で手動確認を継続できる。
