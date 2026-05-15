# Resolution Provenance Model

## 1. Purpose

この文書は、`CALCULATE` で導入した「解決結果そのもの」ではなく「その解決由来を保持する」設計を、`CHECK`, `FILTER`, `RETURN`, `TRANSFORM` へどう拡張するかを定義するためのものである。

ここでの狙いは metadata の追加そのものではない。downstream が過剰具体化を避けるために、どの解決が強く、どの解決が弱いかを deterministic に読めるようにすることが目的である。

## 2. Core Position

今後の provenance metadata は、次の形で統一して考える。

1. `resolved value`
2. `resolution provenance`

たとえば `CALCULATE` では、

- `target_entity = Product`
- `entity_resolution = unique_owner`
- `calculate_target_resolution = schema_property`

の 2 層で見ている。`CHECK` と `FILTER` でも同じく、「何になったか」と「なぜそうなったか」を分ける。

## 3. Why Extend Beyond CALCULATE

`CALCULATE` だけでは、IR metadata が downstream conservatism を制御できることは示せても、それが一般原理かどうかはまだ弱い。

次に価値が高いのは次の 2 論点である。

- `CHECK`
  - 何を判定対象にしたか
  - その subject をどの根拠で解決したか
- `FILTER`
  - どの predicate を適用するか
  - その predicate / collection をどの根拠で解決したか
- `RETURN`
  - 何を返すか
  - その return target をどの根拠で解決したか
- `TRANSFORM`
  - どの transform operation を適用するか
  - その transform source をどの根拠で解決したか

## 4. CHECK Provenance

### 4.1 Target

`CHECK` で次に provenance を付ける対象は `check_subject` である。

### 4.2 Proposed Field

- `semantic_map.subject_resolution`

### 4.3 Allowed Values

- `explicit_subject`
  - step text や explicit metadata に subject が明示されている
- `quoted_literal`
  - `"config.json"` のような quoted literal から採った
- `schema_property`
  - schema / POCO property 逆引きで subject を持ち上げた
- `history_subject`
  - 直前文脈から subject を補った
- `default_subject`
  - 十分な根拠がなく `value` などの保守的 default に留めた

### 4.4 Initial Policy

- `explicit_subject`, `quoted_literal`, `schema_property`
  - downstream で強い解決として扱ってよい
- `history_subject`
  - exact-scope 限定で使う
- `default_subject`
  - property-aware concretization をしない

## 5. FILTER Provenance

### 5.1 Target

`FILTER` で provenance を付ける対象は 2 つある。

1. predicate
2. collection source

### 5.2 Proposed Fields

- `semantic_roles.predicate_resolution`
- `semantic_roles.collection_resolution`

### 5.3 Allowed Values

`predicate_resolution`:

- `explicit_ops`
  - `ops` や explicit semantic_roles で filter 操作が明示されている
- `logic_goal`
  - logic goal から比較条件を抽出した
- `schema_property`
  - property 名を schema / POCO 逆引きで特定した
- `history_predicate`
  - 直前文脈から predicate を補った
- `default_predicate`
  - 強い根拠がなく、粗い一般 predicate に留めた

`collection_resolution`:

- `explicit_input_link`
  - `input_refs` や明示 source で集合源が確定している
- `structural_parent`
  - loop / block の構造親から確定している
- `history_collection`
  - 文脈から直前 collection を採った
- `default_collection`
  - 根拠が弱く一般 context を採った

### 5.4 Initial Policy

- `explicit_ops`, `logic_goal`, `schema_property`
  - predicate-specific な `.Where(...)` を組み立ててよい
- `history_predicate`
  - 既知 scope 内でのみ使う
- `default_predicate`
  - property-specific filter を生成しない

## 6. Boundary Rules

この provenance model は、何でも説明するメタデータとしては使わない。

含めるもの:

- downstream の具体化強度を変える要因
- 同じ resolved value でも安全性が変わる要因

含めないもの:

- 単なる観測ログ
- 生成後にしか分からない派生状態
- runtime の一時的な都合だけで、仕様意味に戻れない情報

## 6.5 RETURN Provenance

### Target

`RETURN` で provenance を付ける対象は `return_value` である。

### Proposed Fields

- `semantic_roles.return_value`
- `semantic_roles.return_value_resolution`
- 必要なら `semantic_roles.return_source_node_id`

### Allowed Values

- `literal_boolean`
- `literal_null`
- `literal_numeric`
- `quoted_literal`
- `explicit_literal`
- `source_var`
- `input_link_var`

### Initial Policy

- `literal_*`, `quoted_literal`, `explicit_literal`, `source_var`
  - downstream で explicit return として扱ってよい
- `input_link_var`
  - exact upstream node 限定で返却変数を解決してよい
- metadata が無い場合
  - typed latest-var fallback に留める

## 6.6 TRANSFORM Provenance

### Target

`TRANSFORM` で provenance を付ける対象は 2 つである。

1. operation
2. source

### Proposed Fields

- `semantic_roles.transform_op_resolution`
- `semantic_roles.transform_source_resolution`
- 必要なら `semantic_roles.transform_source_node_id`

### Allowed Values

`transform_op_resolution`:

- `explicit_ops`

`transform_source_resolution`:

- `source_var`
- `input_link_var`

### Initial Policy

- `explicit_ops`
  - downstream で specialized transform path を使ってよい
- `source_var`
  - explicit source をそのまま使ってよい
- `input_link_var`
  - exact upstream node 限定で transform source var を解決してよい
- metadata が無い場合
  - `active_scope_item` / binder fallback に留める

## 7. Canonical Reading Rule

今後 provenance metadata を読むときは、次の順を統一する。

1. `spec_role`
2. role-specific resolved value
3. role-specific resolution provenance
4. その provenance に応じた downstream policy

`CALCULATE` なら:

- `spec_role = CALCULATE`
- `target_entity = Product`
- `entity_resolution = unique_owner`

`CHECK` なら:

- `spec_role = CHECK`
- `check_subject = config.json`
- `subject_resolution = quoted_literal`

`FILTER` なら:

- `spec_role = FILTER`
- `property = Points`
- `predicate_resolution = logic_goal`

`RETURN` なら:

- `spec_role = RETURN`
- `return_value = true`
- `return_value_resolution = literal_boolean`

## 8. Minimal Implementation Order

順番は次の通りに固定する。

1. 研究文書で provenance 種別を定義する
2. benchmark case を追加する
3. IRGenerator で metadata を保持する
4. downstream で conservatism policy を最小適用する

この順を崩すと、また局所修正が先行して研究上の境界が曖昧になる。

## 9. Immediate Next Cases

次に追加すべき補助ケースは 3 つで十分である。

1. `FILTER` predicate provenance case
   - property 比較が logic goal 由来なのか explicit ops 由来なのかを見分ける
2. `CHECK` subject provenance case
   - quoted literal 由来なのか history subject 由来なのかを見分ける
3. `RETURN` source provenance case
   - literal return なのか input-link 由来なのかを見分ける

## 10. Immediate Decision

次段では `entity_resolution` を汎用化するのではなく、`CHECK` は `subject_resolution`、`FILTER` は `predicate_resolution` / `collection_resolution` として role ごとに分ける。これが最小で、かつ downstream policy に直結する。
