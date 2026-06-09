# advanced_tdd Design Document

## 1. Purpose (Updated 2026-04-14)

`advanced_tdd` はテスト失敗分析、修正提案、目標駆動型の合成を統合する。  
`AdvancedTDDSupport` を入口として、`TestFailureAnalyzer` と `CodeFixSuggestionEngine` を用いる。

## 2. Structured Specification

### Input
- **Description**: テスト失敗情報、TDD 目標、設定。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: 修正提案または合成結果。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. `advanced_tdd_config.json` を読み込み、デフォルトとマージする。
2. `AdvancedTDDSupport.__init__` は `TestFailureAnalyzer`、`CodeFixSuggestionEngine`、および `AutonomousSynthesizer` を束ねる。
3. `AutonomousSynthesizer` へは軽量な `ConfigAdapter` を渡し、`workspace_root`、`storage_dir`、`repair_knowledge_path`、`task_definitions_path`、`method_store_path` など TDD 実行に必要な設定参照点を決定論的に供給する。
4. `analyze_and_fix_test_failure` で失敗情報を `TestFailure` に変換し、分析と修正提案を返す。
5. `execute_goal_driven_tdd` で `AutonomousSynthesizer` を用いて合成を実行する。

### Test Cases
- **Happy Path**:
  - **Scenario**: テスト失敗情報から修正提案が生成される。
  - **Expected Output**: `status == "success"`。
- **Edge Cases**:
  - **Scenario**: 設定ファイルが壊れている。
  - **Expected Output / Behavior**: デフォルト設定で継続。

## 3. Dependencies
- **Internal**: `failure_analyzer`, `fix_engine`, `autonomous_synthesizer`
- **External**: `json`, `os`, `logging`

## 4. Review Notes
- 2026-04-14: AdvancedTDDSupport 入口と目標駆動TDDの流れを現行実装に合わせて再確認。
- 2026-06-09: `ConfigAdapter` 経由で `AutonomousSynthesizer` に repair knowledge / task definitions / method store の各パスを供給する現在の初期化経路を反映した。
