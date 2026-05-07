# Role Weakening Regression Table

## Purpose

この表は、`role weakening` に関する主要 role を
回帰確認の観点で横断比較するための基準表である。

`role_mapping_matrix.md` は初期ケースの観測結果、
`regression_run_2026_05_07_metadata_baseline.md` は 1 回分の運用記録、
この文書はそれらを日常の regression 観点へ圧縮した一覧である。

## Reading Rule

- `spec_role` は仕様意味の保持対象
- `runtime bridge / consumer` は downstream でその role をどこが読むか
- `Baseline Status` は 2026-05-07 時点の current implementation を表す
- `Regression Check` は変更時に最低限確認すべき観点

## Table

| `spec_role` | Main Drift Risk | Runtime Bridge / Consumer | Baseline Status | Key Evidence | Regression Check |
| --- | --- | --- | --- | --- | --- |
| `FETCH` | source-only I/O role へ縮退 | `ActionSynthesizer`, fetch/io handlers | Stable | `role_mapping_matrix.md`, `results/failure_mapping.md` | `source_kind`, `source_ref`, `FETCH` dispatch が保たれるか |
| `DESERIALIZE` | `ACTION` / `FETCH` へ吸収 | `ActionSynthesizer` -> `JSON_DESERIALIZE` | Stable after bridge | `focused_role_analysis.md`, `results/role_mapping_matrix.md` | auto `JSON_DESERIALIZE` node と `spec_role=DESERIALIZE` が残るか |
| `FILTER` | lexical `FETCH` へ崩落、または `ACTION` 圧縮 | `ActionSynthesizer` -> `LINQ`, LINQ handlers | Stable with promotion rule | `filter_fetch_collapse_analysis.md`, `case_16`, `provenance_case_observation.md` | predicate/context 条件なしで昇格しないか、逆に必要ケースで `LINQ` に上がるか |
| `TRANSFORM` | `ACTION` へ圧縮 | display/transform handlers, generic action path | Partially stable | `role_mapping_matrix.md` | `ops` 付き transform が generic action に落ちていないか |
| `CHECK` | `ACTION` へ圧縮、subject provenance 消失 | `SemanticBinder` condition generation | Stable with metadata path | `check_role_refinement.md`, `results/check_case_observation.md`, `case_17` | `check_kind`, `check_subject`, `subject_resolution` が保持されるか |
| `CALCULATE` | `GENERAL/ACTION` へ弱化、target 解決喪失 | `ActionSynthesizer` -> `CALC`, `calc_ops.py` | Stable with guarded concretization | `calculate_promotion_rule.md`, `results/calculate_case_observation.md` | `entity_resolution` が適切か、ambiguous case で過剰具体化しないか |
| `DISPLAY` | `void` / generic action へ弱化 | display/transform handlers | Stable | `role_mapping_matrix.md` | display intent が sink として残るか |
| `PERSIST` | write intent は残るが upstream provenance 消失 | file/io/persist path | Stable | `role_mapping_matrix.md`, `results/failure_mapping.md` | scalar vs collection persist で bridge node 条件が崩れていないか |
| `RETURN` | `ACTION` へ圧縮 | return handler | Partially stable | `role_mapping_matrix.md` | literal return と chained return が誤連結しないか |
| `ITERATE` | runtime role に出ず構造だけ残る | loop handler | Stable on structure, weak on runtime role | `structural_role_bridge.md`, `results/structural_dependency_observation.md` | loop node の `spec_role=ITERATE` と child linkage が残るか |
| `WRAP` | wrapper semantics が単なる action に吸収 | structural handling in `IRGenerator` | Stable on structure | `structural_role_bridge.md`, `test_ir_generator` | wrapper node の `spec_role=WRAP` と child boundary が残るか |

## Current Interpretation

2026-05-07 時点では、
`CHECK`, `FILTER`, `CALCULATE`, `DESERIALIZE` は
metadata-driven bridge が入ったことで baseline は安定している。

一方で、次の role はまだ runtime 側で独立性が弱い。

- `TRANSFORM`
- `RETURN`
- `ITERATE`
- `WRAP`

ただしここで重要なのは、
runtime role 自体を無理に細分化することではなく、
`spec_role` と構造 metadata が保持され、
downstream が必要な箇所だけを読める状態を維持することである。

## Recommended Use

1. `IRGenerator` や promotion rule を触る前に、変更対象 role の行を先に確認する。
2. 変更後は `regression_run_template` に、この表の `Regression Check` を転記して使う。
3. 新しい role claim を追加した場合は、まずこの表に行を追加してから benchmark を増やす。
