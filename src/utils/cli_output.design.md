# cli_output Design Document

## 1. Purpose

`cli_output` は CLI の正式 stdout/stderr 出力を小さく統一する補助モジュールである。  
利用者向けの正式結果と異常系診断を分離し、各 CLI が個別に `print(..., file=sys.stderr)` の判断をばらまかないようにする。

## 2. Structured Specification

### Input
- **Description**: 出力する文字列または JSON 化可能なオブジェクト。
- **Type/Format**: `str | Any`
- **Example**:
  ```python
  {"status": "success", "message": "ok"}
  ```

### Output
- **Description**: CLI 標準出力または標準エラー出力への書き込み。
- **Type/Format**: `None`
- **Example**:
  ```text
  {
    "status": "success",
    "message": "ok"
  }
  ```

### Core Logic
1. import 時に `install_stdout_guard()` を呼び、安全な stdout/stderr ラッパーを有効化する。
2. `emit_stdout` は受け取った文字列を標準出力へ出す。
3. `emit_stderr` は受け取った文字列を標準エラー出力へ出す。
4. `emit_progress` は進行表示を stdout へ出す。
5. `emit_error` は利用者向けエラー文言を stderr へ出す。
6. `emit_json_stdout` は payload を `ensure_ascii=False, indent=2` で JSON 文字列化し、正式 stdout として出力する。

### Test Cases
- **Happy Path**:
  - **Scenario**: JSON payload を stdout に出す。
  - **Expected Output / Behavior**: UTF-8 相当の日本語を保持した整形 JSON が出る。
- **Edge Cases**:
  - **Scenario**: stderr に異常系メッセージを出す。
  - **Expected Output / Behavior**: stdout と混在しない。

## 3. Dependencies
- **Internal**: `src.utils.stdout_guard`
- **External**: `json`, `sys`

## 4. Operational Notes
- CLI の正式結果は stdout、異常系の補助診断は stderr に分ける。
- より複雑な進行表示や debug 出力はこのモジュールで扱わない。
