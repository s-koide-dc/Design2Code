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
1. ソースからクラス名と名前空間を抽出し、`Program.cs` ラッパーを生成する。
2. 例外は `[RUNTIME_ERROR]` と `[ASSERTION_FAILURE]` を優先的に解析する。
3. `dotnet run` を実行し、標準出力/例外を収集する。
4. `verify_runtime` は `dotnet test` 方式でテストコードを実行する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 実行が成功する。
  - **Expected Output**: `success == true`。
- **Edge Cases**:
  - **Scenario**: 実行時例外が発生。
  - **Expected Output / Behavior**: `exception.type` が返る。

## 3. Dependencies
- **External**: `subprocess`, `tempfile`, `shutil`, `os`, `re`
