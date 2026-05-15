# Cross-Role Provenance Design

## 1. Purpose

この文書は、`CHECK`, `FILTER`, `CALCULATE`, `RETURN`, `TRANSFORM` を横断して provenance metadata をどう統一的に扱うかを定義するためのものである。

ここでの目的は metadata を増やすこと自体ではない。役割ごとに保存された provenance を、同じ読み方と同じ保守性原理で downstream に接続できるようにすることが目的である。

## 2. Core Position

この研究で保持したいものは、単なる `resolved value` ではない。最低でも次の 3 層を分ける。

1. `spec_role`
2. role-specific resolved value
3. role-specific resolution provenance

たとえば `CALCULATE` なら、

- `spec_role = CALCULATE`
- `target_entity = Product`
- `entity_resolution = unique_owner`

の 3 層で読む。

同じ構造を `CHECK`, `FILTER`, `RETURN`, `TRANSFORM` にも適用する。

## 3. Canonical Reading Rule

今後 provenance metadata は、次の順で読むことを標準とする。

1. `spec_role`
2. resolved value
3. provenance field
4. provenance に対応する downstream policy

この順を固定することで、「何になったか」と「なぜそうなったか」と「どこまで具体化してよいか」が一貫して読める。

## 4. Cross-Role Canonical Schema

role ごとの field 名は完全には統一しない。代わりに、意味上の slot を統一する。

### 4.1 Canonical Slots

- `role_subject`
  - その role が作用する主対象
- `role_predicate`
  - その role が適用する条件や演算対象
- `role_source`
  - その role が依存する入力源や集合源
- `role_provenance`
  - 上記がどう解決されたか

### 4.2 Concrete Mapping

`CALCULATE`:

- `role_subject` -> `target_entity`
- `role_predicate` -> `property` / `target_hint`
- `role_source` -> `calculate_source_node_id` or explicit `source_var`
- `role_provenance` -> `entity_resolution`, `calculate_target_resolution`, `calculate_source_resolution`

`CHECK`:

- `role_subject` -> `check_subject`
- `role_predicate` -> `check_kind`, `check_operator`, `check_value`
- `role_source` -> `source_ref`, `source_kind`
- `role_provenance` -> `subject_resolution`

`FILTER`:

- `role_subject` -> collection target
- `role_predicate` -> `property`, predicate logic
- `role_source` -> input collection
- `role_provenance` -> `predicate_resolution`, `collection_resolution`

`RETURN`:

- `role_subject` -> `return_value`
- `role_predicate` -> return literal / source kind distinction
- `role_source` -> `return_source_node_id`
- `role_provenance` -> `return_value_resolution`

`TRANSFORM`:

- `role_subject` -> transform result
- `role_predicate` -> `ops`
- `role_source` -> `transform_source_node_id` or explicit `source_var`
- `role_provenance` -> `transform_op_resolution`, `transform_source_resolution`

## 5. Resolution Strength Lattice

共通設計として重要なのは、provenance を「ラベルの集合」ではなく「強さの順序」として読めることだ。

初期段階では、少なくとも次の 4 段階に整理できる。

1. `explicit`
   - 明示指定や直接記述に基づく
2. `schema_backed`
   - schema / property owner / typed structure に基づく
3. `history_based`
   - 直前文脈や構造文脈の継承に基づく
4. `default_or_ambiguous`
   - 根拠が弱い、または候補が複数ある

これは field 名そのものではなく、各 provenance 値がどの強さに属するかを読むための共通 lattice である。

## 6. Mapping To Existing Fields

### 6.1 CALCULATE

- `explicit_entity` -> `explicit`
- `unique_owner` -> `schema_backed`
- `history_fallback` -> `history_based`
- `ambiguous` -> `default_or_ambiguous`
- `schema_property` -> `schema_backed`
- `history_target` -> `history_based`
- `explicit_target` -> `explicit`
- `default_target` -> `default_or_ambiguous`
- `source_var` -> `explicit`
- `input_link_var` -> `history_based`
- `default_scope_var` -> `default_or_ambiguous`

### 6.2 CHECK

- `explicit_subject` -> `explicit`
- `quoted_literal` -> `explicit`
- `schema_property` -> `schema_backed`
- `history_subject` -> `history_based`
- `default_subject` -> `default_or_ambiguous`

### 6.3 FILTER

`predicate_resolution`:

- `explicit_ops` -> `explicit`
- `logic_goal` -> `explicit`
- `schema_property` -> `schema_backed`
- `history_predicate` -> `history_based`
- `default_predicate` -> `default_or_ambiguous`

`collection_resolution`:

- `explicit_input_link` -> `explicit`
- `structural_parent` -> `schema_backed` に近い構造的強解決
- `history_collection` -> `history_based`
- `default_collection` -> `default_or_ambiguous`

### 6.4 RETURN

- `literal_boolean` -> `explicit`
- `literal_null` -> `explicit`
- `literal_numeric` -> `explicit`
- `quoted_literal` -> `explicit`
- `explicit_literal` -> `explicit`
- `source_var` -> `explicit`
- `input_link_var` -> `history_based`

### 6.5 TRANSFORM

- `explicit_ops` -> `explicit`
- `source_var` -> `explicit`
- `input_link_var` -> `history_based`

## 7. Common Downstream Principle

downstream policy は role ごとに個別に見えても、原理としては次の 1 文に統一できる。

`provenance が弱くなるほど、具体化を減らし、cross-scope 推論を避け、停止寄りに振る舞う`

この原理を role ごとに読むと以下になる。

### 7.1 CALCULATE

- `explicit` / `schema_backed`: 通常具体化
- `history_based`: exact target 限定の保守具体化
- `default_or_ambiguous`: cross-entity fallback 禁止、必要なら TODO 停止
- source provenance も同様に、`source_var` / `input_link_var` がある場合だけ exact upstream var を使い、`default_scope_var` の場合は weak retention として `active_scope_item` に留める

### 7.2 CHECK

- `explicit` / `schema_backed`: property-aware な条件式を許可
- `history_based`: exact scope 内でのみ subject 補完を許可
- `default_or_ambiguous`: generic `value` / null-based expression に留める

### 7.3 FILTER

- `explicit` / `schema_backed`: property-aware `.Where(...)` を許可
- `history_based`: 既知 collection scope に限定して predicate を適用
- `default_or_ambiguous`: property-specific filter を作らず、粗い filtering か停止寄りへ寄せる

### 7.4 RETURN

- `explicit`: literal return または明示 source var をそのまま返してよい
- `history_based`: `input_link` が指す exact upstream node に限定して返却先を解決してよい
- `default_or_ambiguous`: latest-var fallback か TODO 停止に留める

### 7.5 TRANSFORM

- `explicit`: explicit `ops` と explicit `source_var` をそのまま消費してよい
- `history_based`: exact upstream node に限定して transform source var を解決してよい
- `default_or_ambiguous`: `active_scope_item` / binder fallback に留める

## 8. What Is Common And What Must Stay Role-Specific

### 8.1 Common

- 読み順
- provenance strength の考え方
- downstream conservatism の単調原理
- `resolved value` と `provenance` を分ける方針

### 8.2 Role-Specific

- field 名
- exact provenance 値の vocabulary
- resolved value の shape
- downstream の具象コード形

ここを無理に全部統一すると、かえって role 固有の意味が潰れる。

## 9. Research Claim Enabled By This Design

この共通設計により、次の中間主張が可能になる。

1. provenance metadata は role ごとのローカルな小細工ではなく、cross-role に適用可能な設計原理である
2. metadata の追加は観測用途に留まらず、downstream conservatism を決定論的に制御する
3. `CHECK`, `FILTER`, `CALCULATE`, `RETURN`, `TRANSFORM` は field 名は異なっても、同一の「resolved value + provenance + policy」枠組みで説明できる

## 10. Immediate Next Step

この文書の次にやるべきことは、次のどちらかである。

1. `CHECK` と `FILTER` にも provenance-strength に応じた downstream policy を最小導入する
2. この文書を 1 ページ版に圧縮して、研究の主張としてより短く再整理する

研究の流れとしては、まず 1 の方が筋が良い。

## 11. Current Implementation Status

この文書の設計に対して、現時点では少なくとも次の最小実装が入っている。

- `CALCULATE`
  - `entity_resolution` に応じて downstream concretization を制御
  - `calculate_source_resolution` がある場合、latest var fallback より前に exact upstream var を優先
- `CHECK`
  - weak `subject_resolution` のとき、comparison generation で schema-backed property lifting をしない
  - `history_subject` のとき、global reverse lookup ではなく exact target scope に限定して property resolution を許可
- `FILTER`
  - `default_predicate` / `default_collection` のとき、property-aware `.Where(...)` を組まず明示 TODO 停止へ送る
  - `history_predicate` / `history_collection` のとき、strong shortcut を使わず generic logic path に留める
- `RETURN`
  - `literal_*` / `quoted_literal` / `source_var` のとき、latest var fallback より前に explicit return を優先
  - `input_link_var` のとき、exact upstream node id から返却変数を限定解決

したがって、cross-role provenance design は文書上の概念に留まらず、少なくとも初期の downstream conservatism policy として実装に接続済みである。
