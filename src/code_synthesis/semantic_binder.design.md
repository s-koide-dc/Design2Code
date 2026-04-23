# Semantic Binder Design Document

## 1. Purpose
The `SemanticBinder` is a critical component of the Code Synthesis module [Phase 23.3]. It functions as the "High-fidelity Logical Synthesis Layer," bridging the gap between abstract semantic intent (from the Design Parser) and concrete C# code artifacts. Its primary responsibilities are binding method parameters, generating boolean logic expressions, and resolving variable references within the current execution scope.

## 2. Structured Specification

### 2.1 Inputs
- **Method Definition** (`Dict[str, Any]`): Metadata about the target C# method (name, parameters, types, roles).
- **Node** (`Dict[str, Any]`): The current action node containing semantic maps, intents, and roles.
- **Path** (`Dict[str, Any]`): The current synthesis context, including available variables (`type_to_vars`), active scope items, and POCO definitions.

### 2.2 Outputs
- **Parameter Values** (`List[str]`): A list of C# code strings representing the arguments to be passed to a method.
- **Logic Expression** (`str`): A C# boolean expression string (e.g., `item.Price > 1000 && item.IsActive`).
- **Resolved Variable** (`Tuple[str, Optional[str]]`): The name of a variable in the current scope that best matches a requested type and role.

### 2.3 Core Logic

#### 2.3.1 Parameter Binding (`bind_parameters`)
1.  **Iterate Parameters**: For each parameter in the target method:
    -   **Semantic Map Lookup**: Check if the parameter's role exists in `node.semantic_map.semantic_roles`.
        -   If found and type is `string`, handle literals (quote/escape) vs. variable references.
    -   **Literal Injection**:
        -   If role is "url", extract URL from `original_text` using regex.
        -   If role is "path" or "sql", check `path["last_literal_map"]` for context continuity.
        -   If role is "sql" and intent is "PERSIST", invoke `_build_persist_sql`.
    -   **Contextual Fallback**:
        -   If intent is "DATABASE_QUERY" and role is "params", try to find an existing input variable (int/decimal/string).
    -   **Variable Resolution**:
        -   Call `_resolve_source_var` to find a matching variable in the current scope.
    -   **Default/Literal Fallbacks**:
        -   If "literal_only" constraint exists, return empty string/zero/null.
        -   Handle `HttpContent` serialization for HTTP_REQUESTs.
2.  **Dapper/SQL Specialization**:
    -   If the method is a Dapper execution, parse the SQL string for parameters (e.g., `@Name`).
    -   Wrap matching arguments into an anonymous object `new { Name = value }`.
3.  **Sanity Checks**:
    -   Validate that critical roles (data, predicate) are not bound to `null`.

#### 2.3.2 Logic Expression Generation (`generate_logic_expression`)
1.  **Goal Parsing**: Iterate through `semantic_map.logic` goals.
2.  **Property Resolution**:
    -   If `semantic_roles.property`/`field`/`target_property` is specified, use it as the authoritative property.
    -   For each goal, resolve the target property on the `target_entity` POCO using hints (e.g., "価格" -> "Price").
    -   Use `_resolve_prop` with a priority map and fuzzy matching.
3.  **Expression Building**:
    -   Map semantic operators (Greater, Equal, etc.) to C# operators (`>`, `==`).
    -   Handle string methods (`StartsWith`, `Contains`).
    -   Handle numeric comparisons.
    -   Support "variable access" (e.g., `item.Price` vs `Price` depending on loop context).
4.  **Aggregation**: Join individual expressions with `&&` or `||`.

#### 2.3.3 Variable Resolution (`_resolve_source_var`)
1.  **Candidate Gathering**: Collect all variables in `path` matching the `target_type` or compatible types (via `TypeSystem`).
2.  **Scoring**:
    -   **Role Match**: +10 points if variable role matches requested role.
    -   **Synonym Match**: +5 points if variable role is a synonym (e.g., "content" <-> "data").
    -   **Recency**: Higher score for more recently declared variables.
    -   **Context Penalty**: Penalize "READ" variables if a "TRANSFORM" result is available.
3.  **Selection**: Return the highest-scoring variable.

#### 2.3.4 Persistence SQL Generation (`_build_persist_sql`)
1.  **Intent Check**: Verify the node text implies an update/save operation.
2.  **Entity Resolution**: Identify the target table/entity.
3.  **Column Selection**: Heuristically choose a column to update (e.g., `Status`, `UpdatedAt`) if not specified.
4.  **Query Construction**: Generate `UPDATE Table SET Col = @Col WHERE Id = @Id`.

### 2.4 Test Cases

#### Happy Path
1.  **Bind Literal Parameter**:
    -   Method: `WriteAllText(string path, string content)`
    -   Semantic Map: `{"path": "test.txt", "content": "hello"}`
    -   Result: `["\"test.txt\"", "\"hello\""]`
2.  **Bind Variable Parameter**:
    -   Method: `Console.WriteLine(string value)`
    -   Path: Contains `string message = "Hi"` (role="content")
    -   Result: `["message"]`
3.  **Generate Logic Expression**:
    -   Goal: `{"operator": "Greater", "expected_value": 100, "variable_hint": "price"}`
    -   POCO: `Product { decimal Price; }`
    -   Result: `item.Price > 100m`

#### Edge Cases
1.  **SQL Generation Fallback**:
    -   Intent: PERSIST, Text: "Update status"
    -   POCO: `User { int Id; string Status; }`
    -   Result: `UPDATE Users SET Status = @Status WHERE Id = @Id` (bound to `sql` param).
2.  **Unknown Property Hint**:
    -   Goal: Filter by "UnknownProp"
    -   Result: Fallback to primary property or "Unknown" (graceful failure logic).
3.  **Dapper Anonymous Object**:
    -   SQL: `SELECT * FROM Users WHERE Name = @Name`
    -   Params: `string name`
    -   Result: `["sql_query", "new { Name = name_var }"]`

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.

