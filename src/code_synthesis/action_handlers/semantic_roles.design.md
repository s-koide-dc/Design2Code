# semantic_roles Design Document

## 1. Purpose

`semantic_roles` はノードに付与された `semantic_roles` を正規化して返す。

## 2. Structured Specification

### Input
- **Description**: 解析対象ノード。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: 正規化済みの `semantic_roles` 辞書。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. ノードの `semantic_roles` と `semantic_map.semantic_roles` を取得する。
2. `semantic_map` を優先し、`semantic_roles` で上書きする。
3. `None` 値は除外して返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 両方にキーが存在する。
  - **Expected Output**: `semantic_roles` の値で上書きされる。
- **Edge Cases**:
  - **Scenario**: `semantic_roles` が空。
  - **Expected Output / Behavior**: `semantic_map` の値のみが返る。

## 3. Dependencies
- **Internal**: `code_synthesis`
