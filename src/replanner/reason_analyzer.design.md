# Reason Analyzer Design Document

## 1. Purpose
The `ReasonAnalyzer` [Phase 23.4] is the diagnostic engine of the self-correction loop. It examines the results of code synthesis and verification (including compilation errors and semantic violations) to determine *why* a failure occurred. It then translates these root causes into actionable "hints" that the `Replanner` and `IRPatcher` can use to modify the intermediate representation (IR) and repair the code.

## 2. Structured Specification

### 2.1 Inputs
- **synthesis_result** (`Dict[str, Any]`): The output of the synthesis phase, including generated code and trace/blueprint.
- **verification_result** (`Dict[str, Any]`): Results from the compiler or build system (success/failure, error list).
- **semantic_issues** (`List[str]`): A list of semantic violations detected by the `CodeVerification` module (e.g., "Missing side-effect").

### 2.2 Output
- **Hints** (`List[Dict[str, Any]]`): A list of diagnostic objects, each containing:
    -   `reason`: Error category code.
    -   `detail`: Human-readable description.
    -   `patch`: A structured instruction for `IRPatcher` (type + parameters).

### 2.3 Core Logic

#### 2.3.1 Compilation Error Analysis (`_analyze_compilation_error`)
1.  **Parse Error**: Extract error code (e.g., "CS0103") and message.
2.  **Locate Node**: Map line numbers back to Node IDs using `// Node: ID` comments in the source code.
3.  **Heuristic Mapping**:
    -   **CS0103** (Name doesn't exist): `ENSURE_FIELD_OR_LOCAL` (Inject field/variable).
    -   **CS1061** (Type missing member): `ADD_POCO_PROPERTY` (Extend POCO).
    -   **CS0120** (Static vs Instance): `INSTANCE_REQUIRED` (Fix method call style).
    -   **Default**: `FIX_LOGIC_GAPS` (Trigger general retry logic for the node).

#### 2.3.2 Semantic Issue Analysis (`_analyze_semantic_issue`)
1.  **TODO Detection**: If code contains "TODO: Step failed", find the failing node ID and suggest `FIX_LOGIC_GAPS`.
2.  **Spec Violations**:
    -   `SPEC_STEP_NOT_EMITTED`: Suggest `FIX_LOGIC_GAPS` for the missing step.
    -   `SPEC_OUTPUT_TYPE_MISMATCH`: Suggest `FIX_LOGIC_GAPS` to retry binding.
3.  **Data Flow**:
    -   "Node X not consumed by Y": Suggest `REBIND_INPUT_LINK`.

#### 2.3.3 Logic Mismatch Analysis (`analyze_logic_mismatch`)
1.  **Delusional Literals**: Scan code for `Console.WriteLine` calls that output hardcoded strings instead of data variables (when the intent was data display). Suggest `FORCE_VARIABLE_BINDING`.
2.  **Logic Verification**: Use `LogicAuditor` to verify if numeric/boolean constraints in the semantic map (e.g., "price > 100") are actually present in the generated code. If missing, suggest `FIX_LOGIC_GAPS`.

### 2.4 Test Cases

#### Happy Path
1.  **Missing Field Error**:
    -   Input: Error CS0103 "The name '_httpClient' does not exist".
    -   Result: Hint `type="ENSURE_FIELD_OR_LOCAL"`, `name="_httpClient"`.
2.  **Logic Gap**:
    -   Input: Semantic issue "GENERATED_CODE_CONTAINS_TODOS". Trace shows Node "n1" failed.
    -   Result: Hint `type="FIX_LOGIC_GAPS"`, `failed_texts=["n1"]`.
3.  **Literal Hallucination**:
    -   Input: Code `Console.WriteLine("Item");` for a node intended to display `item.Name`.
    -   Result: Hint `type="FORCE_VARIABLE_BINDING"`.

#### Edge Cases
1.  **Unknown Compilation Error**:
    -   Input: Error "CS9999".
    -   Result: Generic `FIX_LOGIC_GAPS` hint targeting the specific node (if locatable).
2.  **No Code Generated**:
    -   Input: Empty string code.
    -   Result: Returns empty hints (or handles gracefully).
