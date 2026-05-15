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
| `TRANSFORM` | `ACTION` へ圧縮、source provenance が active scope に吸収 | display/transform handlers, generic action path | Stable with weak-intent bridge and source provenance path | `role_mapping_matrix.md`, `action_synthesizer.py`, `transform_resolution.py` | `ops` 付き transform が generic action に落ちず、`transform_op_resolution` / `transform_source_resolution` / `transform_source_node_id` が保持され、exact upstream source が active scope より優先されるか |
| `CHECK` | `ACTION` へ圧縮、subject provenance 消失 | `SemanticBinder` condition generation | Stable with metadata path | `check_role_refinement.md`, `results/check_case_observation.md`, `case_17` | `check_kind`, `check_subject`, `subject_resolution` が保持されるか |
| `CALCULATE` | `GENERAL/ACTION` へ弱化、target 解決や source continuity が latest var fallback に吸収 | `ActionSynthesizer` -> `CALC`, `calc_ops.py` | Stable with guarded concretization and source/target provenance path | `calculate_promotion_rule.md`, `results/calculate_case_observation.md` | `entity_resolution` が適切か、ambiguous case で過剰具体化しないか、`calculate_target_resolution` が `schema_property` / `history_target` / `explicit_target` / `default_target` を適切に分けるか、`calculate_source_resolution` / `calculate_source_node_id` がある場合は exact upstream source が `active_scope_item` や latest var より優先されるか、source が弱い場合でも `default_scope_var` として観測可能に残るか |
| `DISPLAY` | `void` / generic action へ弱化、property-backed display が item 全体表示へ崩れる | display/transform handlers | Stable with property-side display provenance | `role_mapping_matrix.md`, `display_resolution.py`, `display_transform_ops.py` | display intent が sink として残り、schema-backed `property` / `display_property_resolution` がある場合は `item.<Property>` 表示へ落ちるか |
| `PERSIST` | write intent は残るが upstream provenance 消失 | file/io/persist path | Stable | `role_mapping_matrix.md`, `results/failure_mapping.md` | scalar vs collection persist で bridge node 条件が崩れていないか |
| `RETURN` | `ACTION` へ圧縮、literal return や upstream return source が latest var へ吸収 | return handler | Stable with literal and input-link metadata path | `role_mapping_matrix.md`, `test_ir_generator`, `test_code_synthesizer_integration.py` | `return_value` / `return_value_resolution` / `return_source_node_id` が保持され、literal return と chained return が誤連結しないか |
| `ITERATE` | runtime role に出ず構造だけ残る、loop source と item semantics が weak fallback に吸収 | loop handler | Stable on structure with collection/item provenance path | `structural_role_bridge.md`, `results/structural_dependency_observation.md`, `action_synthesizer.py` | loop node の `spec_role=ITERATE` と child linkage が残り、`iteration_source_resolution` / `iteration_source_node_id` / `iteration_item_entity` / `iteration_item_resolution` / `iteration_item_var` / `iteration_item_var_resolution` が保持され、exact upstream collection と item entity が weak fallback より優先され、explicit item alias がある場合は nested child も generic `item` に戻らないか |
| `WRAP` | wrapper semantics が単なる action に吸収、または wrapper-kind ごとの policy metadata が暗黙 default に埋もれる | `IREmitter` wrapper consumer, fallback renderer, `CodeBuilder` | Stable with deterministic retry/timeout/transaction consumers and default-policy provenance | `structural_role_bridge.md`, `wrap_retry_semantics_design.md`, `wrap_timeout_semantics_design.md`, `wrap_transaction_semantics_design.md`, `test_ir_generator`, `test_code_synthesizer_integration.py` | wrapper node の `spec_role=WRAP` と child boundary が残り、`retry` / explicit `timeout` / explicit `transaction` statement と body が generic fallback call に落ちず、retry は explicit policy だけでなく default policy (`default_attempts`, `default_exception_type`, `default_no_delay_policy`) も、timeout は `timeout_ms` / `timeout_resolution` も、transaction は `transaction_resolution` も sync/async codegen に保持されるか |

## Current Interpretation

2026-05-07 時点では、
`CHECK`, `FILTER`, `CALCULATE`, `DESERIALIZE` は
metadata-driven bridge が入ったことで baseline は安定している。

一方で、次の role はまだ runtime 側で独立性が弱い。

- `TRANSFORM`
- `ITERATE`
- `WRAP` は deterministic retry/timeout/transaction consumer と default-policy provenance までは入ったが、timeout/transaction の自然言語推定や wrapper kind のさらなる一般化はまだ扱わない

ただしここで重要なのは、
runtime role 自体を無理に細分化することではなく、
`spec_role` と構造 metadata が保持され、
downstream が必要な箇所だけを読める状態を維持することである。

## Recommended Use

1. `IRGenerator` や promotion rule を触る前に、変更対象 role の行を先に確認する。
2. 変更後は `regression_run_template` に、この表の `Regression Check` を転記して使う。
3. 新しい role claim を追加した場合は、まずこの表に行を追加してから benchmark を増やす。
