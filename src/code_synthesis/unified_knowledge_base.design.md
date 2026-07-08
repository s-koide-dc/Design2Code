# Unified Knowledge Base Design Document

## 1. Purpose
The `UnifiedKnowledgeBase` (UKB) [Phase 23.3] serves as the central intelligence facade for the synthesis engine. It aggregates and structurally filters code assets from `MethodStore` (external libraries like .NET Base Class Library), `StructuralMemory` (internal project code), and curated pattern/template sources. Its primary goal is to return structurally valid candidates for a given semantic request. Vector similarity may order candidates, but it must not decide the final method when multiple structurally compatible candidates remain.

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
    -   `source_kind` (str): Explicit source category constraint (e.g., "file", "db", "http").

### 2.2 Output
- **Structurally Valid Candidates** (`List[Dict[str, Any]]`): A list of method/pattern definitions that satisfy the explicit structural constraints. If exactly one candidate remains, it is returned. If multiple candidates remain, `AmbiguousMethodCandidatesError` is raised with candidate identifiers.

### 2.3 Core Logic

#### 2.3.1 Aggregation (`search`)
1.  **External Search**: Query `MethodStore` for library methods (broad search).
2.  **Internal Search**: Query `StructuralMemory` for project code candidates. Natural-language/vector similarity is used only to discover and order candidates.
3.  **Pattern/Template Matching**:
    -   Load `action_patterns.json` and `canonical_knowledge.json`.
    -   Add pattern/template candidates to the unified candidate set; they are filtered by the same structural constraints as method candidates.

#### 2.3.2 Filtering & Validation
1.  **Identifier Validity**: Exclude candidates with unsupported generated/internal identifier forms.
2.  **Intent/Role Check**: Candidate intent, role, or declared capabilities must satisfy the requested intent and `requested_role`.
3.  **Source Check**: `source_kind` must match the candidate's declared source kind or structural target (`_dbConnection`, `_httpClient`).
4.  **Target Entity Check**:
    -   Explicit `target_entity` must match the candidate's declared `target_entity`.
    -   For source-less `TRANSFORM` calls, the terminal class name may serve as a declared structural target (for example, `App.Services.BusinessLogic` -> `BusinessLogic`).
    -   Source-less `TRANSFORM` candidates without a declared target are not accepted when a target entity is explicit.
5.  **Type Check**: `input_type` and `return_type` are validated with `TypeSystem`.

#### 2.3.3 Candidate Ordering and Ambiguity
1.  Candidate identity is deduplicated by `id`, `full_name`, or `name`.
2.  Vector similarity score is preserved as metadata and may order the returned candidate list.
3.  A higher vector score never resolves ambiguity by itself.
4.  If multiple structurally compatible candidates remain after filtering, UKB raises `AmbiguousMethodCandidatesError`; downstream synthesis must either add structural constraints or report ambiguity.

### 2.4 Test Cases

#### Happy Path
1.  **Intent Search**:
    -   Query: "Save user", Intent: "PERSIST", Entity: "User"
    -   Result: A structurally valid Repository.Save method or Dapper Execute pattern is returned only if the constraints identify one candidate.
2.  **Type Constrained**:
    -   Query: "Get count", ReturnType: "int"
    -   Result: Returned candidates must be compatible with `int`.
3.  **Template Retrieval**:
    -   Query: "Select from DB", Intent: "DATABASE_QUERY"
    -   Result: Dapper query template is returned only when the source and return constraints make it structurally unambiguous.

#### Edge Cases
1.  **Role Mismatch**:
    -   Intent: "READ", Candidate Role: "WRITE"
    -   Result: Candidate is filtered out.
2.  **Ambiguous Structural Match**:
    -   Intent: "FETCH", Source: "file", ReturnType: "string"
    -   Result: If both `ReadAllText` and `ReadAllLines` remain, UKB raises `AmbiguousMethodCandidatesError` even when vector scores differ.
3.  **No Results**:
    -   Query: "UnknownMagic"
    -   Result: Empty list (graceful degradation).

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.
- 2026-06-04: `INTENT_CAPABILITY_MAP` と role-based ranking の主要比較を `src.utils.semantic_intents` の共通語彙へ寄せた。
- 2026-07-01: 内部候補検索を役割・戻り値型の明示条件で事前フィルタするよう変更。
- 2026-07-07: ベクトルスコアによる単独候補確定を廃止。スコアは候補順序のメタデータに限定し、最終確定は構造制約でのみ行う。

## 5. Operational Notes
- `action_patterns.json` と `canonical_knowledge.json` の読込失敗は stdout ではなく logger に記録する。
- UKB 自体は検索結果を返すファサードであり、利用者向け出力責務を持たない。

