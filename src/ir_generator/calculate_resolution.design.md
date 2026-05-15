# calculate_resolution Design Document

## 1. Purpose

`calculate_resolution` は `CALCULATE` role の source provenance を deterministic に固定する helper である。

## 2. Structured Specification

### Input
- **Description**: 既存の `semantic_roles`、および必要なら structural upstream node id。
- **Type/Format**: `Dict[str, Any]`, `Optional[str]`

### Output
- **Description**: `calculate_source_resolution`, `calculate_source_node_id`, `calculate_target_resolution` を含む更新済み `semantic_roles`。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. `source_var` が明示されている場合は `calculate_source_resolution=source_var` を付ける。
2. explicit source が無く structural upstream がある場合は
   - `calculate_source_node_id`
   - `calculate_source_resolution=input_link_var`
   を付ける。
3. explicit source も structural source も無い場合は、silent fallback にせず `calculate_source_resolution=default_scope_var` を付ける。
4. explicit source がある場合は structural source で上書きしない。
5. `property` / `target_hint` がある場合は baseline として `calculate_target_resolution=explicit_target` を付ける。
6. canonical property と current target entity が確定している場合は、`calculate_target_resolution` を `schema_property` または `history_target` へ上げる。

### Boundary Rule
- lexical 推定だけで `source_var` を発明しない。
- `input_link` が `CHECK` のような structural parent を指す場合は、semantic upstream source へ引き直した node id を使う。
- `default_scope_var` は弱保持の観測用 provenance であり、exact upstream source が無いことを隠さない。
- `calculate_target_resolution` は target/property の強さを表すだけで、generic free-text を schema-backed property へ自動昇格させない。

## 3. Dependencies
- **Internal**:
  - `ir_generator`

## 4. Notes
- この helper は source/value の具体化ではなく provenance 供給だけを担当する。
- downstream の exact var 解決は `ActionSynthesizer` / `calc_ops` 側で行う。
- `default_scope_var` のとき downstream は `active_scope_item` に留まってよく、別 node の latest var を exact source とみなしてはならない。
- `calculate_target_resolution=explicit_target` は weak retention であり、property-aware concretization の成功を意味しない。
