# Runtime / Schema / Policy Boundary

## Purpose

この文書は、`IR meaning preservation` 研究で繰り返し現れた

- runtime metadata
- schema knowledge
- policy judgment

の境界を 1 枚で固定するための最終圧縮である。

ここでの目的は、新しい規則を足すことではなく、
既存の実装・benchmark・運用文書を
`どの層の責務として読むべきか`
で整理することにある。

## Final Boundary Claim

この研究の最終主張は次の 1 文に圧縮できる。

`意味保存に必要な最小情報は runtime metadata として IR に保持し、canonical knowledge は schema に置き、admission や expansion の判断は policy として分離するのが、決定論性と保守性を両立する最小境界である。`

## 1. Runtime Layer

runtime 層の責務は、
`現在の specification step から決定論的に materialize できる metadata を IR に残すこと`
である。

ここに置くもの:

- `spec_role`
- role-specific resolved value
- source / target / subject / predicate / collection provenance
- structural continuity metadata
- downstream conservatism を切り替えるための resolution label

代表例:

- `CHECK`
  - `check_kind`
  - `check_subject`
  - `subject_resolution`
- `FILTER`
  - `predicate_resolution`
  - `collection_resolution`
- `CALCULATE`
  - `entity_resolution`
  - `calculate_source_resolution`
  - `calculate_target_resolution`
- `RETURN`
  - `return_value_resolution`
  - `return_source_node_id`
- `TRANSFORM`
  - `transform_source_resolution`
  - `transform_op_resolution`
- `ITERATE`
  - `iteration_source_resolution`
  - `iteration_item_entity`
  - `iteration_item_var`
- `WRAP`
  - `wrapper_kind`
  - retry / timeout / transaction metadata
  - default-policy provenance

runtime 層でやらないこと:

- alias を似ているから canonical property へ寄せる
- wrapper kind を自然文から広く推定する
- weak provenance を exact entity / exact property に勝手に昇格する

つまり runtime は、
`いま deterministic に言えることを明示する`
層であり、
`足りない情報を推測で埋める`
層ではない。

## 2. Schema Layer

schema 層の責務は、
`runtime が参照してよい canonical knowledge を宣言的に持つこと`
である。

ここに置くもの:

- entity/property ownership
- canonical property name
- admitted alias
- owner-confined field bridge

代表例:

- `Stock` が `Product` の property であること
- `Total` が `Order` / `Invoice` に属すること
- `在庫 -> Stock`
- `合計金額 -> Total`
- `受注額 -> OrderAmount`

schema 層でやらないこと:

- alias admission timing の判断
- provenance strength の最終評価
- weak runtime input を救うための ad hoc fallback

つまり schema は、
`何が canonical か`
を持つ層であり、
`いまそれを採用すべきか`
を決める層ではない。

## 3. Policy Layer

policy 層の責務は、
`schema に何を入れてよいか、weak metadata を downstream でどこまで許すか`
を決めることである。

ここに置くもの:

- alias admission timing
- provenance-strength ごとの許可/停止
- generic fallback と TODO stop の境界
- wrapper kind generalization を続けるかどうかの判断

代表例:

- `Hold For Evidence`
- `Repeated Spec Use`
- `Cross-Case Relevance`
- `Downstream Impact`
- `External Compatibility`

加えて、

- `ambiguous` target は stop する
- `history_based` は exact scope に限って許可する
- `default_target` は generic numeric-property fallback に落とさない

のような conservatism も policy 層で読む。

policy 層でやらないこと:

- runtime metadata そのものの materialization
- schema owner / alias の事実宣言

つまり policy は、
`許可境界を決める`
層であり、
`事実を抽出する`
層ではない。

## 4. Cross-Layer Reading

同じ role でも、読む順序は常に

1. runtime
2. schema
3. policy

でよい。

### 4.1 CALCULATE

runtime:

- `entity_resolution`
- `calculate_source_resolution`
- `calculate_target_resolution`

schema:

- property owner
- admitted alias

policy:

- weak target を stop するか
- ambiguous owner を保守停止するか

結論:

`CALCULATE` の問題は 1 本ではなく、
source, target, owner ambiguity, alias supply をこの 3 層で分担して閉じる。

### 4.2 CHECK / FILTER

runtime:

- `subject_resolution`
- `predicate_resolution`
- `collection_resolution`

schema:

- canonical property
- alias

policy:

- `schema_backed` と `history_based` の許可差
- `default_*` の停止条件

結論:

property-side provenance promotion は runtime 規則だが、
それが成立する前提は schema と policy に分かれている。

### 4.3 RETURN / TRANSFORM / ITERATE

runtime:

- exact source node
- item continuity
- explicit alias continuity

schema:

- property/entity bind に必要な canonical knowledge

policy:

- provenance が弱いときに latest-var fallback を許すか止めるか

結論:

この群では alias timing より、
`source continuity を exact に残し、weak なら weak と明示する`
ことが主眼になる。

### 4.4 WRAP

runtime:

- `wrapper_kind`
- retry / timeout / transaction metadata
- default-policy provenance

schema:

- 基本的には薄い

policy:

- non-explicit kind inference を許すか
- wrapper kind の一般化を続けるか

結論:

`WRAP` は schema 依存より policy 依存が強い role である。

## 5. Operational Consequence

この境界を採ると、変更時の問いも明確になる。

1. これは runtime metadata の追加か
2. schema admission の追加か
3. policy 境界の変更か

たとえば

- new alias 追加:
  - schema change
  - policy review 必須
- weak provenance の codegen 改善:
  - policy change
  - regression table 更新必須
- new resolution field 追加:
  - runtime change
  - downstream consumer と benchmark 更新必須

という読み方ができる。

## 6. What Remains Open

この境界を前提にした current open issue は限定的である。

- `WRAP` の non-explicit kind inference を runtime に入れるか
- cross-role quantitative comparison を policy/summary 層でどこまで要求するか
- final external report でこの 3 層をどこまで簡約するか

重要なのは、
これらは
`metadata をまだ発見できていない`
問題ではなく、
`どこで閉じるか`
の問題だということである。

## 7. Final Reading

この研究の成果は、
`IR を高精度にする単発の改善`
ではない。

より正確には、

- runtime には deterministic metadata を置く
- schema には canonical knowledge を置く
- policy には admission と conservatism の境界を置く

という 3 層分離を、benchmark・observed IR・実装・回帰運用まで含めて成立させたことにある。
