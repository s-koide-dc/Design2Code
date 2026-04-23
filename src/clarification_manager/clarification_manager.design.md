# clarification_manager Design Document

## 1. Purpose

`clarification_manager` は意図・エンティティの不確実性や必須情報不足を検出し、ユーザーに明確化メッセージを提示する。  
TaskManager が既に明確化を要求している場合はその状態を尊重する。

## 2. Structured Specification

### Input
- **Description**: `intent_confidence`、`entities`、`errors` を含むコンテキスト。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: `clarification_needed` と `response.text` を更新したコンテキスト。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. 起動時にテンプレートを `resources/knowledge_base.json` から読み込み、未存在時はデフォルトテンプレートを使用する。
2. `clarification_needed` が既に True の場合は、`task.clarification_message` を優先して返す。
3. `errors` があればエラー内容を明確化メッセージとして返す。
4. `clarification_history` を使って試行回数を追跡し、上限に達したら最終メッセージを返して回数をリセットする。
5. `task.state == READY_FOR_EXECUTION` の場合は低い `intent_confidence` を理由にブロックしない。
6. `intent_confidence` が閾値未満なら意図確認メッセージを返す。
7. エンティティの信頼度が閾値未満なら該当エンティティの確認メッセージを返す。
8. 必須エンティティが不足していれば、テンプレートに基づいた質問を返す。複合タスクの場合は現在のサブタスクの `parameters` を含めて不足判定する。
9. 生成したメッセージを `response.text` に設定し、`clarification_needed` を True にする。

### Test Cases
- **Happy Path**:
  - **Scenario**: すべての必須情報が揃っている。
  - **Expected Output**: `clarification_needed == false`。
- **Edge Cases**:
  - **Scenario**: `intent_confidence` が閾値未満。
  - **Expected Output / Behavior**: 意図確認メッセージを返す。
  - **Scenario**: 試行回数が上限に達する。
  - **Expected Output / Behavior**: 最終メッセージを返し、回数をリセット。
  - **Scenario**: `task.state == READY_FOR_EXECUTION`。
  - **Expected Output / Behavior**: 低い `intent_confidence` でも確認を挟まずに進める。

## 3. Dependencies
- **Internal**: `action_executor`, `log_manager`
- **External**: `json`, `os`
