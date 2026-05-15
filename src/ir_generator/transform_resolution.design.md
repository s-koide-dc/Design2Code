# transform_resolution Design Document

## 1. Purpose

`transform_resolution` は `TRANSFORM` role の operation/source provenance を deterministic に固定する helper である。

## 2. Structured Specification

### Input
- **Description**: 既存の `semantic_roles`、および必要なら structural upstream node id。
- **Type/Format**: `Dict[str, Any]`, `Optional[str]`

### Output
- **Description**: `transform_op_resolution`, `transform_source_resolution`, `transform_source_node_id` を含む更新済み `semantic_roles`。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. `ops` が明示されている場合は `transform_op_resolution=explicit_ops` を付ける。
2. `source_var` が明示されている場合は `transform_source_resolution=source_var` を付ける。
3. explicit source が無く structural upstream がある場合は
   - `transform_source_node_id`
   - `transform_source_resolution=input_link_var`
   を付ける。
4. explicit source がある場合は structural source で上書きしない。

### Boundary Rule
- lexical 推定だけで `source_var` を発明しない。
- `input_link` が `CHECK` のような structural parent を指す場合は、semantic upstream source へ引き直した node id を使う。

## 3. Dependencies
- **Internal**:
  - `ir_generator`

## 4. Notes
- この helper は source/value の具体化ではなく provenance 供給だけを担当する。
- downstream の exact var 解決は `ActionSynthesizer` 側で行う。
