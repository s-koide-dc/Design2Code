# target_resolution Design Document

## 1. Purpose

`target_resolution` は property surface と entity schema を使って canonical property と owner entity を決定し、`CHECK`, `FILTER`, `CALCULATE` の provenance / resolution を支える。

## 2. Structured Specification

### Input
- **Description**: `entity_schema`、property token、current entity、history。
- **Type/Format**: `Dict[str, Any]`, `Optional[str]`, `List[Dict[str, Any]]`

### Output
- **Description**: canonical property、owner entity 群、property provenance、`entity_resolution`。
- **Type/Format**: `Tuple[...]`, `List[str]`

### Core Logic
1. schema の property 定義から canonical property 名と alias 群を列挙する。
2. `resolve_canonical_property_name` は exact match のみで canonical property と owner entity 群を返す。
3. `find_property_owner_entities` は property owner entity 一覧を返す。
4. `resolve_property_provenance` は unique owner なら `schema_property`、current entity が owner 集合内にある場合は `history_scope` を返す。
5. `infer_calculate_target_entity` は property owners、current entity、role entity、history を使って `unique_owner`, `explicit_entity`, `ambiguous`, `history_fallback` を決める。
6. alias は schema から供給されたものだけを使い、runtime 側で推測拡張しない。

### Test Cases
- **Happy Path**:
  - **Scenario**: `Stock` が 1 entity にのみ存在する。
  - **Expected Output**: `unique_owner`。
- **Edge Cases**:
  - **Scenario**: `Total` が複数 entity に存在する。
  - **Expected Output / Behavior**: `ambiguous`。
  - **Scenario**: alias が schema に無い。
  - **Expected Output / Behavior**: canonical property を返さない。

## 3. Dependencies
- **Internal**: なし
- **External**: なし
