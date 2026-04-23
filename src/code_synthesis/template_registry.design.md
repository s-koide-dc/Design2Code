# Template Registry Design Document

## 1. Purpose
The `TemplateRegistry` [Phase 23.3] manages the collection of reusable code templates used during synthesis. It acts as a repository interface, loading template definitions from `canonical_knowledge.json` and providing a query mechanism to retrieve relevant templates based on semantic intent, data source types, and operational constraints.

## 2. Structured Specification

### 2.1 Inputs
- **knowledge_path** (`str`, optional): Path to the `canonical_knowledge.json` file. Defaults to `resources/canonical_knowledge.json`.
- **Query Parameters**:
    -   `intent` (str): The desired semantic intent (e.g., "DATABASE_QUERY").
    -   `source_kind` (str, optional): The type of data source (e.g., "db", "http", "file").
    -   `is_db_allowed` (bool): Whether database operations are permitted in the current context.

### 2.2 Output
- **List[Dict[str, Any]]**: A list of template dictionaries matching the criteria.

### 2.3 Core Logic

#### 2.3.1 Initialization
1.  **Load JSON**: Attempt to read the file at `knowledge_path`.
2.  **Parse**: Extract the `templates` list from the JSON object.
3.  **Error Handling**: Log errors if file is missing or invalid JSON, initializing with an empty list.

#### 2.3.2 Template Retrieval (`get_templates_for_intent`)
1.  **Iterate**: Loop through all loaded templates.
2.  **Blacklist Check**: Skip templates with names known to be legacy or problematic (e.g., "Enumerable.ToList", "GenericAction").
3.  **Intent Match**:
    -   Check if template's `intent` matches the query `intent`.
    -   Alternatively, check if query `intent` is present in template's `capabilities` list.
    -   If neither matches, skip.
4.  **Constraint Filtering**:
    -   **Database**: If template targets `_dbConnection` or has `DATABASE_QUERY` capability, but `is_db_allowed` is False, skip.
    -   **Source Kind**: If template specifies a `source_kind` (e.g., "db") and query specifies a different `source_kind` (e.g., "file"), skip.
5.  **Return**: Collect and return all passing templates.

### 2.4 Test Cases

#### Happy Path
1.  **Basic Intent Match**:
    -   Template: `{"name": "t1", "intent": "DISPLAY"}`
    -   Query: `intent="DISPLAY"`
    -   Result: `[t1]`
2.  **Capability Match**:
    -   Template: `{"name": "t2", "capabilities": ["CALC"]}`
    -   Query: `intent="CALC"`
    -   Result: `[t2]`

#### Edge Cases
1.  **DB Restriction**:
    -   Template: `{"name": "db_t", "target": "_dbConnection"}`
    -   Query: `intent="FETCH", is_db_allowed=False`
    -   Result: `[]`
2.  **Source Mismatch**:
    -   Template: `{"name": "http_t", "source_kind": "http"}`
    -   Query: `intent="FETCH", source_kind="db"`
    -   Result: `[]`
3.  **Missing File**:
    -   Condition: `knowledge_path` does not exist.
    -   Result: Registry initializes safely with 0 templates.
