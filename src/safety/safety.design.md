# safety Design Document

## 1. Purpose

`safety` はプラン段階の安全性評価を行い、危険な操作を事前に抑止する。

## 2. Structured Specification

### Input
- **Description**: アクションメソッド、パラメータ、intent。
- **Type/Format**: `str`, `Dict[str, Any]`, `str | None`
- **Example**: `("_run_command", {"command":"dotnet test"}, "CMD_RUN")`

### Output
- **Description**: 安全性評価結果。
- **Type/Format**: `SafetyCheckResult`
- **Example**: `{"status":"OK","message":"Safety Check OK","risk_level":"LOW"}`

### Core Logic
1. `SafetyPolicyValidator` がポリシー（`config`/`resources`）を読み込み、危険/注意 intent を初期化する。
2. `CMD_RUN` は `safe_commands` に含まれるコマンドのみ許可し、メタ文字が含まれる場合はブロックする。
3. intent が破壊的または注意対象に該当する場合、リスクレベルを引き上げる。

### Test Cases
- **Happy Path**:
  - **Scenario**: 安全な `CMD_RUN`。
  - **Expected Output**: `status=OK`, `risk_level=LOW`。
- **Edge Cases**:
  - **Scenario**: 未許可コマンド。
  - **Expected Output / Behavior**: `status=BLOCK`, `risk_level=HIGH`。

## 3. Dependencies
- **Internal**: `safety_policy_validator`, `action_executor`, `config_manager`
- **External**: `json`, `os`
