# Statement Builder Design Document

## 1. Purpose
The `StatementBuilder` acts as the "Low-Level Renderer" in the Code Synthesis module [Phase 23.3]. While `ActionSynthesizer` decides *what* logic to generate, `StatementBuilder` decides *how* to format it as valid C# code. It transforms abstract Intermediate Representation (IR) nodes into syntactically correct C# strings, managing indentation, variable naming scopes, control structures, and method call syntax.

## 2. Structured Specification

### 2.1 Inputs
- **statements** (`List[Dict[str, Any]]`): A list of IR statement objects.
- **path** (`Dict[str, Any]`): The current synthesis context, containing indentation level, variable usage tracking (`used_names`), and entity definitions (`poco_defs`).

### 2.2 Output
- **Code Block** (`str`): A multi-line string containing the rendered C# code, properly indented and terminated (semicolons, braces).

### 2.3 Core Logic

#### 2.3.1 Statement Dispatch (`render_statements`)
1.  **Iterate**: Loop through each statement in the input list.
2.  **Dispatch**:
    -   **call**: Invoke `render_method_call`. Add prefix (`var x = `) and suffix (`;`). Handle `await`.
    -   **foreach**: Invoke `render_foreach`. Recursively render body.
    -   **if**: Invoke `render_if`. Recursively render body and else-block.
    -   **try_catch**: Invoke `render_try_catch`. Add robust logging and fallback return logic.
    -   **raw**: Append raw string code directly (handling indentation).
    -   **comment**: formatting as `// text`.

#### 2.3.2 Method Call Rendering (`render_method_call`)
1.  **Receiver Resolution**:
    -   Map classes to dependency fields (e.g., `System.Net.Http.HttpClient` -> `_httpClient`).
    -   Handle extension methods (first argument becomes receiver).
    -   Handle static calls (`File.Read...`) vs. instance calls.
2.  **Async/Await Handling**:
    -   Detect if method is async (via metadata or naming convention "Async").
    -   Update `path["has_async_io"]`.
3.  **Generic Type Handling**:
    -   Resolve `<T>` placeholders to concrete types (e.g., `List<User>`).
4.  **Argument Formatting**:
    -   Join arguments with commas. Ensure literals are quoted/escaped (handled by upstream binder, but double-check).

#### 2.3.3 Control Structure Rendering
1.  **Indentation**: Manage `path["indent_level"]`. Increment before entering blocks, decrement after.
2.  **Foreach**: Generate `foreach (var {item} in {source}) { ... }`. Register loop variable in `path`.
3.  **If/Else**: Generate `if ({condition}) { ... } else { ... }`.
4.  **Resilient Try/Catch**:
    - `DATABASE_QUERY` / `HTTP_REQUEST` / `FILE_IO` / `FETCH` / `PERSIST` / `JSON_DESERIALIZE` は resilient intent として `try/catch` で包む。
    - `OperationCanceledException` は通常例外として握りつぶさず再throwする。
    - `error_policy=continue` は catch 後に return せず継続、`error_policy=rethrow` は catch 内で `throw;`、既定の `return_default` は戻り値型に応じた安全な既定値を返す。
    - `Task<T>` 戻り値は内部の `T` を有効戻り値型として扱い、hoisted result の型と一致する場合は catch から hoisted result を返す。

#### 2.3.4 Variable Name Generation (`get_semantic_var_name`)
1.  **Base Name**: Derive from entity name (e.g., "User" -> "user") or usage hint.
2.  **Collision Avoidance**: Check `path["used_names"]`. If `user` exists, try `user1`, `user2`.
3.  **Reserved Keywords**: Avoid C# keywords (`class`, `int`, etc.) by fallback to "result" or appending numbers.
4.  **Registration**: Add final name to `used_names` and `name_to_role`.

#### 2.3.5 Entity & POCO Management
1.  **Registration**: `register_entity` looks up schema/memory for properties and adds them to `path["poco_defs"]`.
2.  **Display**: `build_poco_display_expression` generates an interpolated string showing all properties (e.g., `$"User {{ Name={Name}, Age={Age} }}"`).

### 2.4 Test Cases

#### Happy Path
1.  **Render Method Call**:
    -   Input: `type="call"`, `method="Console.WriteLine"`, `args=["Hello"]`
    -   Result: `Console.WriteLine("Hello");`
2.  **Render Async Assignment**:
    -   Input: `type="call"`, `out_var="data"`, `is_async=True`, `method="api.GetData"`
    -   Result: `var data = await api.GetData();`
3.  **Render Foreach**:
    -   Input: `type="foreach"`, `source="items"`, `item_name="item"`, `body=[call...]`
    -   Result:
        ```csharp
        foreach (var item in items)
        {
            // body code
        }
        ```

#### Edge Cases
1.  **Variable Collision**:
    -   Context: `used_names={"user"}`
    -   Request: Generate name for "User"
    -   Result: `user1`
2.  **Try/Catch Wrapping**:
    -   Input: `intent="DATABASE_QUERY"`, return `int`
    -   Result:
        ```csharp
        try { ... }
        catch (OperationCanceledException) { throw; }
        catch (Exception ex) { _logger.LogError(...); return 0; }
        ```
    -   Reference-type result variables that are hoisted before the `try` block use nullable declarations when initialized from `null` (for example `HttpResponseMessage? response = null;`) so nullable-enabled compilation does not emit avoidable warnings.
    -   戻り値変数をhoistした呼び出しはcatch後も継続し、後から確定するメソッド戻り値に依存した不正な `return;` を生成しない。
    -   配列のhoisted既定値は `Array.Empty<T>()` とし、後続のLINQ処理でnullを参照しない。
    -   `error_policy` が `continue` / `rethrow` の場合はそれぞれ継続 / 再throw の契約を優先し、戻り値既定値の生成で上書きしない。
3.  **Complex Generic**:
    -   Input: `method="Query<T>"`, `target="User"`
    -   Result: `conn.Query<User>(...)`

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.
- 2026-06-04: resilient intent の判定語彙を `src.utils.semantic_intents` の共通定数へ寄せた。
- 2026-06-24: resilient wrap の hoisted reference-type locals は nullable declaration (`Type? x = null;`) を使い、nullable-enabled verifier で `CS8600` を出さない現在の方針へ同期。
- 2026-06-29: 戻り値変数を持つresilient callの継続契約と、配列の空配列初期化を反映。
- 2026-07-08: resilient try/catch の `error_policy`、`OperationCanceledException` 再throw、`Task<T>` 戻り値の有効型判定、catch から hoisted result を返す契約を反映。

