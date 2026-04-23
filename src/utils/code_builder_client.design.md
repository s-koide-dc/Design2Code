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
    -   `message`: Error details (if failed).

### 2.3 Core Logic

#### 2.3.1 Blueprint Persistence
1.  **Cache**: Save the blueprint JSON to `cache/blueprint_{timestamp}.json` for debugging and audit purposes.

#### 2.3.2 Execution (`build_code`)
1.  **Command Construction**: Prepare `dotnet run --project tools/csharp/CodeBuilder/CodeBuilder.csproj`.
2.  **Invocation**: Use `subprocess.Popen` to run the command, passing the blueprint JSON via `stdin`.
3.  **Output Handling**: Capture `stdout` and `stderr`.

#### 2.3.3 Response Parsing (`_extract_json_payload`)
1.  **Marker Search**: Look for `__CODEBUILDER_JSON_START__` and `__CODEBUILDER_JSON_END__` markers in `stdout` to isolate the JSON payload from any build logs or console noise.
2.  **Fallback**: If markers are missing, attempt to parse the last non-empty line of output.
3.  **Deserialization**: Parse the extracted string as JSON.

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
