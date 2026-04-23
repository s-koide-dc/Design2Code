# action_executor Design Document

## 1. Purpose

`action_executor` は Planner が決定した `action_method` を実行し、ファイル操作・コマンド実行・解析/テスト・TDD支援などの具体的な副作用を担当する。  
安全性のため、パスとコマンドは厳格に検証し、実行結果を `action_result` に格納する。

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
5. 実行結果を `action_result` に格納し、ログへ記録する。
6. `_safe_join` でワークスペース外アクセスを拒否する。
7. `_run_command` でホワイトリストとサブコマンド検証、禁止オプション、メタ文字、読み取り/一覧パス制限を行う（既定の読み取り許可ディレクトリは `AIFiles/config/docs/scripts/src/tests` のみ）。
8. `python/py` は `scripts/` 配下かつ allowlist (`python_allowed_scripts`) に限定する。
9. `FILE_DELETE` / `APPLY_CODE_FIX` / `APPLY_REFACTORING` は実行前にバックアップが必須。

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

## 3. Dependencies
- **Internal**: `file_operations`, `csharp_operations`, `test_operations`, `refactoring_operations`, `cicd_operations`, `tdd_operations`, `semantic_analyzer`
- **External**: `os`, `subprocess`, `shlex`, `json`, `re`
