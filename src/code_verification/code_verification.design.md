# code_verification Design Document
<!-- metadata-sync: 2026-07-09T00:00:00+09:00 -->

## 1. Purpose

`code_verification` は生成コードのコンパイル検証、実行検証、生成品質ゲート、明示 runtime oracle の集計と実行を提供する。
`CompilationVerifier`、`ExecutionVerifier`、`generation_quality`、`runtime_oracle` を入口として、C# のビルド/実行結果、品質判定、意味検証契約の有無と実行結果を構造化して返す。
`runtime_oracle` は互換 facade とし、契約正規化は `runtime_oracle_contract`、xUnit 生成は `runtime_oracle_test_builder`、実行と依存追加は `runtime_oracle_executor` に分離する。

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
5. `runtime_oracle` が StructuredSpec の Test Cases から JSON 形式の明示 oracle を抽出し、自然文 expected は推測せず `unverified` として可視化する。
6. 明示 oracle 実行が要求された場合は、file fixture、environment fixture、HTTP response fixture、SQLite schema/seed、method args、async await、return、stdout、file assertions、HTTP method/url/header/body assertions、DB scalar assertions を xUnit test code に変換し、`ExecutionVerifier` で生成コードを実行する。
7. 失敗時は例外情報、品質 issue、または oracle 実行失敗を抽出して返す。
8. 依存パッケージは `dependency_contract` で検証してから `.csproj` に出力する。副作用を持つ生成コードの `run_and_capture` は外部サンドボックスの明示許可がない限り拒否する。

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
- **Internal**: `compilation_verifier`, `execution_verifier`, `generation_quality`, `runtime_oracle`, `runtime_oracle_contract`, `runtime_oracle_test_builder`, `runtime_oracle_executor`, `semantic_assertions`
- **External**: `subprocess`, `tempfile`, `os`
