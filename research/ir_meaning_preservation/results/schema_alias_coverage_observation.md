# Schema Alias Coverage Observation

## Scope

この文書は、`schema_alias_coverage_policy.md` に従って alias coverage の admission / rejection 境界が observed IR にどう現れるかを比較するための初回観測結果である。

対象:

- `case_22_allowed_alias_admission`
- `case_23_disallowed_generic_alias_rejection`

## Summary

### Case 22: Allowed Alias Admission

- Observed IR:
  - `step_2` は `comparison_check`
  - `step_6` は `LINQ/FILTER`
- Preserved metadata:
  - `check_subject=Total`
  - `subject_resolution=history_subject`
  - `property=Total`
  - `predicate_resolution=history_predicate`

Reading:

- policy 上で許可される alias `合計金額 -> Total` は、`CHECK` / `FILTER` の両方で canonical property へ deterministic に上がった
- `Total` は複数 owner を持つため、結果は `schema_property` ではなく `history_*` に留まる
- つまり、coverage admission は canonicalization の許可であり、owner ambiguity を消すことまでは意味しない

### Case 23: Disallowed Generic Alias Rejection

- Observed IR:
  - `step_2` は `comparison_check`
  - `step_6` は `LINQ/FILTER`
- Preserved metadata:
  - `check_subject=金額`
  - `subject_resolution=explicit_subject`
  - `property=金額`
  - `predicate_resolution=logic_goal`

Reading:

- policy 上で拒否される generic alias `金額` は canonical property `Total` へ上がらなかった
- `CHECK` / `FILTER` 自体は保持されているため、弱いのは role ではなく alias admission である
- 現行実装は generic token を理由なく canonical property に寄せておらず、rejection policy と整合している

## Cross-Case Interpretation

この contrast から、次のことが明確になった。

1. alias supply が存在していても、coverage policy で admission されない token は canonicalization されない
2. alias coverage の成功は `schema_property` を保証せず、owner ambiguity が残る場合は `history_*` に留まる
3. `allowed alias` と `disallowed generic token` は observed IR 上で明確に分離できる

つまり、property-side provenance の弱さを単なる schema 不足と見るのではなく、`supply existence` と `coverage admission` を別段として説明できるようになった。

## Immediate Conclusion

次段で優先すべきなのは次の 2 点である。

1. coverage policy の `Tier 2` 候補が本当に benchmark-driven need を満たすかを追加ケースで確かめる
2. alias を追加せずに generic token を canonical 化したくなる圧力に対して、rejection rule をどこまで downstream policy と一貫させるかを整理する

研究の流れとしては、次に必要なのは canonicalization の拡張そのものではなく、`どの lexical token を schema alias に入れてよいか` の実務基準を benchmark で閉じることだといえる。
