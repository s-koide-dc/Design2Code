# TypeSystem Design Document

## 1. Purpose
The `TypeSystem` simulates C# type compatibility, inheritance, and generic constraints to guide the `CodeSynthesizer` in selecting appropriate methods and variables.

## 2. Structured Specification

### Core Logic
1.  **Normalization**: Standardizes type names (removes namespaces, handles aliases like `int`/`Int32`).
2.  **Compatibility Check (`is_compatible`)**:
    -   **Exact Match**: Score 100.
    -   **Inheritance**: Score based on hierarchy depth.
    -   **Numeric Widening**: Allowed (e.g., `int` -> `double`) with high score (85).
    -   **String Conversion**:
        -   `bool` -> `string`: **Explicitly blocked** (Score 0) to prevent logic errors.
        -   `int`/`double` -> `string`: Score 90.
    -   **Bridge Conversions**:
        -   `IEnumerable` -> `string` (Serialization): **Low Score (2)** to prioritize item-level processing.
3.  **Generics & Concretization**:
    -   Handles open generics (`List<T>`) and constraints.
    -   Concretizes `T` based on context.
    -   **Automatic List Wrapping**: If the context hint suggests multiple items (e.g., "all", "list"), automatically wraps the target type in `List<T>`.

### Interface
-   `is_compatible(target, source)`: Returns `(bool, score, conversion_template)`. The `conversion_template` provides the necessary C# code (e.g., `JsonSerializer.Serialize({var})`) to bridge incompatible types.

## 3. Dependencies
-   None (Pure logic).

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.

