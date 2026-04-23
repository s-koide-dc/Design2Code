# Blueprint Assembler Design Document

## 1. Purpose
The `BlueprintAssembler` acts as the final assembly stage [Phase 23.2] in the Code Synthesis pipeline. Its role is to consolidate all intermediate synthesis artifacts—statements, type definitions, variable scopes, and resource requirements—into a cohesive, high-fidelity "Blueprint." This blueprint serves as the definitive specification for the `CodeBuilder` to generate the final compilable C# source code.

## 2. Structured Specification

### 2.1 Inputs
- **method_name** (`str`): The name of the primary method to be generated.
- **path** (`Dict[str, Any]`): The final synthesis state containing sequences of statements, variable mappings, and POCO definitions.
- **inputs** (`List[Dict[str, Any]]`, optional): Definitions of input parameters (name, type).
- **ir_tree** (`Dict[str, Any]`, optional): The original Intermediate Representation tree, used for cross-referencing data sources.

### 2.2 Output
- **Blueprint** (`Dict[str, Any]`): A structured dictionary containing:
    - `namespace`: The target namespace (default: "Generated").
    - `class_name`: The target class name (default: "GeneratedProcessor").
    - `usings`: List of required `using` directives.
    - `fields`: List of dependency-injected fields (e.g., `_httpClient`, `_dbConnection`).
    - `methods`: List of method definitions (only one primary method currently).
    - `extra_classes`: List of POCO class definitions.

### 2.3 Core Logic

#### 2.3.1 Namespace & Import Management
1.  **Defaults**: Always include core namespaces: `System`, `System.IO`, `System.Linq`, `System.Collections.Generic`, `System.Threading.Tasks`, `System.Text.Json`.
2.  **Contextual Additions**:
    -   Add `System.Data` if `IDbConnection` or `Dapper` is used.
    -   Add `System.Net.Http` if `HttpClient` is used.
    -   Add `Microsoft.Extensions.Logging` if logging is active.

#### 2.3.2 Async/Await Detection
1.  **Flag Check**: Check `path.get("is_async_needed")`.
2.  **Code Scan**: Iterate through all statements. If any statement contains the substring `await `, force `is_async = True`.
3.  **Return Type Adjustment**: If async, wrap the return type in `Task<T>` (or `Task` if void).

#### 2.3.3 Method Signature Construction
1.  **Parameters**: Map `inputs` to method parameters.
2.  **Guard Clauses**: For each reference-type parameter, inject a null-check statement at the beginning of the body: `if (param == null) throw new ArgumentNullException(nameof(param));`.

#### 2.3.4 Body Assembly
1.  **Hoisted Statements**: Prepend any statements marked as "hoisted" (e.g., accumulator variable declarations) to the top of the body.
2.  **Main Statements**: Append the sequence of statements from `path["statements"]`.
3.  **Return Statement**:
    -   Check if the last statement is a `return`.
    -   If not, and the method is non-void, attempt to find a variable matching the return type in `type_to_vars`.
    -   If found, return that variable.
    -   Otherwise, return a default value (`0`, `false`, `null`) to ensure compilation.

#### 2.3.5 Dependency Injection (DI) Resolution
1.  **Resource Audit**: Check `ir_tree` for data sources (DB, HTTP) and add corresponding fields (`_dbConnection`, `_httpClient`).
2.  **Usage Scan**: Recursively scan the final statement body for references to known DI fields.
3.  **Field Definition**: Add identified fields to the blueprint's `fields` list, excluding static classes (e.g., `Console`, `File`).

#### 2.3.6 POCO Generation
1.  **Iteration**: Process `path["poco_defs"]`.
2.  **Naming Convention**: Convert property names to PascalCase.
3.  **Attributes**: If the PascalCase name differs from the original (e.g., snake_case json source), add `[JsonPropertyName("original_name")]`.
4.  **Class Definition**: Add to `extra_classes`.

### 2.4 Test Cases

#### Happy Path
1.  **Simple Sync Method**:
    -   Input: `inputs=[{"name": "id", "type": "int"}]`, `statements=[{"code": "return id * 2;"}]`
    -   Result: Method `int Method(int id)` with body `return id * 2;`.
2.  **Async Method with DI**:
    -   Input: `statements=[{"code": "await _httpClient.GetAsync(...);"}]`
    -   Result: Method `async Task Method(...)`, Field `HttpClient _httpClient`.
3.  **POCO Generation**:
    -   Input: `poco_defs={"User": {"user_id": "int"}}`
    -   Result: Class `User` with property `UserId` and attribute `[JsonPropertyName("user_id")]`.

#### Edge Cases
1.  **Missing Return**:
    -   Input: Return type `int`, body has no return.
    -   Result: Inject `return 0;` at the end.
2.  **Unused DI Field**:
    -   Input: `ir_tree` has DB source, but code doesn't use `_dbConnection`.
    -   Result: Field is still added (based on resource audit) to allow potential future use or manual fix.
3.  **Static Class Confusion**:
    -   Input: Code uses `File.WriteAllText`.
    -   Result: `File` is NOT added as a DI field.

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.

