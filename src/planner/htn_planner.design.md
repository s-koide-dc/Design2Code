# HTN Planner Design Document

## 1. Purpose
The `HTNPlanner` [Phase 23.3] is responsible for breaking down high-level, abstract user intents into concrete, executable sequences of method calls. Utilizing a Hierarchical Task Network (HTN) approach, it recursively decomposes goals (e.g., "Update User") into sub-tasks (Fetch, Modify, Save) and assigns specific C# methods from the Unified Knowledge Base (UKB) to each step, ensuring type safety and logical flow.

## 2. Structured Specification

### 2.1 Inputs
- **Dependencies**: `UnifiedKnowledgeBase` (for method lookup), `TypeSystem` (for compatibility checks).
- **Request**:
    -   `intent` (str): The high-level goal (e.g., "UPDATE", "CREATE").
    -   `target_entity` (str): The domain entity (e.g., "User", "File").
    -   `source_kind` (str, optional): Constraint on data source (e.g., "db", "file").

### 2.2 Output
- **Action Plan** (`List[Dict[str, Any]]`): A sequence of step dictionaries, each containing:
    -   `task`: The sub-task name.
    -   `entity`: The target entity.
    -   `method`: The assigned `MethodDef` (if found).
    -   `status`: "assigned" or "missing".
    -   `adapter`: Optional transformation logic (if type bridging is needed).

### 2.3 Core Logic

#### 2.3.1 Goal Decomposition (`create_action_plan`)
The `decompose` function operates recursively (max depth 3):
1.  **Direct Match**: Search UKB for a method or pattern matching the `task_name` and `entity`.
    -   If a "pattern" (e.g., Dapper Execute) is found, return it as a single, complete step (patterns often encapsulate multiple logical steps).
    -   If a single method is found, return it as an assigned step.
2.  **Rule Expansion**: Look up `task_name` in `self.task_networks`.
    -   **UPDATE** -> [FETCH, MODIFY, SAVE]
    -   **CREATE** -> [VALIDATE, SAVE]
    -   **DELETE** -> [FETCH, DELETE]
    -   **TRANSFORM** -> [FETCH, TRANSFORM, SAVE]
    -   Recursively decompose each sub-task.
3.  **Dynamic Bridging**:
    -   If `task_name` is "FETCH" (and no direct match), try decomposing into [READ, JSON_DESERIALIZE].

#### 2.3.2 Post-Processing
-   **Redundancy Removal**: If a step is assigned a "pattern" method, check its `steps` metadata. If the pattern covers subsequent tasks (e.g., a "Save" pattern that includes connection opening), remove those redundant steps from the plan.

#### 2.3.3 Plan Validation (`validate_plan`)
Iterates through the generated plan to ensure data flow connectivity:
1.  **Connectivity Check**: Compare `Step[i].Output` with `Step[i+1].Input`.
2.  **Type Compatibility**: Use `TypeSystem.is_compatible`.
3.  **Adapter Injection**:
    -   If types match directly -> Pass.
    -   If types match via transformation (e.g., `HttpResponseMessage` -> `string`) -> Inject `adapter` metadata into `Step[i+1]`.
    -   If types mismatch -> Record error message and `type_error` metadata.

### 2.4 Test Cases

#### Happy Path
1.  **Simple Update**:
    -   Input: Intent="UPDATE", Entity="User".
    -   Result: Plan with 3 steps:
        1.  FETCH (e.g., `UserRepository.Get`)
        2.  MODIFY (Placeholder or setter logic)
        3.  SAVE (e.g., `UserRepository.Save`)
2.  **Direct Pattern**:
    -   Input: Intent="DATABASE_QUERY", Entity="User".
    -   Result: Single step containing a Dapper query pattern.
3.  **Type Bridging**:
    -   Step 1 returns `HttpResponseMessage`. Step 2 expects `string`.
    -   Result: Step 2 has adapter `await {var}.Content.ReadAsStringAsync()`.

#### Edge Cases
1.  **Missing Method**:
    -   Input: Intent="UNKNOWN", Entity="Alien".
    -   Result: Step with `status="missing"`.
2.  **Type Mismatch**:
    -   Step 1 returns `int`. Step 2 expects `List<string>`.
    -   Result: Validation returns error strings.
3.  **Recursion Limit**:
    -   Circular dependency in rules.
    -   Result: Recursion stops at depth 3, returning empty/partial plan.
