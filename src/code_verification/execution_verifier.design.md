# ExecutionVerifier Design Document

## 1. Purpose

`ExecutionVerifier` は生成コードを実行して動作を検証する。  
`CompilationVerifier` を継承し、`dotnet run` による実行結果や例外を取得する。

## 2. Structured Specification

### Input
- **Description**: ソースコード、メソッド名、引数、アサーション目標。
- **Type/Format**: `str`, `List[Any]`

### Output
- **Description**: 実行成功可否と例外情報。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. `run_and_capture` は CodeBuilder の `--inspect-source` モードを呼び、Roslyn 構文木から対象の public method、所属 class、namespace、public constructor、引数、戻り値を取得する。
2. 検査結果に基づいて `Program.cs` ラッパーを生成する。ソース行の文字列分割から class / namespace / method signature を推定しない。
3. 例外はラッパーが出力する `__RUNTIME_JSON__` の構造化JSON診断を優先的に解析する。非構造テキストから例外型を推定しない。
4. `dotnet run` を実行し、標準出力/例外を収集する。
5. `verify_runtime` は `dotnet test` 方式でテストコードを実行する。
6. `run_and_capture` は `has_side_effects=true` のコードを、`allow_side_effects=true` かつ外部サンドボックスを用意した呼び出し以外では実行しない。

### Test Cases
- **Happy Path**:
  - **Scenario**: 実行が成功する。
  - **Expected Output**: `success == true`。
- **Edge Cases**:
  - **Scenario**: 実行時例外が発生。
  - **Expected Output / Behavior**: `exception.type` が返る。
  - **Scenario**: file-scoped namespace、constructor dependency、async `Task<T>` method を含む。
  - **Expected Output / Behavior**: Roslyn 検査結果に基づいて完全修飾名、constructor 引数、method 引数、戻り値が取得される。

## 3. Dependencies
- **Internal**: `tools/csharp/CodeBuilder` の Roslyn 検査モード
- **External**: `subprocess`, `tempfile`, `shutil`, `os`, `json`

## 4. Operational Notes
- 実行検証中に生成するモックファイルの通知は `src.utils.stdout_guard.debug_print` による opt-in 出力とする。
- 通常の検証結果は戻り値の `stdout` / `stderr` / `exception` に集約し、補助通知を標準出力へ常時流さない。
- 2026-05-07: モックファイル生成通知は実行フローの副作用説明に留め、正式な検証結果チャネルには含めない。
