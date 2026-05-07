# Schema Alias Tier 2 Observation

## Scope

この文書は、`schema_alias_coverage_policy.md` における `Tier 2: Conditionally Allowed` の admission / rejection 境界が observed IR にどう現れるかを比較するための初回観測結果である。

対象:

- `case_24_conditional_alias_with_owner_explanation`
- `case_25_generic_abbreviation_rejection`
- `case_26_legacy_field_bridge_admission`

## Summary

### Case 24: Conditional Alias With Owner Explanation

- Observed IR:
  - `step_2` は `comparison_check`
  - `step_6` は `LINQ/FILTER`
- Preserved metadata:
  - `check_subject=OrderAmount`
  - `subject_resolution=schema_property`
  - `property=OrderAmount`
  - `predicate_resolution=schema_property`

Reading:

- policy 上で `Tier 2` admission が許可される alias `受注額 -> OrderAmount` は、`CHECK` / `FILTER` の両方で canonical property に上がった
- canonical property 自体が owner-confined なので、`history_*` ではなく `schema_property` まで上がっている
- つまり conditional alias でも、owner explanation と canonical non-ambiguity が揃えば deterministic canonicalization に使ってよい

### Case 25: Generic Abbreviation Rejection

- Observed IR:
  - `step_2` は `comparison_check`
  - `step_6` は `LINQ/FILTER`
- Preserved metadata:
  - `check_subject=額`
  - `subject_resolution=explicit_subject`
  - `property=額`
  - `predicate_resolution=logic_goal`

Reading:

- owner explanation を欠く generic abbreviation `額` は canonical property へ上がらなかった
- `CHECK` / `FILTER` 自体は保持されているため、弱いのは role ではなく alias admission 側である
- 現行実装は abbreviation を理由なく canonical property に寄せておらず、`Tier 2` rejection policy と整合している

### Case 26: Legacy Field Bridge Admission

- Observed IR:
  - `step_2` は `comparison_check`
  - `step_6` は `LINQ/FILTER`
- Preserved metadata:
  - `check_subject=OrderAmount`
  - `subject_resolution=schema_property`
  - `property=OrderAmount`
  - `predicate_resolution=schema_property`

Reading:

- policy 上で `Tier 2` admission が許可される `legacy field bridge` alias `伝票金額 -> OrderAmount` も、`CHECK` / `FILTER` の両方で canonical property に上がった
- `compound-part shorthand` だった `case_24` と同じく、canonical property が owner-confined なので `schema_property` まで上がっている
- したがって category の違いよりも、owner explanation と canonical non-ambiguity の充足が admission の本体である

## Cross-Case Interpretation

この contrast から、次のことが明確になった。

1. `Tier 2` alias は category 名よりも、owner explanation と benchmark need の有無で admission される
2. `compound-part shorthand` と `legacy field bridge` は、どちらも owner-confined なら `schema_property` まで上げられる
3. generic abbreviation は alias supply が存在しても admission されず、weak retention に留まる

つまり、`Tier 2` は category 列挙で決まるのではなく、deterministic 説明力が保てるかで切られていることを observed IR 上で示せた。

## Immediate Conclusion

次段で優先すべきなのは次の 2 点である。

1. owner-confined だが benchmark need が弱い alias をどう扱うか、coverage policy の admission threshold をもう一段詰める
2. `Tier 2` の `legacy field bridge` と `compound-part shorthand` のうち、どちらが schema maintenance cost を上げやすいかを別軸で整理する

研究の流れとしては、ここから先は alias 形式の追加ではなく、`Tier 2` admission の実務閾値を benchmark で具体化していく段階である。
