# action_intents Design Document

## 1. Purpose

`action_intents` はファイル操作、C#解析、TDD、設計書生成などの主要 action intent 名を共通定数として定義し、実装コード内の action 分岐から文字列直書きを減らす。

## 2. Structured Specification

### Input
- **Description**: なし。定数モジュールとして利用される。
- **Type/Format**: N/A

### Output
- **Description**: action intent 定数と、一部の共通 intent 集合。
- **Type/Format**: `str` / `Tuple[str, ...]`

### Core Logic
1. `INTENT_FILE_CREATE`、`INTENT_CMD_RUN`、`INTENT_EXECUTE_GOAL_DRIVEN_TDD`、`INTENT_PROVIDE_CRITERIA` など、実行系 intent 名を定義する。
2. `FILE_MUTATION_INTENTS` は `planner` の命名規則補正対象をまとめる。
3. `PROJECT_LANGUAGE_DEFAULT_INTENTS` は `planner` が `language="csharp"` を自動補完する対象 intent 群をまとめる。

### Test Cases
- **Happy Path**:
  - **Scenario**: `Planner` が `INTENT_FILE_CREATE` を処理する。
  - **Expected Output**: ActionExecutor メソッド解決や project rule 判定が定数経由で行われる。
- **Edge Cases**:
  - **Scenario**: `TaskManager` が `INTENT_PROVIDE_CONTENT` を単独で受け取る。
  - **Expected Output / Behavior**: `INTENT_FILE_CREATE` へ正規化される。

## 3. Dependencies
- **Internal**: なし
- **External**: なし
