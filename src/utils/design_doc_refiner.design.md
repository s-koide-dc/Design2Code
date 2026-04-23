# Design Doc Refiner Design Document

## 1. Purpose
The `DesignDocRefiner` [Phase 23.4] ensures that design documentation remains the "Single Source of Truth" by actively synchronizing it with the implementation. When code evolves (e.g., signature changes, new methods), this utility analyzes the source code (via AST) and updates the `.design.md` file's Input/Output definitions and logic descriptions, preventing documentation drift.

## 2. Structured Specification

### 2.1 Inputs
- **design_path** (`str`): Path to the target `.design.md` file.
- **source_path** (`str`): Path to the corresponding source code file.

### 2.2 Output
- **Result** (`Dict[str, Any]`):
    -   `status`: "success", "no_change", or "error".
    -   `message`: Description of the outcome.
    -   `audit_score`: Consistency score from `LogicAuditor`.
    -   `findings`: List of remaining issues.

### 2.3 Core Logic

#### 2.3.1 Analysis & Audit (`sync_from_code`)
1.  **File Loading**: Read content of both files. Return error if missing.
2.  **AST Analysis**: Use `ASTAnalyzer` to extract class/method structure, parameters, and return types from the source code.
3.  **Parsing**: Use `DesignDocParser` to understand the current state of the design doc.
4.  **Audit**: Use `LogicAuditor` to check current consistency before modification.

#### 2.3.2 Interface Synchronization (`_sync_interface`)
1.  **Target Identification**: Find the primary class/method in the source structure (First class's first method, or first function).
2.  **Parameter Extraction**: format parameters as a comma-separated string (e.g., `arg1, arg2`).
3.  **Return Type Extraction**: Identify return type annotation.
4.  **Regex Replacement**:
    -   Locate `### Input` section and update `**Description**`.
    -   Locate `### Output` section and update `**Description**`.

#### 2.3.3 Logic Refinement (`_refine_logic_placeholders`)
1.  **Placeholder Search**: Look for specific "TODO" patterns (e.g., `(ロジックの詳細をここに記述してください...)`).
2.  **Method Listing**: Collect method names from the source AST.
3.  **Generation**: Create a numbered list of method calls (e.g., "1. Call `calculate_total`...").
4.  **Replacement**: Overwrite the placeholder with the generated list.

### 2.4 Test Cases

#### Happy Path
1.  **Sync Interface**:
    -   Source: `def func(a: int, b: str) -> bool:`
    -   Design: `Input: ...`
    -   Result: Design updated to "Input: `a, b`..." and "Output: `bool`...".
2.  **Fill Logic**:
    -   Source: `class A: def method1(): pass`
    -   Design: contains logic placeholder.
    -   Result: Design logic replaced with "1. Call `method1`...".

#### Edge Cases
1.  **Files Missing**:
    -   Input: Invalid paths.
    -   Result: Error status.
2.  **No Structure**:
    -   Source: Empty file.
    -   Result: No changes made.
3.  **Already Synced**:
    -   Input: Perfectly matching files.
    -   Result: "no_change" status.
