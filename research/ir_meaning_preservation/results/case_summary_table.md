# Case Summary Table

| Case | Title | Benchmark Role | Primary Failure | Secondary Failure |
|---|---|---|---|---|
| 01 | StdinToStdoutTransform | 最小の直列変換ケース | `Intent Drift` | `Under-Spec Capture` |
| 02 | ComplexLinqSearch | JSON 読み込みと多段フィルタ連鎖の確認 | `Source Drift` | `Intent Drift` |
| 03 | BatchProcessProducts | 最小の `LOOP` 構造確認 | `Under-Spec Capture` | `Source Drift` |
| 04 | RobustConfigLoader | `CONDITION / ELSE / END` を含む最小分岐ケース | `Dependency Loss` | `Intent Drift` |
| 05 | SyncExternalData | `http` と `db` を跨ぐ複合同期ケース | `Intent Drift` | `Under-Spec Capture` |
| 06 | Check Exists File | `exists_check` の最小ケース | `Under-Spec Capture` | `None` |
| 07 | Check Null Guard | `null_check` の最小ケース | `Under-Spec Capture` | `None` |
| 08 | Check Numeric Comparison | `comparison_check` の最小ケース | `Under-Spec Capture` | `None` |
| 09 | Condition Branch Dependency | `CONDITION` 配下の `first-child` / `second sibling` | `Under-Spec Capture` | `None` |
| 10 | Loop Body Dependency | `LOOP` 配下の `first-child` / `second sibling` / `nested child` | `Intent Drift` | `Under-Spec Capture` |
| 11 | Wrapper Scope Dependency | `WRAPPER` 配下の `first-child` / `second sibling` / `nested child` | `Under-Spec Capture` | `None` |
| 12 | Calculate With Target Hint | explicit target hint を持つ `CALCULATE` | `Under-Spec Capture` | `None` |
| 13 | Calculate Without Target Hint | implicit phrase のみを持つ `CALCULATE` | `Intent Drift` | `Under-Spec Capture` |
| 14 | Calculate Ambiguous Property Owner | ambiguous property owner を持つ `CALCULATE` | `None` | `None` |
| 15 | Calculate History Fallback Gap | upstream で `history_fallback` が純粋に観測できるかの確認 | none | none |
| 16 | Filter Predicate Provenance | `FILTER` に対する `predicate_resolution` / `collection_resolution` の観測 | none | none |
| 17 | Check Subject Provenance | `CHECK` に対する `subject_resolution` の観測 | none | none |
| 18 | Check Provenance Strength Boundary | `CHECK` の `subject_resolution` と exact-scope rule の境界観測 | none | none |
| 19 | Filter Provenance Strength Boundary | `FILTER` の `predicate_resolution` と exact-scope rule の境界観測 | none | none |
| 20 | Schema Alias Supplied Canonicalization | alias supply model と property-side provenance promotion の結合確認 | none | none |
| 21 | Schema Alias Missing Weak Retention | alias supply failure と provenance promotion failure の切り分け | none | none |
| 22 | Allowed Alias Admission | `schema_alias_coverage_policy` の admission 側の検証 | none | none |
| 23 | Disallowed Generic Alias Rejection | `schema_alias_coverage_policy` の rejection 側の検証 | none | none |
| 24 | Conditional Alias With Owner Explanation | `schema_alias_coverage_policy` における `conditionally allowed` admission の検証 | none | none |
| 25 | Generic Abbreviation Rejection | `schema_alias_coverage_policy` における conditional alias rejection の検証 | none | none |
| 26 | Legacy Field Bridge Admission | `schema_alias_coverage_policy` における `legacy field bridge` category の admission 検証 | none | none |
| 27 | Admissible But Deferred Alias | `schema_alias_admission_threshold.md` の `admissible but deferred` 状態の検証 | none | none |
| 28 | Repeated Spec Use Promotes Alias | `schema_alias_admission_threshold.md` の `Repeated Spec Use` 閾値の検証 | none | none |
| 29 | Cross-Case Relevance Threshold | `schema_alias_admission_threshold.md` の `Cross-Case Relevance` 閾値の検証 | none | none |
| 30 | Downstream Impact Threshold | `schema_alias_admission_threshold.md` の `Downstream Impact` 閾値の検証 | none | none |
| 31 | External Compatibility Threshold | `schema_alias_admission_threshold.md` の `External Compatibility` 閾値の検証 | none | none |
