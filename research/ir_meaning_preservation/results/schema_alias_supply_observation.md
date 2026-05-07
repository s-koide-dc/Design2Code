# Schema Alias Supply Observation

## Scope

この文書は、`schema_alias_supply_model.md` に従って alias 供給の有無が observed IR にどう現れるかを比較するための初回観測結果である。

対象:

- `case_20_schema_alias_supplied_canonicalization`
- `case_21_schema_alias_missing_weak_retention`

## Summary

### Case 20: Alias-Supplied Canonicalization

- Observed IR:
  - `step_2` は `comparison_check`
  - `step_6` は `LINQ/FILTER`
- Preserved metadata:
  - `check_subject=Stock`
  - `subject_resolution=schema_property`
  - `property=Stock`
  - `predicate_resolution=schema_property`

Reading:

- schema alias `在庫 -> Stock` があると、`CHECK` / `FILTER` の両方で canonical property へ deterministic に上がる
- ここでは supply success と provenance promotion success が連続して成立している

### Case 21: Alias-Missing Weak Retention

- Observed IR:
  - `step_2` は `comparison_check`
  - `step_6` は `LINQ/FILTER`
- Preserved metadata:
  - `check_subject=在庫`
  - `subject_resolution=explicit_subject`
  - `property=在庫`
  - `predicate_resolution=logic_goal`

Reading:

- schema alias が無い場合、lexical property token は canonical property へ上がらない
- それでも `CHECK` / `FILTER` 自体は保持されるため、弱いのは role ではなく alias supply である

## Cross-Case Interpretation

この contrast から、次のことが明確になった。

1. `supply failure` と `promotion failure` は分離して観測できる
2. alias supply があると、同一 step でも `CHECK` / `FILTER` の property-side provenance が強化される
3. alias supply が無い場合、現行実装は weak retention に留まり、誤った canonicalization をしていない

つまり、property-side provenance の弱さをすべて promotion rule の責任に帰すのではなく、schema supply 層の有無として分けて説明できるようになった。

## Immediate Conclusion

次段で優先すべきなのは次の 2 点である。

1. alias coverage をどこまで `entity_schema` に持つべきかの実務境界を定義する
2. alias が無い lexical property token を、なお deterministic に canonical 化できる追加源があるかを検討する

研究の流れとしては、次に必要なのは「alias 追加」ではなく、「alias 追加の基準」をケース拡張で固めることだといえる。
