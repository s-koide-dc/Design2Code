# control_intents Design Document

## 1. Purpose

`control_intents` は対話制御で使う intent 名の共通定数を提供し、`pipeline_core`、`task_manager`、`intent_detector`、`planner`、`response_generator` に散っていた会話制御用の文字列直書きを排除する。

## 2. Structured Specification

### Input
- **Description**: なし。定数モジュールとして利用される。
- **Type/Format**: N/A

### Output
- **Description**: 会話制御用の intent 定数と、会話扱いする intent 集合。
- **Type/Format**: `str` / `Tuple[str, ...]`

### Core Logic
1. `INTENT_TIME`、`INTENT_GENERAL`、`INTENT_CANCEL_TASK`、`INTENT_FEEDBACK_RECEIVED` など、会話制御や確認フローに関わる intent 名を定義する。
2. `CONVERSATIONAL_INTENTS` は `pipeline_core` の会話ショートカット判定で使う共通集合を提供する。
3. `TASK_INTERRUPTION_INTENTS` は `NO_INTENT` を含めた割り込み判定用集合を提供し、`task_manager` の対話中断制御を安定化する。

### Test Cases
- **Happy Path**:
  - **Scenario**: `TaskManagementStage` が `INTENT_TIME` を受け取る。
  - **Expected Output**: `CONVERSATIONAL_INTENTS` / `TASK_INTERRUPTION_INTENTS` に基づいて割り込み扱いされる。
- **Edge Cases**:
  - **Scenario**: `INTENT_CANCEL_TASK` が pending confirmation 中に入る。
  - **Expected Output / Behavior**: 確認再表示へ進まず、キャンセル分岐に入る。

## 3. Dependencies
- **Internal**: なし
- **External**: なし
