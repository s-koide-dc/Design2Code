# CodeBuilder Design Document

## 1. Purpose

`CodeBuilder` は JSON ブループリントから C# コードを生成するツール。  
生成したコードを Roslyn で簡易診断し、結果を JSON で返す。

## 2. Structured Specification

### Input
- **Description**: 標準入力の JSON ブループリント。
- **Type/Format**: `Blueprint` JSON
- **Alternate Mode**: `--inspect-source` 指定時は `{"source_code": "...", "method_name": "..."}` を受け取る。
- **Alternate Mode**: `--analyze-source-metrics` 指定時は `{"source_code": "..."}` を受け取る。

### Output
- **Description**: 生成コードと診断結果の JSON。
- **Type/Format**: `{"status":"success","code":...,"diagnostics":[...],"has_errors":bool}`
- **Alternate Mode Output**: `--inspect-source` 指定時は Roslyn 構文木から取得した namespace、class、qualified name、public constructor parameters、target method return type / async flag / parameters を `inspection` として返す。
- **Alternate Mode Output**: `--analyze-source-metrics` 指定時は Roslyn 構文木から class/struct 数、総行数、method/constructor ごとの declaring type、accessibility、行数、try/catch/return 数を `metrics` として返す。

### Core Logic
1. 標準入力から JSON を読み込み `Blueprint` にデシリアライズする。
2. `GenerateCode` でクラス/メソッド/フィールド/追加クラスを生成する。
   - `StatementBlueprint` の `type` に応じて `assign`, `call`, `if`, `foreach`, `try`, `try_catch`, `raw`, `comment`, `retry`, `timeout`, `transaction` を C# 構文へ変換する。
   - `call` は `call_expr` が指定されていれば式全体を Roslyn で parse して使い、null 合体などの複合式を保持する。`call_expr` が無い場合は従来通り `method` と `args` から invocation を構築する。
   - `call` に `out_var` と `is_assignment_only=true` がある場合は既存 local への代入として出力し、再宣言を避ける。
   - `try_catch` は `body` を try block、`catch_body` を `catch (Exception ex)` block として展開する。旧 `try` 型は互換のため `catch_body` が無い場合に `else_body` を catch block として扱う。
   - `rethrow_operation_canceled=true` の `try_catch` は `catch (OperationCanceledException) { throw; }` を通常 catch の前に生成する。
   - `retry` は `for + try/catch + break/rethrow` の決定論的構造へ展開する。
   - explicit delay/backoff metadata があれば、sync は `System.Threading.Thread.Sleep`、async は `await Task.Delay` で展開する。
   - `timeout` は nested `body` を保ったまま、sync は `Task.Run(...).Wait(TimeSpan)`、async は `CancellationTokenSource + WaitAsync` へ展開する。
   - `transaction` は nested `body` を保ったまま、sync は `TransactionScope()`、async は `TransactionScopeAsyncFlowOption.Enabled` 付き `TransactionScope` へ展開する。
3. Roslyn でコードをパースし、エラー診断を収集する。
4. `--inspect-source` 指定時はコード生成を行わず、Roslyn 構文木から対象 public method を持つ class を特定して実行ラッパー生成に必要な構造情報を返す。
5. `--analyze-source-metrics` 指定時はコード生成を行わず、Roslyn 構文木から保守性ゲート用の構造メトリクスを返す。
6. `__CODEBUILDER_JSON_START__/END` で結果 JSON を出力する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 最小の Blueprint 入力。
  - **Expected Output**: `status == "success"` かつ `code` を返す。
- **Edge Cases**:
  - **Scenario**: JSON 解析失敗。
  - **Expected Output / Behavior**: `status == "error"`。
  - **Scenario**: `--inspect-source` で file-scoped namespace / constructor dependency / async method を含むソースを渡す。
  - **Expected Output / Behavior**: namespace、qualified name、constructor parameters、method return type、method parameters が構造化JSONで返る。
  - **Scenario**: `--analyze-source-metrics` で public method、private helper、generic struct constructor を含むソースを渡す。
  - **Expected Output / Behavior**: Roslyn 由来の method/constructor metrics が構造化JSONで返る。

## 3. Dependencies
- **External**: `Microsoft.CodeAnalysis`, `System.Text.Json`

## 4. Review Notes
- 2026-05-11: `retry` statement blueprint を追加し、wrapper semantics を raw text ではなく構造化 statement として codegen できるように更新。さらに explicit delay/backoff metadata を保持して sync/async 両経路へ展開できるようにした。
- 2026-05-13: explicit `timeout` statement blueprint を追加し、nested body を sync/async の timeout guard へ決定論的に展開できるようにした。
- 2026-05-13: explicit `transaction` statement blueprint を追加し、nested body を sync/async の `TransactionScope` へ決定論的に展開できるようにした。
- 2026-07-08: `--inspect-source` mode を追加し、ExecutionVerifier が class / namespace / method signature を文字列分割で推定せず Roslyn 構文木から取得できるようにした。
- 2026-07-10: `try_catch` statement blueprint を追加し、raw try/catch から構造化 codegen へ移行できる入口を用意。
- 2026-07-10: `call_expr`、`is_assignment_only`、`rethrow_operation_canceled` を statement contract として反映し、複合呼び出し式と resilient assignment を保持する。
- 2026-07-13: `--analyze-source-metrics` mode を追加し、生成品質ゲートの保守性指標を Roslyn 構文木から取得できるようにした。
