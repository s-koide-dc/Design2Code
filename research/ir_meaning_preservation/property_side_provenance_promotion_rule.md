# Property-Side Provenance Promotion Rule

## 1. Purpose

この文書は、`CHECK` と `FILTER` において property-side provenance を `explicit_subject` / `logic_goal` のような表層段階から、`schema_backed` または `history_based` へどう持ち上げるかを定義するためのものである。

`provenance_strength_boundary_observation.md` で見えた問題は明確である。

- `CHECK` は comparison metadata を持てているが、`subject_resolution` が property owner resolution まで上がっていない
- `FILTER` は collection provenance を持てているが、`predicate_resolution` が property-side strength へ上がっていない

したがって次段では、「property をどう読めたか」を role 横断で昇格させる最小原理を固定する。

## 2. Core Position

ここで昇格させたいのは `CHECK` や `FILTER` 自体ではない。すでに role は立っている。

次に昇格させる対象は、次の property-side provenance である。

- `CHECK.subject_resolution`
- `FILTER.predicate_resolution`

目的は、表層文面から抽出した property token を、そのまま強い根拠だと見なすことではない。

最低でも次の 3 層を分ける。

1. lexical property token
2. canonical property candidate
3. property provenance strength

## 3. Problem Statement

現状の観測では、次の形で情報が潰れている。

### 3.1 `CHECK`

- `在庫が 0 より大きい`
  - `check_subject = 在庫`
  - `subject_resolution = explicit_subject`
- `合計金額が 100 より大きい`
  - `check_subject = 合計金額`
  - `subject_resolution = explicit_subject`

つまり、「property が文面にあった」ことは分かっても、

- schema 上で一意か
- current target scope に閉じて解決したのか
- unresolved のままか

が区別できない。

### 3.2 `FILTER`

- `在庫が 0 より大きい商品を抽出する`
  - `property = 在庫`
  - `predicate_resolution = logic_goal`
- `合計金額が 100 より大きい注文を抽出する`
  - `property = 金額`
  - `predicate_resolution = logic_goal`

こちらも collection 側は取れているが、property 側の強さが区別できない。

## 4. Promotion Goal

最小目標は次の 2 点である。

1. unique owner なら `schema_backed` へ持ち上げる
2. global には曖昧でも current scope に閉じれば決まるなら `history_based` へ持ち上げる

逆に、次はやらない。

- lexical token だけで schema-backed 扱いする
- fuzzy な文字列一致で property owner を決める
- global reverse lookup を history-based の代わりに使う

## 5. Canonical Promotion Inputs

property-side promotion は、次の 3 種の入力だけを使う。

### 5.1 Lexical Property Token

文面から得られた property 候補。

例:

- `在庫`
- `合計金額`
- `Stock`
- `Total`

これは昇格の出発点だが、単独では強い根拠にならない。

### 5.2 Canonical Property Mapping

schema / entity property から得られる canonical property 候補。

例:

- `在庫` -> `Stock`
- `合計金額` -> `Total`

ここで重要なのは、単なる語彙一致ではなく、既存の entity/property model で deterministic に説明できるかどうかである。

初期実装では、canonical property mapping は schema に明示された property 名または property alias の exact match に限定する。

### 5.3 Scope Constraint

property をどの entity / collection scope で読むか。

対象は次の通り。

- `CHECK`
  - current `target_entity`
  - direct upstream value
- `FILTER`
  - current collection target
  - direct `input_link` collection

## 6. Promotion Rules

### Rule A: Canonical + Unique Owner -> `schema_backed`

次の 3 条件を同時に満たすとき、property-side provenance を `schema_backed` へ上げてよい。

1. lexical property token から canonical property が決まる
2. canonical property の owner entity が schema 上で一意に決まる
3. current role context と矛盾しない

適用結果:

- `CHECK`
  - `subject_resolution = schema_property`
  - `check_subject = <canonical property>`
- `FILTER`
  - `predicate_resolution = schema_property`
  - `property = <canonical property>`

### Rule B: Canonical + Exact Scope Only -> `history_based`

次の 4 条件を同時に満たすとき、property-side provenance を `history_based` へ上げてよい。

1. lexical property token から canonical property 候補が得られる
2. global schema では owner entity が一意に決まらない
3. current exact scope の中では 1 候補に絞れる
4. その解決に global reverse lookup を使っていない

適用結果:

- `CHECK`
  - `subject_resolution = history_subject`
  - `check_subject = <canonical property>`
- `FILTER`
  - `predicate_resolution = history_predicate`
  - `property = <canonical property>`

### Rule C: Canonicalization Fails -> Stay Weak

次のいずれかの場合は昇格しない。

- canonical property が決まらない
- current scope 内でも複数候補のまま
- current role context と矛盾する

この場合:

- `CHECK` は `explicit_subject` または `default_subject` に留める
- `FILTER` は `logic_goal` または `default_predicate` に留める

## 7. Exact-Scope Rule For Property Promotion

この文書でいう exact scope は、`cross_role_provenance_design.md` の一般原理を property-side へ具体化したものである。

### 7.1 `CHECK`

許可:

- current `target_entity` が持つ property だけを見る
- direct upstream fetch / deserialized object に閉じた property candidate を使う

禁止:

- unrelated entity の property owner を探す
- 条件の外側にある previous entity へ飛ぶ
- global schema 全体から最初に見つかった owner を採用する

### 7.2 `FILTER`

許可:

- current collection target entity の property だけを見る
- direct `input_link` collection の element type に閉じた property candidate を使う

禁止:

- unrelated collection/entity の property owner を採る
- collection scope を跨いで shortcut path を選ぶ
- global reverse lookup で property owner を決め打ちする

## 8. Why This Is Not Cheap Matching

この設計は lexical property token を出発点にするが、token だけでは昇格しない。

昇格には必ず、

- canonical property mapping
かつ
- owner uniqueness または exact-scope uniqueness

が必要である。

したがって、単なるキーワード一致やスコアリングではない。

## 9. Expected Effect On Current Boundary Cases

### Case 18

- `在庫` は `Product.Stock` に一意対応できるなら `schema_property`
- `合計金額` は global には曖昧でも current scope=`Order` に閉じれば `Total` として `history_subject`

### Case 19

- `在庫` は `Product.Stock` に一意対応できるなら `schema_property`
- `合計金額` は current collection scope=`Order` に閉じれば `history_predicate`

## 10. Minimal Implementation Boundary

最初の変更は `IRGenerator` に限定する。

触る候補:

- comparison/filter property token の canonicalization
- exact-scope 内 property owner 決定
- `subject_resolution` / `predicate_resolution` の昇格

まだ触らない候補:

- downstream binder / synthesizer の policy 追加
- schema vocabulary の大規模拡張
- fuzzy alias 解決

## 11. Exit Condition

この設計が成立したと判断する条件は次の通りである。

1. `case_18` で `subject_resolution=schema_property` と `history_subject` が分かれる
2. `case_19` で `predicate_resolution=schema_property` と `history_predicate` が分かれる
3. weak case は `explicit_subject` / `logic_goal` に留まる
4. global reverse lookup による誤昇格が出ない

## 12. Immediate Next Step

次にやるべきことは、この規則を `IRGenerator` の property resolution helper 群へ最小実装し、`case_18` / `case_19` と既存 provenance ケースで回帰確認することである。
