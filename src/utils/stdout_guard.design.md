# stdout_guard Design Document

## 1. Purpose

`stdout_guard` は `stdout` / `stderr` への書き込み失敗で本処理が壊れないように、安全な stream wrapper を挿入する。
あわせて、通常経路では無音を保ちつつ、必要時だけ opt-in で debug 出力を許可する小さな helper を提供する。

## 2. Structured Specification

### Input
- **Description**: 実行中の `sys.stdout` / `sys.stderr`。
- **Type/Format**: Python stream object

### Output
- **Description**: 失敗を握りつぶすラッパーに置き換えられた標準出力/標準エラー。
- **Type/Format**: 副作用

### Core Logic
1. `_SafeStream` は `write`, `flush`, `isatty` を例外安全に委譲する。
2. `write` が失敗した場合は `0` を返し、例外を表に出さない。
3. `flush` と `isatty` も失敗を握りつぶす。
4. `install_stdout_guard` は `sys.stdout` / `sys.stderr` が存在する場合のみ処理する。
5. すでに `_stdout_guard` が付いている stream は二重ラップしない。
6. `is_debug_stdout_enabled` は `NLP_DEBUG_STDOUT` 環境変数を読み、debug 出力を有効化するかどうかを決める。
7. `debug_print` は debug が有効なときだけ安全に `print` し、通常経路では何も出さない。

### Test Cases
- **Happy Path**:
  - **Scenario**: 通常 stream を guard 付きに置き換える。
  - **Expected Output**: `_SafeStream` が設定される。
- **Edge Cases**:
  - **Scenario**: 元 stream の `write` が例外を投げる。
  - **Expected Output / Behavior**: 例外を伝播させず `0` を返す。
  - **Scenario**: `NLP_DEBUG_STDOUT` が未設定。
  - **Expected Output / Behavior**: `debug_print` は何も出さない。

## 3. Dependencies
- **Internal**: なし
- **External**: なし
