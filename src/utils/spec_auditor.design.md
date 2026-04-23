# Spec Auditor Design Document

## 1. Purpose
The `SpecAuditor` [Phase 23.4] is a quality assurance component that validates whether the synthesized code actually faithfully implements the provided `StructuredSpec`. It compares the original design intent (steps, output types, side effects) against the generated Intermediate Representation (IR) and Blueprint to detect dropped logic, missing side effects, or signature mismatches.

## 2. Structured Specification

### 2.1 Inputs
- **spec** (`Dict[str, Any]`): The parsed `StructuredSpec`.
- **synthesis_result** (`Dict[str, Any]`): The output from the synthesis engine, containing `trace` (IR/Blueprint) and `best_path`.

### 2.2 Output
- **Issues** (`List[str]`): A list of formatted error strings (e.g., `SPEC_STEP_NOT_EMITTED|step_1`). Empty list implies full compliance.

### 2.3 Core Logic

#### 2.3.1 Step Coverage Audit
1.  **Collection**: Traverse `best_path["statements"]` and `hoisted_statements` to collect all `node_id`s present in the final code.
2.  **Verification**: Iterate through `spec["steps"]`.
    -   Skip control flow markers (END, ELSE).
    -   Check if `step_id` (or a derived ID like `step_1_sub`) exists in the collected set.
    -   If missing, record `SPEC_STEP_NOT_EMITTED`.

#### 2.3.2 Side-Effect Alignment
1.  **Flatten IR**: Convert the recursive `logic_tree` into a flat list of nodes.
2.  **Verification**: Iterate through `spec["steps"]` that declare a side effect (DB, IO, NETWORK).
    -   Find corresponding IR nodes.
    -   Check if the node's `intent` or `source_kind` matches the declared side effect.
        -   **DB**: `intent` in [DATABASE_QUERY, PERSIST] or `source_kind`="db".
        -   **IO**: `intent` in [FETCH, FILE_IO, WRITE] or `source_kind` in [file, env, stdin].
        -   **NETWORK**: `intent` in [HTTP_REQUEST] or `source_kind`="http".
    -   If mismatch/missing, record `SPEC_SIDE_EFFECT_MISSING`.

#### 2.3.3 Output Type Compliance
1.  **Extract Expected**: Get `type_format` from `spec["outputs"][0]`.
2.  **Extract Actual**: Get `return_type` from `blueprint["methods"][0]`.
3.  **Comparison**:
    -   Normalize strings (lowercase, remove spaces).
    -   Handle `Task<T>` unwrap if the spec implies async operations (e.g., side effects present or "async" in description).
    -   If types differ, record `SPEC_OUTPUT_TYPE_MISMATCH`.

### 2.4 Test Cases

#### Happy Path
1.  **Full Compliance**:
    -   Spec: 1 Step (ACTION), Output (int).
    -   Code: 1 Node emitted, Return int.
    -   Result: `[]`.
2.  **Async Wrapping**:
    -   Spec: Output (string), SideEffect (IO).
    -   Code: Return `Task<string>`.
    -   Result: `[]` (Valid because IO implies async).

#### Edge Cases
1.  **Dropped Step**:
    -   Spec has `step_2`. Code only has `step_1`.
    -   Result: `["SPEC_STEP_NOT_EMITTED|step_2"]`.
2.  **Fake Side Effect**:
    -   Spec declares `DB` side effect. Code uses `List.Add` (Memory).
    -   Result: `["SPEC_SIDE_EFFECT_MISSING|step_1|DB"]`.
3.  **Type Mismatch**:
    -   Spec expects `int`. Code returns `string`.
    -   Result: `["SPEC_OUTPUT_TYPE_MISMATCH|step_last|int|string"]`.
