# Provenance Strength Policy Matrix

## 1. Purpose

この文書は、`CHECK`, `FILTER`, `CALCULATE` に共通する provenance-strength を、downstream の許可操作と禁止操作へ直接対応付けるための matrix である。

`cross_role_provenance_design.md` では設計原理を定義した。この文書では、その原理を `どの strength なら何をしてよいか` という判定表へ落とす。

目的は 2 つある。

1. 実装側で保守性 policy を増やす際の共通判断基準にする
2. 研究上、`weak provenance のとき何を抑制したか` を role 横断で説明可能にする

## 2. Canonical Strength Order

provenance-strength は次の順で強いものから弱いものへ並ぶ。

1. `explicit`
2. `schema_backed`
3. `history_based`
4. `default_or_ambiguous`

この順は単なる分類ではなく、許可される concretization の上限を決める順序として読む。

## 3. Global Policy

共通原理は次の 1 文で十分である。

`strength が弱くなるほど、cross-scope 推論を減らし、schema 依存の補完を止め、generic path または停止へ寄せる`

この原理をさらに operational に言い換えると、以下になる。

- `explicit`: role-specific shortcut を許可してよい
- `schema_backed`: schema 根拠のある concretization を許可してよい
- `history_based`: exact scope に閉じた補完だけ許可する
- `default_or_ambiguous`: generic path に留めるか、明示停止する

## 4. Cross-Role Matrix

| Strength | Common Rule | `CHECK` | `FILTER` | `CALCULATE` |
| --- | --- | --- | --- | --- |
| `explicit` | 明示指定に従って具体化してよい | property-aware condition 可 | property-aware `.Where(...)` 可 | entity / property concretization 可 |
| `schema_backed` | schema 根拠がある範囲で具体化してよい | schema-backed property lifting 可 | schema-backed property predicate 可 | owner entity への持ち上げ可 |
| `history_based` | exact scope に限定して補完可 | exact target scope 内だけ subject/property 解決可 | strong shortcut 禁止、既知 collection scope の generic logic path のみ可 | exact target entity 限定で concretization 可 |
| `default_or_ambiguous` | cross-scope 補完禁止、generic または停止 | generic expression に留める | property-aware filter 禁止、必要なら TODO 停止 | cross-entity fallback 禁止、必要なら TODO 停止 |

## 5. Allowed Operations By Strength

### 5.1 `explicit`

許可:

- direct field / property concretization
- role-specific shortcut path
- named target への直接 binding

禁止:

- 特になし

ただし explicit でも、他 role の metadata を横断して勝手に補完してよいわけではない。明示情報と矛盾する再解釈は禁止する。

### 5.2 `schema_backed`

許可:

- schema 上で一意に説明できる property lookup
- owner entity の deterministic lifting
- typed structure に閉じた binding

禁止:

- schema で一意に決まらない候補への片寄せ
- history や lexical fallback を優先した上書き

### 5.3 `history_based`

許可:

- exact target scope に限定した補完
- 直前ノードや同一構造ブロックからの deterministic 継承
- generic logic path を使った保守生成

禁止:

- global reverse lookup
- cross-entity / cross-collection fallback
- schema-backed shortcut への自動昇格

`history_based` は「弱いので全部止める」ではなく、「scope を狭く保ったまま最低限だけ進める」と読む。

### 5.4 `default_or_ambiguous`

許可:

- generic expression
- placeholder / TODO stop
- non-committal metadata retention

禁止:

- property-aware concretization
- owner/entity の勝手な選択
- shortcut path の使用

## 6. Exact-Scope Rule

`history_based` の扱いで重要なのは、exact scope をどう読むかである。

この研究では当面、exact scope を次のように定義する。

- `CHECK`
  - current `target_entity`
  - current node が直接依存する upstream value
- `FILTER`
  - current `input_link` が指す collection
  - current structure 内で継続している collection context
- `CALCULATE`
  - current `target_entity`
  - no-history base inference の外側で、明示的に継承された直近 entity

逆に、以下は exact scope に含めない。

- repo 全体の schema からの無制限 reverse lookup
- unrelated previous entity
- weak lexical hint だけに基づく property owner 推定

## 7. Mapping To Current Field Values

### 7.1 `CHECK`

- `explicit_subject` -> `explicit`
- `quoted_literal` -> `explicit`
- `schema_property` -> `schema_backed`
- `history_subject` -> `history_based`
- `default_subject` -> `default_or_ambiguous`

### 7.2 `FILTER`

`predicate_resolution`:

- `explicit_ops` -> `explicit`
- `logic_goal` -> `explicit`
- `schema_property` -> `schema_backed`
- `history_predicate` -> `history_based`
- `default_predicate` -> `default_or_ambiguous`

`collection_resolution`:

- `explicit_input_link` -> `explicit`
- `structural_parent` -> `schema_backed`
- `history_collection` -> `history_based`
- `default_collection` -> `default_or_ambiguous`

### 7.3 `CALCULATE`

- `explicit_entity` -> `explicit`
- `unique_owner` -> `schema_backed`
- `history_fallback` -> `history_based`
- `ambiguous` -> `default_or_ambiguous`

## 8. Current Implementation Alignment

現時点の実装は、この matrix と次のように整合している。

- `CHECK`
  - `history_subject`: exact target scope 内だけ property 解決を許可
  - `default_subject`: generic condition に留める
- `FILTER`
  - `history_*`: strong shortcut を使わず generic logic path に留める
  - `default_*`: property-aware filter を作らず TODO 停止
- `CALCULATE`
  - `history_fallback`: exact target entity 限定
  - `ambiguous`: cross-entity fallback を止め、必要なら TODO 停止

したがって、この matrix は新しい理想論ではなく、すでに入った PoC 実装を role 横断で読めるようにした整理である。

## 9. Research Claim Supported By The Matrix

この matrix により、次の主張がしやすくなる。

1. provenance metadata は観測情報ではなく、concretization 上限を決める制御変数である
2. role ごとに field 名が異なっても、strength order と exact-scope rule で共通説明できる
3. deterministic conservatism は role ごとの場当たり停止ではなく、strength monotonicity に基づく

## 10. Immediate Next Step

次にやるべきことは、`exact scope` 判定をさらに形式化して、少なくとも次の 2 点を benchmark で確認することである。

1. `history_based` が誤って global reverse lookup に滑らないこと
2. `schema_backed` と `history_based` の境界がケース比較で再現できること
