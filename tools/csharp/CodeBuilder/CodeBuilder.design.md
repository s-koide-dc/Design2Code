# CodeBuilder Design Document

## 1. Purpose

`CodeBuilder` は JSON ブループリントから C# コードを生成するツール。  
生成したコードを Roslyn で簡易診断し、結果を JSON で返す。

## 2. Structured Specification

### Input
- **Description**: 標準入力の JSON ブループリント。
- **Type/Format**: `Blueprint` JSON
- **Alternate Mode**: `--inspect-source` 指定時は `{"source_code": "...", "method_name": "..."}` を受け取る。

### Output
- **Description**: 生成コードと診断結果の JSON。
- **Type/Format**: `{"status":"success","code":...,"diagnostics":[...],"has_errors":bool}`
- **Alternate Mode Output**: `--inspect-source` 指定時は Roslyn 構文木から取得した namespace、class、qualified name、public constructor parameters、target method return type / async flag / parameters を `inspection` として返す。

### Core Logic
1. 標準入力から JSON を読み込み `Blueprint` にデシリアライズする。
2. `GenerateCode` でクラス/メソッド/フィールド/追加クラスを生成する。
   - `StatementBlueprint` の `type` に応じて `assign`, `call`, `if`, `foreach`, `try`, `raw`, `comment`, `retry`, `timeout`, `transaction` を C# 構文へ変換する。
   - `retry` は `for + try/catch + break/rethrow` の決定論的構造へ展開する。
   - explicit delay/backoff metadata があれば、sync は `System.Threading.Thread.Sleep`、async は `await Task.Delay` で展開する。
   - `timeout` は nested `body` を保ったまま、sync は `Task.Run(...).Wait(TimeSpan)`、async は `CancellationTokenSource + WaitAsync` へ展開する。
   - `transaction` は nested `body` を保ったまま、sync は `TransactionScope()`、async は `TransactionScopeAsyncFlowOption.Enabled` 付き `TransactionScope` へ展開する。
3. Roslyn でコードをパースし、エラー診断を収集する。
4. `--inspect-source` 指定時はコード生成を行わず、Roslyn 構文木から対象 public method を持つ class を特定して実行ラッパー生成に必要な構造情報を返す。
5. `__CODEBUILDER_JSON_START__/END` で結果 JSON を出力する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 最小の Blueprint 入力。
  - **Expected Output**: `status == "success"` かつ `code` を返す。
- **Edge Cases**:
  - **Scenario**: JSON 解析失敗。
  - **Expected Output / Behavior**: `status == "error"`。
  - **Scenario**: `--inspect-source` で file-scoped namespace / constructor dependency / async method を含むソースを渡す。
  - **Expected Output / Behavior**: namespace、qualified name、constructor parameters、method return type、method parameters が構造化JSONで返る。

## 3. Dependencies
- **External**: `Microsoft.CodeAnalysis`, `System.Text.Json`

## 4. Review Notes
- 2026-05-11: `retry` statement blueprint を追加し、wrapper semantics を raw text ではなく構造化 statement として codegen できるように更新。さらに explicit delay/backoff metadata を保持して sync/async 両経路へ展開できるようにした。
- 2026-05-13: explicit `timeout` statement blueprint を追加し、nested body を sync/async の timeout guard へ決定論的に展開できるようにした。
- 2026-05-13: explicit `transaction` statement blueprint を追加し、nested body を sync/async の `TransactionScope` へ決定論的に展開できるようにした。
- 2026-07-08: `--inspect-source` mode を追加し、ExecutionVerifier が class / namespace / method signature を文字列分割で推定せず Roslyn 構文木から取得できるようにした。
