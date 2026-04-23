# code_verification Design Document

## 1. Purpose

`code_verification` は生成コードのコンパイル検証と実行検証を提供する。  
`CompilationVerifier` と `ExecutionVerifier` を入口として、C# のビルド/実行結果を構造化して返す。

## 2. Structured Specification

### Input
- **Description**: C# ソースコード、依存関係、実行対象メソッド。
- **Type/Format**: `str`, `List[Dict[str, str]]`

### Output
- **Description**: 検証結果（成功/失敗、エラー詳細）。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. `CompilationVerifier` がサンドボックスで `dotnet build` を実行し、エラーを構造化する。
2. `ExecutionVerifier` が `Program.cs` を生成し、`dotnet run` で実行結果を取得する。
3. 失敗時は例外情報を抽出して返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 正常なコードがビルドできる。
  - **Expected Output**: `valid == true`。
- **Edge Cases**:
  - **Scenario**: コンパイルエラー。
  - **Expected Output / Behavior**: エラー一覧が返る。

## 3. Dependencies
- **Internal**: `compilation_verifier`, `execution_verifier`
- **External**: `subprocess`, `tempfile`, `os`
