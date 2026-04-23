# Unified Knowledge Base Design Document

## 1. Purpose
The `UnifiedKnowledgeBase` (UKB) [Phase 23.3] serves as the central intelligence facade for the synthesis engine. It aggregates, filters, and ranks code assets from three distinct sources: `MethodStore` (external libraries like .NET Base Class Library), `StructuralMemory` (internal project code), and `TemplateRegistry` (curated patterns). Its primary goal is to provide the most contextually appropriate method or code snippet for a given semantic request.

## 2. Structured Specification

### 2.1 Inputs
- **Dependencies**:
    -   `MethodStore`: Access to indexed external libraries.
    -   `StructuralMemory`: Access to the current project's codebase.
    -   `ConfigManager`: Configuration access.
- **Search Parameters**:
    -   `query` (str): Natural language description or keywords.
    -   `intent` (str): Semantic intent (e.g., "FETCH", "DISPLAY").
    -   `target_entity` (str): The entity being operated on (e.g., "User").
    -   `return_type` (str): Expected return type constraint.
    -   `input_type` (str): Expected input type constraint.
    -   `requested_role` (str): Specific role required (e.g., "READ", "WRITE").

### 2.2 Output
- **Ranked Candidates** (`List[Dict[str, Any]]`): A list of method/pattern definitions, sorted by relevance score.

### 2.3 Core Logic

#### 2.3.1 Aggregation (`search`)
1.  **External Search**: Query `MethodStore` for library methods (broad search).
2.  **Internal Search**: Query `StructuralMemory` for project-specific methods (semantic vector search).
3.  **Pattern/Template Matching**:
    -   Load `action_patterns.json` and `canonical_knowledge.json`.
    -   Filter based on `intent` and `INTENT_CAPABILITY_MAP`.
    -   Assign high base scores to matched templates (0.9 - 1.0).

#### 2.3.2 Filtering & Validation
1.  **Blacklist**: Exclude methods known to cause issues (e.g., `Enumerable.ToList` loop, `GenericAction`).
2.  **Noise Reduction**: Filter out internal .NET namespaces (e.g., `Serialization.Metadata`, `Reflection`).
3.  **Capability Check**:
    -   Verify candidate's capabilities against the requested intent using `INTENT_CAPABILITY_MAP`.
    -   Example: If intent is "PERSIST", candidate must support "WRITE", "PERSIST", or "DATABASE_ACCESS".

#### 2.3.3 Ranking Strategy (`_rank_candidates`)
Candidates are sorted based on a tuple of priority scores (Descending Order):
1.  **Role Match** (Score 0-5): Exact match with `requested_role` (e.g., READ vs READ).
2.  **Template Priority** (Score 0-25): Patterns and Templates get massive boost over raw methods.
3.  **Architecture Tier** (Score 0-4): Internal methods > Tier 2/3 (Domain/Infra) > Tier 1 (UI).
4.  **Intent Match** (Score 0-2): Explicit intent alignment.
5.  **Entity Match** (Score 0-2): Name/Class matches `target_entity`.
6.  **Type Compatibility** (Score 0-3): Return/Input types match requirements (via `TypeSystem`).
7.  **Knowledge Match** (Score 0-2): Keywords match `DOMAIN_ONTOLOGY`.
8.  **Base Similarity**: Vector/Text similarity score.

### 2.4 Test Cases

#### Happy Path
1.  **Intent Search**:
    -   Query: "Save user", Intent: "PERSIST", Entity: "User"
    -   Result: Top candidate is a Repository.Save method or Dapper Execute pattern.
2.  **Type Constrained**:
    -   Query: "Get count", ReturnType: "int"
    -   Result: Top candidate returns `int` (e.g., `List.Count`, `Count()`).
3.  **Template Retrieval**:
    -   Query: "Select from DB", Intent: "DATABASE_QUERY"
    -   Result: Dapper query template ranks higher than generic `IDbConnection` methods.

#### Edge Cases
1.  **Blacklisted Method**:
    -   Query matches "ToList"
    -   Result: `Enumerable.ToList` is excluded to prevent infinite recursion in synthesis.
2.  **Role Mismatch**:
    -   Intent: "READ", Candidate Role: "WRITE"
    -   Result: Candidate penalised or filtered out.
3.  **No Results**:
    -   Query: "UnknownMagic"
    -   Result: Empty list (graceful degradation).

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.

