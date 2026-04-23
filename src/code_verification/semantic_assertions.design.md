# Semantic Assertions Design Document

## 1. Purpose
The `SemanticAssertions` module [Phase 23.4] provides a rule-based verification engine to ensure that the synthesized code meets specific semantic contracts. Unlike the compiler (which checks syntax) or the `SpecAuditor` (which checks coverage), this module verifies *how* the code behaves—for example, ensuring that a variable returned by `GetUsers()` is actually used later, or that `Console.WriteLine` displays a specific property.

## 2. Structured Specification

### 2.1 Inputs
- **blueprint** (`Dict[str, Any]`): The synthesized code structure (methods, body, statements).
- **contract** (`Dict[str, Any]`): A dictionary defining the verification rules (e.g., `require_call_methods`, `disallow_placeholder_fetch`).

### 2.2 Output
- **Issues** (`List[str]`): A list of violation messages.
- **Exception**: `SemanticAssertionError` is raised by the wrapper if issues exist.

### 2.3 Core Logic

#### 2.3.1 Pre-processing (`flatten_statements`)
-   Recursively traverses the statement tree (handling `if`, `foreach`, `while`, `try`) to produce a flat list of all statements for easier analysis.

#### 2.3.2 Contract Validation (`evaluate_blueprint_contract`)
1.  **Placeholder Check** (`disallow_placeholder_fetch`):
    -   Scans for method calls to `Enumerable.Empty`. If found, reports error.
2.  **Required Calls** (`require_call_methods`):
    -   List of method suffixes (e.g., "Save").
    -   Verifies that at least one statement calls a method matching the suffix.
3.  **Display Property** (`require_display_property`):
    -   Verifies that `Console.WriteLine` arguments include a specific property access (e.g., `.Id`).
4.  **Variable Usage** (`require_var_usage_from_methods`):
    -   Ensures data flow connectivity.
    -   Identifies the output variable of a source method (e.g., `var data = GetData()`).
    -   Scans subsequent statements to ensure `data` is used (referenced).

### 2.4 Test Cases

#### Happy Path
1.  **Valid Data Flow**:
    -   Contract: `require_var_usage_from_methods=["GetData"]`.
    -   Code: `var data = api.GetData(); Console.WriteLine(data);`
    -   Result: `[]`.
2.  **Required Call**:
    -   Contract: `require_call_methods=["Save"]`.
    -   Code: `repo.Save(item);`
    -   Result: `[]`.

#### Edge Cases
1.  **Unused Variable**:
    -   Code: `var data = api.GetData();` (End of method).
    -   Result: `["output variable from GetData is not consumed"]`.
2.  **Placeholder Detected**:
    -   Code: `var items = Enumerable.Empty<T>();`
    -   Contract: `disallow_placeholder_fetch=True`.
    -   Result: `["placeholder fetch (Enumerable.Empty) is used"]`.
3.  **Missing Display Prop**:
    -   Code: `Console.WriteLine("Done");`
    -   Contract: `require_display_property="Id"`.
    -   Result: `["displayed value does not include property: Id"]`.
