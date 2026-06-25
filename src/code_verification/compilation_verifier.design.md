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
   - `Sandbox.csproj` では `<Nullable>enable</Nullable>` を有効にし、生成コードが `string?` などの nullable 参照型注釈を含んでも余計な `CS8632` 警告を出さない。
3. 依存関係をマージし、必要に応じて `dotnet restore` を実行する。
4. `dotnet build` を実行し、`_parse_errors` でエラーを構造化する。
5. `verify_project` は指定プロジェクトの `.csproj` をビルドして結果を返す。

## 4. Review Notes
- 2026-06-24: sandbox project に nullable context を明示し、nullable return type を含む生成コードで `CS8632` 警告を出さない現在の検証前提へ同期。

### Test Cases
- **Happy Path**:
  - **Scenario**: 正常なソースを検証。
  - **Expected Output**: `valid == true`。
- **Edge Cases**:
  - **Scenario**: 不正な型参照。
  - **Expected Output / Behavior**: `errors` に `SYMBOL_NOT_FOUND` が含まれる。

## 3. Dependencies
- **External**: `subprocess`, `tempfile`, `shutil`, `os`, `re`
