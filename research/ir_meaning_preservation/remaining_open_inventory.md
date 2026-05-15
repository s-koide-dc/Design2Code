# Remaining Open Inventory

## Purpose

この文書は、`IR meaning preservation` 研究において

- すでに十分閉じた role / metadata
- かなり閉じたが一般化は保留している論点
- まだ明示的に残課題として扱う論点

を分けて、次の着手順を見失わないようにするための棚卸しである。

## 1. Substantially Closed Roles

次の role は、少なくとも

- upstream IR metadata
- downstream bridge / conservatism
- regression table
- benchmark または observed IR

まで揃っている。

### 1.1 CHECK

- `check_kind`
- `check_subject`
- `subject_resolution`

状態:

- substantially closed

残り:

- 定量比較は薄いが、研究上の主要未解決ではない

### 1.2 FILTER

- promotion rule
- `predicate_resolution`
- `collection_resolution`
- weak/default provenance に対する保守停止

状態:

- substantially closed

残り:

- broader quantitative comparison のみ

### 1.3 CALCULATE

- promotion
- `entity_resolution`
- `calculate_source_resolution`
- `calculate_target_resolution`
- ambiguous / weak target の保守停止

状態:

- substantially closed

残り:

- benchmark 上の定量比較
- role 横断 summary への圧縮

### 1.4 RETURN

- `return_value`
- `return_value_resolution`
- `return_source_node_id`
- literal / input-link / weak retention の境界

状態:

- substantially closed

残り:

- cross-role comparison のみ

### 1.5 TRANSFORM

- weak-intent bridge
- `transform_op_resolution`
- `transform_source_resolution`
- exact upstream source 優先

状態:

- substantially closed

残り:

- broader benchmark coverage

### 1.6 ITERATE

- `iteration_source_resolution`
- `iteration_item_entity`
- `iteration_item_var`
- nested child property continuity

状態:

- substantially closed

残り:

- branch-local item refinement のさらなる細分化は optional

### 1.7 WRAP

- deterministic `retry`
- explicit `timeout`
- explicit `transaction`
- retry default-policy provenance

状態:

- substantially closed

残り:

- non-explicit wrapper-kind inference は未実施
- wrapper kind の一般化は policy-level open issue

## 2. Stable But Not Research Focus

次の role は runtime 上は比較的安定しているが、今回の研究では主要深掘り対象ではない。

- `FETCH`
- `PERSIST`
- `DESERIALIZE`
- `DISPLAY`

補足:

- `DISPLAY` は property-side provenance まで入っているため、weak role というより sink-side role として安定している
- `DESERIALIZE` も bridge 済みで、現在の open issue ではない

## 3. Open Issues

### 3.1 Wrapper Kind Generalization

残っている問い:

- `WRAP` を retry/timeout/transaction 以外へ広げるべきか
- そのとき explicit metadata だけで閉じるか、non-explicit inference を許すか

状態:

- open

理由:

- いまの研究は決定論性を優先しており、wrapper kind の自然言語推定をまだ入れていない

### 3.2 Cross-Role Quantification

残っている問い:

- role 改善を横断してどこまで定量比較するか

状態:

- open

理由:

- benchmark / observation / regression はあるが、定量比較はまだ summary-level claim より弱い

### 3.3 Generalization Boundary Statement

残っている問い:

- 「どこまでが runtime metadata で、どこからが schema/policy 層か」を最終主張としてどう圧縮するか

状態:

- open

理由:

- 実装はかなり閉じたが、外向け主張としての圧縮がまだ可能

## 4. Recommended Order

次に進める順序は次のとおりでよい。

1. 新しい role を広げる前に、closed role 群の横断 summary を更新する
2. wrapper kind generalization を本当に続けるか判断する
3. 必要なら定量比較または外向け報告に圧縮する

## 5. Current Reading

現在の研究は、

- `主要 role の metadata 化`
- `downstream conservatism への接続`
- `運用回帰の整備`

までは十分進んでいる。

したがって、次の価値は
`さらに role を増やすこと`
より
`どこで研究を閉じるかを明示すること`
にある。
