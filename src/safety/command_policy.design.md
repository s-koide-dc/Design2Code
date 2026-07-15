# CommandPolicyValidator Design Document

## 1. Purpose

CommandPolicyValidator はコマンド文字列を実行前に構造化引数へ変換し、安全ポリシーに従って検証する。
実際のプロセス起動は行わず、ActionExecutor の実行責務と分離する。

## 2. Structured Specification

### Input

- **Description**: コマンド文字列と ActionExecutor が保持するポリシー・パス検証機能。
- **Type/Format**: str

### Output

- **Description**: 検証済み引数配列、または利用者向けの拒否理由。
- **Type/Format**: CommandValidation

### Core Logic

1. shlex.split で引数配列へ変換する。
2. コマンド allowlist と許可サブコマンドを検証する。
3. 禁止オプションと shell metacharacter を拒否する。
4. read/list コマンドではワークスペース内パスと blocked rule を検証する。
5. Python 実行では scripts 配下とスクリプト allowlist を検証する。
6. 検証成功時だけ ActionExecutor が shell=False で実行する。

## 3. Error Handling

検証失敗は CommandValidation.error_message に構造化し、プロセスを起動しない。

## 4. Test Cases

- 許可コマンドが検証成功する。
- 未許可コマンド、サブコマンド、オプションを拒否する。
- shell metacharacter を拒否する。
- ワークスペース外・機密パスを拒否する。
- Python の未許可スクリプトを拒否する。

