# action_executor Design Document
<!-- metadata-sync: 2026-07-09T00:00:00+09:00 -->

## 1. Purpose

`action_executor` は Planner が決定した `action_method` を実行し、ファイル操作・コマンド実行・解析/テスト・TDD支援などの具体的な副作用を担当する。  
安全性のため、パスとコマンドは厳格に検証し、実行結果を `action_result` に格納する。

### 1.1 Implementation Sync Notes (2026-07-08)
- intent 判定は `src.utils.action_intents` の定数を使い、Planner / TaskManager と同じ intent 名を共有する。
- 実処理は `FileOperations`、`CSharpOperations`、`TestAndCoverageOperations`、`RefactoringOperations`、`CICDOperations`、`TDDOperations` へ委譲し、`ActionExecutor` は実行前検証、バックアップ、結果メタデータ補完、例外処理の責務を持つ。
- エラーパターン設定はレガシーな `regex` キーを `message_contains` へ正規化するが、実行時マッチングは正規表現評価ではなく例外型と構造化された literal 条件で行う。

## 2. Structured Specification

### Input
- **Description**: `context.plan.action_method` と `context.plan.parameters`。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: `action_result` を更新したコンテキスト。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. `plan` から `action_method` と `parameters` を取得する。
2. `safety_check_status == "BLOCK"` の場合は実行を拒否する。
3. `confirmation_needed == true` かつ `confirmation_granted/confirmed` が未設定の場合は実行を拒否する。
4. `action_method` が存在すれば `execute_action` で該当メソッドを呼び出す。
5. 実行後、`ActionResultMetadata` が `dialogue_metadata.action_method` / `intent` / 主要パラメータを補完し、対話層が安定して参照できる形へ正規化する。
6. 実行結果を `action_result` に格納し、ログへ記録する。
7. `_safe_join` でワークスペース外アクセスを拒否する。
8. `_run_command` でホワイトリストとサブコマンド検証、禁止オプション、メタ文字、読み取り/一覧パス制限を行う（既定の読み取り許可ディレクトリは `AIFiles/config/docs/scripts/src/tests` のみ）。
9. `python/py` は `scripts/` 配下かつ allowlist (`python_allowed_scripts`) に限定する。
10. `FILE_DELETE` / `APPLY_CODE_FIX` / `APPLY_REFACTORING` は実行前にバックアップが必須。
11. `get_required_entities_for_intent` の主要 action intent 判定は `src.utils.action_intents` の共通定数を使い、実行条件分岐の文字列直書きを避ける。
12. `CommandPolicyValidator` がコマンド分割、allowlist、サブコマンド、引数、パス、Python スクリプトの検証を担当する。許可済みコマンドは引数配列と `shell=False` で実行し、終了コードが非0の場合は `action_result.status="error"` と `returncode` を返す。学習イベントの記録有無にかかわらず失敗を成功扱いしない。
13. コード修正の事前バックアップ対象は、明示された `filename` が無い場合、履歴中の構造化修正提案の `target_file` から解決する。
14. `MEASURE_COVERAGE` / `ANALYZE_COVERAGE_GAPS` / `GENERATE_COVERAGE_REPORT` は `TestAndCoverageOperations` に委譲する。
15. `ANALYZE_REFACTORING` / `SUGGEST_REFACTORING` / `APPLY_REFACTORING` は `RefactoringOperations` に委譲し、適用系はバックアップ検証を通過した場合のみ実行する。
16. `ANALYZE_TEST_FAILURE` / `EXECUTE_GOAL_DRIVEN_TDD` / `APPLY_CODE_FIX` は `TDDOperations` に委譲し、対話層向け metadata は戻り値の `action_result` に保持する。
17. `RUN_LEARNING_CYCLE` / `MANAGE_KNOWLEDGE` / `REVERSE_DICTIONARY_SEARCH` は `autonomous_learning` と semantic / vector search の有効状態を確認してから実行する。
18. `_run_command` は `subprocess.run(..., cwd=workspace_root, shell=False)` で実行し、相対パスの解決先を操作対象ワークスペースと一致させる。

### Test Cases
- **Happy Path**:
  - **Scenario**: `FILE_READ` の実行。
  - **Expected Output**: `action_result.status == "success"`。
- **Edge Cases**:
  - **Scenario**: ワークスペース外のパス指定。
  - **Expected Output / Behavior**: `action_result.status == "error"`。
- **Scenario**: ホワイトリスト外コマンド。
  - **Expected Output / Behavior**: `action_result.status == "error"`。
- **Edge Cases**:
  - **Scenario**: `npm` の許可サブコマンド以外を実行。
  - **Expected Output / Behavior**: `action_result.status == "error"`。
  - **Scenario**: カスタムアクションが `action_result` を返す。
  - **Expected Output / Behavior**: `dialogue_metadata.action_method` と `dialogue_metadata.intent` が補完される。

## 3. Dependencies
- **Internal**: `file_operations`, `csharp_operations`, `test_operations`, `refactoring_operations`, `cicd_operations`, `tdd_operations`, `semantic_analyzer`
- **External**: `os`, `subprocess`, `shlex`, `json`, `re`

## 4. Review Notes
- 2026-06-29: コマンド非0終了のエラー契約と、構造化引数による非シェル実行を反映。
- 2026-06-30: 履歴中の修正提案を使ったコード修正の事前バックアップ対象解決を反映。
- 2026-07-08: action intent 定数化、operation class 委譲、TDD / coverage / refactoring / learning 系 action の実行契約を反映。
