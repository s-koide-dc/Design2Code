# Semantic Assertions Design Document

## 1. Purpose
The `SemanticAssertions` module [Phase 23.4] provides a rule-based verification engine to ensure that the synthesized code meets specific semantic contracts. Unlike the compiler (which checks syntax) or the `SpecAuditor` (which checks coverage), this module verifies *how* the code behaves—for example, ensuring that a variable returned by `GetUsers()` is actually used later, or that `Console.WriteLine` displays a specific property.

## 2. Structured Specification

### 2.1 Inputs
- **blueprint** (`Dict[str, Any]`): The synthesized code structure (methods, body, statements).
- **contract** (`Dict[str, Any]`): A dictionary defining the verification rules. New contracts use structured blueprint evidence (`require_intents`, `require_node_intents`); legacy text-oriented rules are retained only for existing callers during migration.

### 2.2 Output
- **Issues** (`List[str]`): A list of violation messages.
- **Exception**: `SemanticAssertionError` is raised by the wrapper if issues exist.

### 2.3 Core Logic

#### 2.3.1 Pre-processing (`flatten_statements`)
-   Recursively traverses the statement tree (handling `if`, `foreach`, `while`, `try`, `try_catch`, and `catch_body`) to produce a flat list of all statements for easier analysis.

#### 2.3.2 Contract Validation (`evaluate_blueprint_contract`)
1.  **Structured provenance checks** (`require_intents`, `require_node_intents`):
    - Verifies exact intent and node-id evidence attached to synthesized blueprint statements.
    - Does not inspect generated C# text, method-name fragments, or local variable spellings.
    - New scenario contracts must use these checks. Legacy rules below are transitional.
2.  **Structured data-flow checks** (`require_dataflow`):
    - Verifies an exact `source_node_id` → `consumer_node_id` edge retained from the IR `input_link` on emitted blueprint statements.
    - Both endpoints must be emitted; this prevents a contract from passing solely because an IR edge exists before synthesis.
3.  **Structured display-property checks** (`require_display_properties`):
    - Verifies the exact display property explicitly selected by semantic binding on an emitted display statement.
    - Does not inspect the rendered C# expression for property-name fragments.
4.  **Structured predicate checks** (`require_predicate_goals`):
    - Verifies the exact canonical predicate goals retained on the emitted LINQ statement, including conjunctions and literal values.
5.  **Automatic predicate-preservation contract** (`build_predicate_preservation_contract`):
    - Builds `require_predicate_goals` from a `StructuredSpec` only when a LINQ step explicitly provides a non-empty `logic` array.
    - The design-review quality gate evaluates this contract against the blueprint; it never infers a predicate from natural-language text.
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
4.  **Lost Explicit Predicate**:
    -   StructuredSpec: a LINQ step explicitly declares `Price > 100`.
    -   Blueprint: the emitted LINQ statement has no matching `predicate_goals`.
    -   Result: the design-review quality gate fails.
