# safety_policy_validator Design Document

## 1. Purpose

`safety_policy_validator`モジュールは、`Planner`が生成しようとしているアクションの安全性を計画段階で検証するためのポリシーとロジックを提供します。
`ActionExecutor`による実行時の強制的なセキュリティチェック（「最後の砦」）とは異なり、このモジュールはユーザー承認の要否判定（リスク評価）や、危険な操作の早期発見・警告を行うことを目的としています。

## 2. Structured Specification

### Input

- **Description**: 検証対象のアクションメソッド名、パラメータ、および元の意図。
- **Type/Format**: 
    - `action_method` (str): `ActionExecutor`のメソッド名（例: `_run_command`）。
    - `parameters` (dict): アクションのパラメータ（例: `{"command": "rm -rf /"}`）。
    - `intent` (str, optional): 元の意図（例: `CMD_RUN`）。
- **Example**:
  ```python
  action_method = "_run_command"
  parameters = {"command": "ls -l"}
  intent = "CMD_RUN"
  ```

### Output

- **Description**: 安全性検証の結果オブジェクト。ステータス、メッセージ、リスクレベルを含む。
- **Type/Format**: `SafetyCheckResult` (dataclass)
    - `status` (SafetyCheckStatus): `OK`, `BLOCK`, `WARN`
    - `message` (str): 説明メッセージ。
    - `risk_level` (RiskLevel): `LOW`, `MEDIUM`, `HIGH`
- **Example**:
  ```python
  SafetyCheckResult(
      status=SafetyCheckStatus.OK,
      message="Safety Check OK",
      risk_level=RiskLevel.HIGH # CMD_RUNは高リスク
  )
  ```

### Core Logic

1.  **ActionExecutor連携**: `ActionExecutor`インスタンスを参照し、`CMD_RUN` のコマンド名が `safe_commands` に含まれるか検証する。
2.  **サブコマンド検証**: `allowed_subcommands` が定義されている場合、許可サブコマンド以外は `BLOCK`。
3.  **禁止オプション**: `disallowed_args` に該当するオプションを含む場合は `BLOCK`。
4.  **メタ文字検証**: `blocked_metacharacters` を含む場合は `BLOCK`。
5.  **python/py 制限**: スクリプト指定必須、`python_allowed_dirs` と `python_allowed_scripts` に一致する場合のみ許可。
6.  **read/list 制限**: `read_commands` / `list_commands` は `read_allowed_dirs` の範囲に限定。
7.  **破壊的操作の判定**: 削除 (`FILE_DELETE`)、移動 (`FILE_MOVE`)、コード修正 (`APPLY_CODE_FIX`, `APPLY_REFACTORING`) などの意図を**高リスク (HIGH)** として判定し、承認を要求する。
8.  **バックアップ付き削除**: `BACKUP_AND_DELETE` は高リスクとして扱う。
9.  **注意が必要な操作の判定**: コマンド実行 (`CMD_RUN`)、ファイル追記 (`FILE_APPEND`)、新規作成 (`FILE_CREATE`) などを**高リスク (HIGH)** または **中リスク (MEDIUM)** として判定する。
10. **結果返却**: 判定結果に基づいて `SafetyCheckResult` を返す。

### Test Cases

- **安全な操作**:
  - **Scenario**: ファイル読み込み。
  - **Input**: `intent: FILE_READ`
  - **Expected Output**: `status: OK`, `risk_level: LOW`.
- **破壊的な操作**:
  - **Scenario**: ファイル削除。
  - **Input**: `intent: FILE_DELETE`
  - **Expected Output**: `status: OK`, `risk_level: HIGH`.
- **未知のコマンド（警告/ソフトブロック）**:
  - **Scenario**: `rm` コマンドの実行（ホワイトリスト外）。
  - **Input**: `intent: CMD_RUN`, `command: rm -rf`
  - **Expected Output**: `status: OK`, `risk_level: HIGH`, `message: "警告: コマンド 'rm' はホワイトリストにありません。..."`

## 3. Consumers
- **planner**: Uses validator to check action safety before planning.
- **action_executor**: Enforces safety checks during execution (conceptually).

## 3. Dependencies
- **Internal**: `action_executor` (ホワイトリスト参照のため)
- **External**: なし

