# task_manager Design Document

## 1. Purpose

`TaskManager` は対話セッション内のタスク状態を管理し、必要な情報が揃った時点で実行可能なタスクへ遷移させる。  
単純タスクと複合タスク（サブタスク列）を扱い、承認ワークフロー、永続化、メトリクス収集、セッション管理、回復タスク生成を行う。

## 2. Structured Specification

### Input
- **Description**: `analysis.intent` と `analysis.entities` を含むコンテキスト。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: `task` と `clarification_needed` が更新されたコンテキスト。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. 設定値を読み込み、`TaskPersistence` / `SessionManager` / `ConditionEvaluator` / `ApprovalMessageGenerator` / `TaskManagerMetrics` を初期化する。`config_manager` と環境変数で永続化、セッション上限、タイムアウト、デバッグ設定を決定する。
2. 安全ポリシーから破壊的意図を読み込み、クリティカルタスク（例: `FILE_DELETE`, `CMD_RUN`）の承認対象を決定する。
3. `manage_task_state` でセッション活動を更新し、セッション上限を超えている場合はエラーを返す。
4. 10% 確率で `cleanup_stale_sessions` を実行し、古いセッションや永続化ファイルをクリーンアップする。
5. `PROVIDE_CONTENT` でアクティブタスクが存在せず、`filename` がある場合は `FILE_CREATE` として扱う。
6. 既存タスクがある場合、抽出されたエンティティを `task.parameters` に反映し、信頼度が高い値で上書きする。
7. `CLARIFICATION_RESPONSE` / `AGREE` / `DISAGREE` は最優先で処理し、`CLARIFICATION_RESPONSE` の遷移ルールに従って承認/取消を判定する。
8. 会話的意図かつエンティティ無しの場合は割り込みとして扱い、タスク状態を維持したまま `task_interruption` を返す。
9. 永続化が有効な場合はセッションからタスク状態を復元する。
10. `CANCEL_TASK` はアクティブタスクを解除して即時に戻す。
11. 新規タスクの場合:
   - 単純タスクは `INIT` 状態で開始し、必須エンティティが揃えば `READY_FOR_EXECUTION` へ遷移する。
   - 複合タスクは全体承認が必要であれば `clarification_needed` を立てる。
12. 複合タスク実行時はサブタスクの状態遷移と承認を処理し、クリティカルサブタスクでは二段階承認（全体承認とサブタスク承認）を要求できる。
13. 不足エンティティがある場合は `clarification_message` を生成し、`awaiting_entity` を記録する。
14. 実行後は `update_task_after_execution` で `COMPLETED/FAILED` を反映し、完了時にタスクをリセットする。
15. `create_recovery_task` は失敗結果から回復用の複合タスクを生成し、試行回数をカウントする。

### Test Cases
- **Happy Path**:
  - **Scenario**: 必須エンティティが揃い、`READY_FOR_EXECUTION` へ遷移。
  - **Expected Output**: `task.state == "READY_FOR_EXECUTION"`。
- **Edge Cases**:
  - **Scenario**: 会話的意図で割り込み発生。
  - **Expected Output / Behavior**: `task_interruption == true`、タスク状態維持。
  - **Scenario**: クリティカルサブタスクで承認が必要。
  - **Expected Output / Behavior**: `clarification_needed == true`。
  - **Scenario**: `CANCEL_TASK` が入力される。
  - **Expected Output / Behavior**: アクティブタスクが解除される。
  - **Scenario**: セッション数上限超過。
  - **Expected Output / Behavior**: `errors` に上限超過メッセージが追加される。

## 3. Dependencies
- **Internal**: `metrics`, `task_persistence`, `condition_evaluator`, `session_manager`, `approval_messages`, `config_manager`
- **External**: `json`, `os`, `time`, `uuid`
