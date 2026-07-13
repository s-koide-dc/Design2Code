# Code Builder Client Design Document

## 1. Purpose
The `CodeBuilderClient` [Phase 23.3] serves as the inter-process communication bridge between the Python synthesis engine and the C# `CodeBuilder` tool. It is responsible for serializing the language-agnostic `Blueprint` into JSON, invoking the external .NET application, and retrieving the generated C# source code.

## 2. Structured Specification

### 2.1 Inputs
- **config**: Application configuration (for workspace root).
- **blueprint** (`Dict[str, Any]`): The code specification to be rendered.

### 2.2 Output
- **Result** (`Dict[str, Any]`):
    -   `status`: "success" or "error".
    -   `code`: The generated C# source code string (if successful).
    -   `metrics`: Roslyn-derived C# source metrics when `analyze_source_metrics` is used.
    -   `message`: Error details (if failed).

### 2.3 Core Logic

#### 2.3.1 Blueprint Persistence
1.  **Cache**: Save the blueprint JSON to `cache/blueprint_{timestamp}.json` for debugging and audit purposes.

#### 2.3.2 Execution (`build_code`)
1.  **Executable Resolution**: If built executables exist, choose the freshest Debug/Release configuration by looking at both `CodeBuilder.exe` and its paired `CodeBuilder.dll`, so apphost lock skew does not cause stale binary drift; otherwise fall back to `dotnet run --project tools/csharp/CodeBuilder/CodeBuilder.csproj`.
2.  **Invocation**: Use `subprocess.Popen` to run the command, passing the blueprint JSON via `stdin`.
3.  **Output Handling**: Capture `stdout` and `stderr`.

#### 2.3.3 Response Parsing (`_extract_json_payload`)
1.  **Marker Search**: Look for `__CODEBUILDER_JSON_START__` and `__CODEBUILDER_JSON_END__` markers in `stdout` to isolate the JSON payload from any build logs or console noise.
2.  **Fallback**: If markers are missing, attempt to parse the last non-empty line of output.
3.  **Deserialization**: Parse the extracted string as JSON.
4.  **Failure Logging**: Non-JSON output is treated as an internal error and recorded via logger output, not unconditional stdout printing.

#### 2.3.4 Source Metrics (`analyze_source_metrics`)
1.  **Invocation**: Call CodeBuilder with `--analyze-source-metrics` and pass `{"source_code": ...}` via stdin.
2.  **Structural Analysis**: The .NET side uses Roslyn syntax nodes to return class/struct counts and method/constructor metrics.
3.  **Consumer Contract**: `generation_quality` uses these metrics as the preferred maintainability source for generated code review and regression.

#### 2.3.5 Fallback Rendering (`_render_fallback_code`)
1.  **Purpose**: When the external `CodeBuilder` project is unavailable, render a minimal but structurally faithful C# fallback for tests.
2.  **Statement Support**: Handle nested `call`, `assign`, `comment`, `foreach`, `if`, `try`, `try_catch`, `retry`, `timeout`, and `transaction` statements.
    - `call_expr` がある `call` は式全体を使い、`method`/`args` からの再構成で null 合体や複合式を落とさない。
    - `call` に `out_var` がある場合は `var_type out_var = call(...)`、`is_assignment_only` の場合は `out_var = call(...)` として戻り値を保持する。
    - `is_async` のcallは代入式の右辺に `await` を付与する。
    - `try_catch` は `body` を try block、`catch_body` を `catch (Exception ex)` block として保持する。旧 `try` 型は互換のため `catch_body` がなければ `else_body` を catch block として扱う。
    - `rethrow_operation_canceled` が true の場合は通常 catch の前に `catch (OperationCanceledException) { throw; }` を出力する。
3.  **Retry Semantics**: Render `retry` as deterministic `for + try/catch + break/rethrow`, matching the C# `CodeBuilder` statement contract instead of flattening wrapper bodies or injecting ad hoc raw code.
4.  **Delay/Backoff Policy**: When explicit retry metadata includes `base_delay_ms`, `max_delay_ms`, or `backoff_multiplier`, preserve it in fallback rendering rather than inferring it from text.
5.  **Timeout Semantics**: Render explicit `timeout` wrappers as sync `Task.Run(...).Wait(TimeSpan)` or async `CancellationTokenSource + WaitAsync`, preserving nested body structure and explicit `timeout_ms`.
6.  **Transaction Semantics**: Render explicit `transaction` wrappers as sync `TransactionScope()` or async `TransactionScopeAsyncFlowOption.Enabled`, preserving nested body structure and wrapper-kind semantics.

### 2.4 Test Cases

#### Happy Path
1.  **Successful Generation**:
    -   Input: Valid blueprint.
    -   Mock Output: `__CODEBUILDER_JSON_START__{"code": "public class A {}"}__CODEBUILDER_JSON_END__`
    -   Result: `{"code": "public class A {}"}`.

#### Edge Cases
1.  **Build Failure**:
    -   Process exits with non-zero code.
    -   Result: `{"status": "error", "message": stderr_content}`.
2.  **Garbage Output**:
    -   Stdout contains no JSON or markers.
    -   Result: `{"status": "error", "message": "Non-JSON output..."}`.
3.  **Blueprint Save Fail**:
    -   Disk write fails.
    -   Result: Log error but proceed with execution (memory-only).
4.  **Source Metrics**:
    -   Input: C# source with public method, private helper, and struct constructor.
    -   Result: `metrics.members` contains method/constructor entries with declaring type, accessibility, and try/catch counts.

## 3. Review Notes
- 2026-06-29: fallback call rendererの戻り値代入とasync代入契約を反映。
- 2026-07-10: `try` / `try_catch` statement validation and fallback rendering を追加し、C# CodeBuilder の構造化 try/catch contract と同期。
- 2026-07-10: fallback call renderer が `call_expr`、`is_assignment_only`、`rethrow_operation_canceled` を保持する契約を明記。
- 2026-07-13: `analyze_source_metrics` を追加し、生成品質ゲートが Roslyn ベースの保守性メトリクスを使えるようにした。
