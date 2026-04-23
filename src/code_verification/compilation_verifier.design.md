# CompilationVerifier Design Document

## 1. Purpose

`CompilationVerifier` は生成された C# コードのビルド可否を検証する。  
サンドボックスにプロジェクトを作成し、`dotnet build` の結果を解析する。

## 2. Structured Specification

### Input
- **Description**: C# ソースコードと依存関係。
- **Type/Format**: `str`, `List[Dict[str, str]]`

### Output
- **Description**: コンパイル成功可否とエラー情報。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. ベースサンドボックス（`cache/base_sandbox`）を準備し、依存関係が変わらなければ `obj` と `Sandbox.csproj` を再利用する。
2. サンドボックスを用意し、`Sandbox.csproj` と `GeneratedCode.cs` を作成する。
3. 依存関係をマージし、必要に応じて `dotnet restore` を実行する。
4. `dotnet build` を実行し、`_parse_errors` でエラーを構造化する。
5. `verify_project` は指定プロジェクトの `.csproj` をビルドして結果を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 正常なソースを検証。
  - **Expected Output**: `valid == true`。
- **Edge Cases**:
  - **Scenario**: 不正な型参照。
  - **Expected Output / Behavior**: `errors` に `SYMBOL_NOT_FOUND` が含まれる。

## 3. Dependencies
- **External**: `subprocess`, `tempfile`, `shutil`, `os`, `re`
