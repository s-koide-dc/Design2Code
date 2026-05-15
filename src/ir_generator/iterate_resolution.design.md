# iterate_resolution Design Document

## 1. Purpose

`iterate_resolution` は `ITERATE` role の collection source provenance と loop item continuity を deterministic に保持する helper である。

## 2. Structured Specification

### Input
- **Description**: 既存 `semantic_roles` と structural upstream source node id。
- **Type/Format**: `Dict[str, Any]`, `Optional[str]`

### Output
- **Description**: `structure_kind`, `iteration_source_resolution`, `iteration_source_node_id`, `iteration_item_entity`, `iteration_item_resolution`, `iteration_item_var`, `iteration_item_var_resolution` を含む更新済み `semantic_roles`。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. loop には `structure_kind=loop` を入れる。
2. explicit `item_entity` または `iteration_item_entity` がある場合は
   - `iteration_item_entity`
   - `iteration_item_resolution=explicit_item_entity`
   を保持する。
3. explicit `item_var` または `iteration_item_var` がある場合は
   - `iteration_item_var`
   - `iteration_item_var_resolution=explicit_item_var`
   を保持する。
4. explicit `source_var` がある場合は `iteration_source_resolution=source_var` を付ける。
5. explicit source が無く structural upstream collection がある場合は
   - `iteration_source_node_id`
   - `iteration_source_resolution=input_link_collection`
   を付ける。
6. upstream collection の inner type か直前 collection entity が確定している場合は `iteration_item_entity` を保持する。
7. explicit source がある場合は structural source で上書きしない。

## 3. Dependencies
- **Internal**:
  - `ir_generator`

## 4. Notes
- item entity は explicit metadata か deterministic な collection inner type / history collection entity に限定して保持する。
- loop item continuity は `context history` 側にも引き継がれ、nested child が weak `Item` のままでも exact item entity を history fallback として読めるようにする。
- explicit item alias がある場合は downstream loop consumer が generic `item` ではなく同じ alias を `foreach` item 名として使えるようにする。
- downstream は `iteration_source_node_id` を見て latest collection ではなく exact upstream collection を選び、必要なら `iteration_item_entity` を item 型として優先する。
