# Knowledge Extractor Design Document

## 1. Purpose
The `KnowledgeExtractor` [Phase 7.1] is a utility component designed to "learn" from the project's own source code. It uses Abstract Syntax Tree (AST) parsing to extract implicit knowledge structures—specifically type hierarchies and intent semantic clusters—hardcoded in other Python modules (`type_system.py`, `ir_generator.py`). This extracted knowledge is consolidated into a `canonical_knowledge.json` file, serving as a dynamic source of truth for the synthesis engine.

## 2. Structured Specification

### 2.1 Inputs
- **workspace_root** (`str`): The absolute path to the project root directory.
- **Source Files** (Implicit):
    -   `src/code_synthesis/type_system.py`: Target for type hierarchy extraction.
    -   `src/ir_generator/ir_generator.py`: Target for intent pattern extraction.
- **Existing Knowledge** (Optional): `resources/canonical_knowledge.json`.

### 2.2 Output
- **canonical_knowledge.json** (`File`): A JSON file containing:
    -   `type_mappings`: Extracted type hierarchy.
    -   `common_patterns`: Extracted intent semantic clusters.
    -   `templates`: Preserved existing templates.

### 2.3 Core Logic

#### 2.3.1 AST Extraction (`extract_from_source`)
1.  **Type System Extraction**:
    -   Parse `type_system.py`.
    -   Walk the AST to find an assignment to the variable `hierarchy`.
    -   If found, recursively parse the dictionary literal (`ast.Dict`) into a Python dictionary.
2.  **IR Pattern Extraction**:
    -   Parse `ir_generator.py`.
    -   Walk the AST to find an assignment to `intent_semantic_clusters`.
    -   If found, parse the dictionary literal.

#### 2.3.2 AST Parsing (`_parse_ast_dict`, `_get_value`)
1.  **Safety**: Only support literal structures (Dict, List, Set, Constant/Str). Do not execute code.
2.  **Recursion**: Handle nested dictionaries and lists.
3.  **Serialization**: Convert Sets to Lists for JSON compatibility.

#### 2.3.3 Knowledge Persistence (`save_canonical_knowledge`)
1.  **Load Existing**: Read `canonical_knowledge.json` if it exists.
2.  **Merge**:
    -   Overwrite `type_mappings` and `common_patterns` with newly extracted data (assuming source code is the source of truth).
    -   Preserve `templates` from the existing file (as they might be manually curated or learned elsewhere).
3.  **Save**: Write the merged dictionary to disk with indentation.

### 2.4 Test Cases

#### Happy Path
1.  **Extract Type Hierarchy**:
    -   Mock `type_system.py` content: `hierarchy = {"int": ["long", "decimal"]}`
    -   Result: `knowledge["type_mappings"]` equals `{"int": ["long", "decimal"]}`.
2.  **Extract IR Patterns**:
    -   Mock `ir_generator.py` content: `intent_semantic_clusters = {"create": ["new", "add"]}`
    -   Result: `knowledge["common_patterns"]` equals `{"create": ["new", "add"]}`.
3.  **Merge and Save**:
    -   Existing JSON: `{"templates": ["t1"]}`
    -   Extracted: `{"type_mappings": {...}}`
    -   Result File: `{"templates": ["t1"], "type_mappings": {...}}`

#### Edge Cases
1.  **File Not Found**:
    -   Condition: Target source files are missing.
    -   Result: Gracefully skip extraction, no crash.
2.  **AST Error**:
    -   Condition: Source file has syntax error.
    -   Result: Catch exception, log error, skip that file.
3.  **Unsupported AST Node**:
    -   Condition: Variable assigned to function call `hierarchy = get_hierarchy()`.
    -   Result: `_parse_ast_dict` returns None or skips, avoiding arbitrary code execution.
