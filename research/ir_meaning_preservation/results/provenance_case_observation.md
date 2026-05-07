# Provenance Case Observation

## Scope

この文書は、`resolution_provenance_model.md` で定義した provenance metadata が、現行 IR でどこまで観測できるかを確認するための初回観測結果である。

対象:

- `case_16_filter_predicate_provenance`
- `case_17_check_subject_provenance`

## Summary

### Case 16: Filter Predicate Provenance

- Observed IR: `step_2` は `LINQ/FILTER`
- Preserved metadata:
  - `semantic_roles.property=Points`
  - `predicate_resolution=logic_goal`
  - `collection_resolution=explicit_input_link`

Reading:

- collection dependency は `input_link=step_1` として残っている
- `FETCH` に先着した曖昧語彙でも、predicate logic goal と upstream collection context が揃えば `LINQ/FILTER` へ巻き戻せる
- したがって `FILTER` provenance は、少なくとも logic-goal / explicit-input-link の範囲では IR field 上で観測可能になった

### Case 17: Check Subject Provenance

- Observed IR:
  - `step_1` は `exists_check`
  - `step_3` は `null_check`
- Preserved metadata:
  - `check_subject`
  - `subject_resolution`
  - `source_ref/source_kind` for file exists

Reading:

- `CHECK` 自体と `check_kind` は十分に保持されている
- `step_1` は `subject_resolution=quoted_literal`, `step_3` は `subject_resolution=explicit_subject` を保持した
- したがって `CHECK` provenance は、少なくとも quoted literal / explicit subject の範囲では IR field 上で観測可能になった

## Cross-Case Interpretation

現時点の観測から、`FILTER` と `CHECK` はどちらも provenance metadata の最初の段までは到達した。

- `FILTER`
  - role, property, predicate provenance, collection provenance まで保持できている
  - 次に残るのは `explicit_ops` / `history_collection` / `default_predicate` の境界確認である
- `CHECK`
  - role, subtype, subject provenance まで保持できている
  - 次に残るのは `history_subject` / `default_subject` の境界確認である

この段階では、`CALCULATE`, `CHECK`, `FILTER` の 3 role で provenance metadata を downstream conservatism へ接続できる見通しが立ったといえる。

## Immediate Conclusion

次段の優先順位は次の通りである。

1. `FILTER` は `explicit_ops` / `history_collection` / `default_predicate` を観測できる補助ケースを追加する
2. `CHECK` は `history_subject` / `default_subject` を観測できる補助ケースを追加する

研究の流れとしても、この順が最も自然である。

追記:

- `FILTER` 側の局所分析は `filter_fetch_collapse_analysis.md` に切り出した
- その後 `filter_promotion_rule.md` に沿って昇格規則を導入し、`case_16` では `FETCH` から `LINQ/FILTER` への巻き戻しが成立した
