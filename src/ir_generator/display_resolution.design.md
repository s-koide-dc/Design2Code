# display_resolution Design Document

## 1. Purpose

`display_resolution` は `DISPLAY` role の property-side provenance を deterministic に保持する helper である。

## 2. Structured Specification

### Input
- **Description**: entity schema、token 列、既存 `semantic_roles`、現在の `target_entity`。
- **Type/Format**: `Dict[str, Any]`, `List[Dict[str, Any]]`, `Dict[str, Any]`, `str`

### Output
- **Description**: `property`, `display_property_resolution` を必要に応じて含む更新済み `semantic_roles`。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. explicit `property` / `display_property` / `field` がある場合は最優先候補にする。
2. それ以外は token の `surface` / `base` を候補として走査する。
3. 候補は `target_resolution.resolve_property_provenance` に渡し、schema 上の exact property / alias match だけを採用する。
4. unique owner のときは `display_property_resolution=schema_property` を付ける。
5. owner が複数でも current entity が exact scope なら `display_property_resolution=history_scope` を付ける。
6. exact match が無い場合は property metadata を発明しない。

## 3. Dependencies
- **Internal**:
  - `target_resolution`
  - `ir_generator`

## 4. Notes
- `DISPLAY` property provenance は schema-backed exact match に限定する。
- loop item continuity と組み合わせることで、`名前を表示する` のような child display が weak `item` ではなく `item.Name` へ落ちる。
