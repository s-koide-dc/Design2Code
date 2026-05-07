# Provenance Strength Boundary Observation

## Scope

この文書は、`provenance_strength_policy_matrix.md` で定義した `schema_backed` と `history_based` の境界が、現行 IR でどこまで観測できるかを確認するための初回観測結果である。

対象:

- `case_18_check_provenance_strength_boundary`
- `case_19_filter_provenance_strength_boundary`

## Summary

### Case 18: Check Provenance Strength Boundary

- Observed IR:
  - `step_2` は `comparison_check`
  - `step_6` も `comparison_check`
- Preserved metadata:
  - `check_kind`
  - `check_subject`
  - `check_operator`
  - `check_value`

Reading:

- `CHECK` 自体と comparison metadata は保持された
- `step_2` は `在庫 -> Stock` に canonical 化され、`subject_resolution=schema_property`
- `step_6` は `合計金額 -> Total` に canonical 化され、`subject_resolution=history_subject`
- したがって `CHECK` の property-side provenance は、schema-backed と exact-scope history-based を比較可能な形で観測できるようになった

### Case 19: Filter Provenance Strength Boundary

- Observed IR:
  - `step_2` は `LINQ/FILTER`
  - `step_4` も `LINQ/FILTER`
- Preserved metadata:
  - `property`
  - `predicate_resolution`
  - `collection_resolution`

Reading:

- `FILTER` への昇格自体は両方で成立した
- `collection_resolution=explicit_input_link` は両方で保持された
- `step_2` は `在庫 -> Stock` に canonical 化され、`predicate_resolution=schema_property`
- `step_4` は `合計金額 -> Total` に canonical 化され、`predicate_resolution=history_predicate`
- したがって `FILTER` の property-side provenance も、schema-backed と exact-scope history-based を比較可能な形で観測できるようになった

## Cross-Case Interpretation

境界ケースの初回観測から、次のことが言える。

1. explicit schema alias を前提にすれば、property-side provenance を canonical property まで deterministic に持ち上げられる
2. その上で、unique owner は `schema_backed`、global には曖昧でも current scope に閉じるものは `history_based` として分離できる
3. つまり `exact scope` の control policy だけでなく、その上流観測である property-side provenance も role 横断で成立し始めた

言い換えると、`exact scope` の control policy と property-side provenance の観測層が、少なくとも explicit alias を持つ schema に対しては接続できた。

## Immediate Conclusion

次段で優先すべきなのは次の 2 点である。

1. alias を持たない lexical property token をどこまで deterministic に canonical 化できるかを設計する
2. branch 内 semantic continuity のように、property provenance 以外にまだ弱い metadata を切り分ける

研究の流れとしては、property-side provenance promotion の PoC は成立したので、次は alias 供給モデルと non-property metadata の残課題を分けて詰めるのが自然である。
