# Action Synthesizer Design Document

## 1. Purpose
The `ActionSynthesizer` is a core component of the Code Synthesis module, responsible for transforming high-level design nodes (representing intents, actions, or control flow) into concrete C# intermediate representation (IR) or code statements. It operates as the "Pure Orchestration" layer [Phase 23.3], bridging the gap between abstract design plans and executable code.

## 2. Structured Specification

### 2.1 Input
- **node** (`Dict[str, Any]`): A dictionary representing the current action node from the execution plan. Key fields include:
    - `type` (str): Node type (e.g., "ACTION", "LOOP", "CONDITION").
    - `intent` (str): The semantic intent (e.g., "DISPLAY", "CALC", "RETURN", "general").
    - `target_entity` (str): The primary entity the action operates on.
    - `semantic_map` (Dict): Detailed semantic roles and logic.
    - `children` (List): Child nodes for container types (LOOP, CONDITION).
- **path** (`Dict[str, Any]`): The current synthesis state/context, containing:
    - `statements` (List): Accumulated code statements.
    - `type_to_vars` (Dict): Mapping of types to available variables.
    - `active_scope_item` (str): The most recently modified/accessed variable.
    - `poco_defs` (Dict): Definitions of POCO classes.
    - `all_usings` (Set): Required namespace imports.
- **future_hint** (`str`, optional): Hint for downstream synthesis.
- **consumed_ids** (`set`, optional): Set of node IDs already processed to prevent cycles.

### 2.2 Output
- **List[Dict[str, Any]]**: A list of potential synthesis paths (branches). Each path is a copy of the input `path` with:
    - Appended `statements` (e.g., method calls, control structures).
    - Updated `type_to_vars` and `active_scope_item`.
    - Updated `consumed_ids`.
    - Increased `completed_nodes` count.

### 2.3 Core Logic

1.  **Dispatch Strategy**:
    -   Evaluate `node.type` and `node.intent` to determine the specific processing handler.
    -   **LOOP**: Delegate to `_process_loop_node`.
    -   **CONDITION**: Delegate to `_process_condition_node`.
    -   **RETURN**: Delegate to `_process_return_node`.
    -   **LINQ**: Delegate to `_process_linq_filter_block`.
    -   **CALC**: Delegate to `_process_calc_node`.
    -   **DISPLAY/TRANSFORM**: Delegate to `_process_display_transform_specialized`.

2.  **Control Flow Handling**:
    -   **Loops**: Identify the collection variable in `path`. Generate a `foreach` structure. Recursively invoke the synthesizer for the loop body (children). Register the loop variable in the inner scope.
    -   **Conditions**: Use `SemanticBinder` to generate the boolean expression. Generate `if` (and optionally `else`) blocks. Recursively invoke the synthesizer for the bodies.

3.  **Calculation & Aggregation**:
    -   **Arithmetic**: Resolve variables for operands. Generate assignment statements (e.g., `var result = a + b;` or `total += amount;`).
    -   **CSV Aggregation**: Handle specific logic for `aggregate_by_product` ops, creating dictionaries and accumulating values.
    -   **State Updates**: Detect intents like "UPDATE" or "SET" to modify properties of existing objects instead of creating new variables.

4.  **Display & Transform**:
    -   **Display**: Generate `Console.WriteLine` calls. Handle literal strings, variable output, and POCO stringification.
    -   **Transform**: Apply specific string operations (`split_lines`, `trim_upper`, `format_kv`, `csv_serialize`) based on `ops` metadata.

5.  **General Action Synthesis**:
    -   **HTN Plans**: If `htn_plan` is present, expand it into a sequence of steps and process sequentially.
    -   **Candidate Gathering**: Query `TemplateRegistry` and `UKB` (Unified Knowledge Base) for methods matching the intent and target entity.
    -   **Method Synthesis**: For each candidate method:
        -   Bind parameters using `SemanticBinder`.
        -   Render the method call using `StatementBuilder`.
        -   Wrap in try-catch blocks if necessary.
        -   Handle return values (declare new variables, update scope).
    -   **Error Handling**: If no candidates are found, generate a `throw new NotImplementedException` statement to allow compilation (with a TODO marker).

### 2.4 Test Cases

#### Happy Path
1.  **Simple Method Call**:
    -   Input: Node with intent="GENERAL", method="File.WriteAllText".
    -   Expected: Path containing `File.WriteAllText(...)` statement.
2.  **Loop Generation**:
    -   Input: Node type="LOOP", child intent="DISPLAY". Path has `List<string> items`.
    -   Expected: Path containing `foreach (var item in items) { Console.WriteLine(item); }`.
3.  **Calculation**:
    -   Input: Intent="CALC", logic="a + b".
    -   Expected: Path containing `var result = a + b;`.

#### Edge Cases
1.  **Unknown Intent**:
    -   Input: Node with intent="UNKNOWN_MAGIC".
    -   Expected: Path containing `throw new NotImplementedException("TODO: Implement UNKNOWN_MAGIC...");`.
2.  **Missing Collection for Loop**:
    -   Input: Node type="LOOP" but path has no collection variables.
    -   Expected: Empty list (no valid paths) or error handling.
3.  **Display Null/Void**:
    -   Input: Intent="DISPLAY", target variable doesn't exist.
    -   Expected: Graceful fallback or generic message.

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.

