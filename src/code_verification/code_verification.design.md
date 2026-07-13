# code_verification Design Document
<!-- metadata-sync: 2026-07-09T00:00:00+09:00 -->

## 1. Purpose

`code_verification` は生成コードのコンパイル検証、実行検証、生成品質ゲートを提供する。
`CompilationVerifier`、`ExecutionVerifier`、`generation_quality` を入口として、C# のビルド/実行結果と品質判定を構造化して返す。

## 2. Structured Specification

### Input
- **Description**: C# ソースコード、依存関係、実行対象メソッド。
- **Type/Format**: `str`, `List[Dict[str, str]]`

### Output
- **Description**: 検証結果（成功/失敗、エラー詳細、警告詳細、品質 issue）。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. `CompilationVerifier` がサンドボックスで `dotnet build` を実行し、エラーと警告を構造化する。
2. `ExecutionVerifier` が `Program.cs` を生成し、`dotnet run` で実行結果を取得する。
3. `generation_quality` が compiler warning、spec audit issue、unresolved marker、blueprint placeholder fetch を品質ゲートとして評価する。
4. `generation_quality` は maintainability 観測値と finding も返す。これは operation method 行数、try 数、catch 数などの傾向把握用で、既定では品質 NG 条件ではない。
   - `fail_on_maintainability=True` の場合だけ finding を品質 NG に昇格する。
5. 失敗時は例外情報または品質 issue を抽出して返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 正常なコードがビルドできる。
  - **Expected Output**: `valid == true`。
- **Edge Cases**:
  - **Scenario**: コンパイルエラー。
  - **Expected Output / Behavior**: エラー一覧が返る。
  - **Scenario**: コンパイルは成功するが nullable warning が出る。
  - **Expected Output / Behavior**: `CompilationVerifier.warnings` に diagnostic が入り、品質ゲートでは失敗扱いにできる。

## 3. Dependencies
- **Internal**: `compilation_verifier`, `execution_verifier`, `generation_quality`, `semantic_assertions`
- **External**: `subprocess`, `tempfile`, `os`
