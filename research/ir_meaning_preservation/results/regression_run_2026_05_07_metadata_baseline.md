# IR Meaning Preservation Regression Run

## 1. Change Summary

- **Date**:
- **Changed Area**:
  - `IRGenerator`
  - `CHECK`
  - `FILTER`
  - `CALCULATE`
  - `DISPLAY`
  - `TRANSFORM`
  - `ITERATE`
  - `schema alias`
  - `downstream conservatism`
- **Related Files**:
  - `src/ir_generator/ir_generator.py`
  - `src/ir_generator/check_resolution.py`
  - `src/ir_generator/display_resolution.py`
  - `src/ir_generator/iterate_resolution.py`
  - `src/ir_generator/transform_resolution.py`
  - `src/ir_generator/promotion_rules.py`
  - `src/ir_generator/target_resolution.py`
  - `src/ir_generator/spec_role_rules.py`
  - `src/utils/entity_inference.py`
  - `src/code_synthesis/action_synthesizer.py`
  - `src/code_synthesis/action_handlers/display_transform_ops.py`
  - `src/code_synthesis/semantic_binder.py`
  - `src/code_synthesis/action_handlers/calc_ops.py`
- **Why This Change Was Made**:
  - 直近まで進めた metadata-driven IR / synthesis 実装を、テンプレート運用の初回実記録として固定するため。

## 5. Benchmark Coverage

- **Existing cases used**:
  - `case_01` (`TRANSFORM`)
  - `case_06` - `case_08` (`CHECK`)
  - `case_12` - `case_15` (`CALCULATE`)
  - `case_16` - `case_21` (`FILTER` / provenance / alias supply)
  - `case_22` - `case_31` (alias admission timing)
- **New contrast case added?**:
  - なし
- **Observed IR files updated**:
  - なし
- **Results tables updated**:
  - なし

## 2. Affected Claims

- **Primary Claim**:
  - 主要な意味損失は structure collapse より role weakening と provenance under-capture にある。
- **Secondary Claims**:
  - provenance metadata は downstream conservatism を制御できる。
  - alias admission は runtime heuristic ではなく schema policy として扱うべきである。
- **Claim Map References**:
  - `claim_evidence_implementation_map.md`
  - `implementation_priority_from_claims.md`

## 6. Downstream Conservatism Check

- **Affected consumers**:
  - `action_synthesizer.py`
  - `display_transform_ops.py`
  - `semantic_binder.py`
  - `calc_ops.py`
- **Expected stronger concretization**:
  - `schema_property` / `unique_owner` / `explicit_entity` がある場合のみ許可
- **Expected weaker/generic fallback**:
  - `history_subject` / `history_predicate` は exact scope 限定
  - `default_*` は generic path か TODO 停止
- **TODO stop points introduced or removed**:
  - baseline 上の変更なし

## 3. Role Weakening Check

- **Affected `spec_role` values**:
  - `CHECK`
  - `FILTER`
  - `CALCULATE`
  - `TRANSFORM`
  - `DISPLAY`
  - `DESERIALIZE`
  - `ITERATE`
  - `WRAP`
- **Expected runtime impact**:
- **Role weakening risk**:

### Before / After Expectation

- **Expected IR fields that must remain stable**:
- **Expected IR fields that may change**:
- **Runtime fields that must not weaken**:
  - `CHECK`: `check_kind`, `check_subject`, `subject_resolution` が保持されるか
  - `FILTER`: predicate/context 条件なしで昇格しないか、逆に必要ケースで `LINQ` に上がるか
  - `CALCULATE`: `entity_resolution` が適切か、ambiguous case で過剰具体化しないか、`calculate_target_resolution` が `schema_property` / `history_target` / `explicit_target` / `default_target` を適切に分けるか、`calculate_source_resolution` / `calculate_source_node_id` がある場合は exact upstream source が `active_scope_item` や latest var より優先されるか、source が弱い場合でも `default_scope_var` として観測可能に残るか
  - `TRANSFORM`: `ops` 付き transform が generic action に落ちず、`transform_op_resolution` / `transform_source_resolution` / `transform_source_node_id` が保持され、exact upstream source が active scope より優先されるか
  - `DISPLAY`: display intent が sink として残り、schema-backed `property` / `display_property_resolution` がある場合は `item.<Property>` 表示へ落ちるか
  - `DESERIALIZE`: auto `JSON_DESERIALIZE` node と `spec_role=DESERIALIZE` が残るか
  - `ITERATE`: loop node の `spec_role=ITERATE` と child linkage が残り、`iteration_source_resolution` / `iteration_source_node_id` / `iteration_item_entity` / `iteration_item_resolution` / `iteration_item_var` / `iteration_item_var_resolution` が保持され、exact upstream collection と item entity が weak fallback より優先され、explicit item alias がある場合は nested child も generic `item` に戻らないか
  - `WRAP`: wrapper node の `spec_role=WRAP` と child boundary が残り、`retry` / explicit `timeout` / explicit `transaction` statement と body が generic fallback call に落ちず、retry は explicit policy だけでなく default policy (`default_attempts`, `default_exception_type`, `default_no_delay_policy`) も、timeout は `timeout_ms` / `timeout_resolution` も、transaction は `transaction_resolution` も sync/async codegen に保持されるか

## 4. Alias Admission Check

- **Alias touched**:
- **Admission state**:
  - `Admit Now`
- **Timing root**:
  - `Downstream Impact`
- **Why this root applies**:
- **Coverage tier**:
- **Regression Check Reference**: `Downstream Impact / admitted` -> canonicalization 後に TODO 停止や generic fallback が不要に残っていないか

## 7. Validation Run

- **regression_runner**:
  - `python scripts/validate/run_ir_meaning_preservation_regression.py --run-file research/ir_meaning_preservation/results/regression_run_2026_05_07_metadata_baseline.md --test-suite ir-core`
  - 結果: `OK: IR meaning-preservation regression workflow completed.`
- **sync_project_map**:
  - `python scripts/sync_project_map.py`
  - 結果: `Synchronization complete.`
- **project_consistency**:
  - `python scripts/validate_project_consistency.py`
  - 結果: `OK: All checks passed. Project is consistent.`
- **regression_run_validator**:
  - `python scripts/validate/validate_ir_meaning_preservation_regression.py --run-file research/ir_meaning_preservation/results/regression_run_2026_05_07_metadata_baseline.md`
  - 結果: `OK: Regression run record is structurally consistent.`
- **unit/integration tests**:
  - `python -m unittest tests.unit.test_ir_generator tests.unit.test_semantic_binder_logic tests.unit.test_code_synthesizer_integration`
  - 結果: `Ran 91 tests in 88.052s` / `OK`
- **other checks**:
  - role regression checks:
    - `CHECK`: `check_kind`, `check_subject`, `subject_resolution` が保持されるか
    - `FILTER`: predicate/context 条件なしで昇格しないか、逆に必要ケースで `LINQ` に上がるか
    - `CALCULATE`: `entity_resolution` が適切か、ambiguous case で過剰具体化しないか、`calculate_target_resolution` が `schema_property` / `history_target` / `explicit_target` / `default_target` を適切に分けるか、`calculate_source_resolution` / `calculate_source_node_id` がある場合は exact upstream source が `active_scope_item` や latest var より優先されるか、source が弱い場合でも `default_scope_var` として観測可能に残るか
    - `TRANSFORM`: `ops` 付き transform が generic action に落ちず、`transform_op_resolution` / `transform_source_resolution` / `transform_source_node_id` が保持され、exact upstream source が active scope より優先されるか
    - `DISPLAY`: display intent が sink として残り、schema-backed `property` / `display_property_resolution` がある場合は `item.<Property>` 表示へ落ちるか
    - `DESERIALIZE`: auto `JSON_DESERIALIZE` node と `spec_role=DESERIALIZE` が残るか
    - `ITERATE`: loop node の `spec_role=ITERATE` と child linkage が残り、`iteration_source_resolution` / `iteration_source_node_id` / `iteration_item_entity` / `iteration_item_resolution` / `iteration_item_var` / `iteration_item_var_resolution` が保持され、exact upstream collection と item entity が weak fallback より優先され、explicit item alias がある場合は nested child も generic `item` に戻らないか
    - `WRAP`: wrapper node の `spec_role=WRAP` と child boundary が残り、`retry` / explicit `timeout` / explicit `transaction` statement と body が generic fallback call に落ちず、retry は explicit policy だけでなく default policy (`default_attempts`, `default_exception_type`, `default_no_delay_policy`) も、timeout は `timeout_ms` / `timeout_resolution` も、transaction は `transaction_resolution` も sync/async codegen に保持されるか
  - alias regression check: `Downstream Impact / admitted` -> canonicalization 後に TODO 停止や generic fallback が不要に残っていないか

## 8. Output Path Check

- **Touched modules with output-path changes**:
  - なし。この run 自体は output-path の追加変更を含まない。
- **Output classification checked against `docs/stdout_output_policy.md`**:
  - `Formal CLI stdout`
  - `Formal CLI stderr`
  - `debug_print`
  - `logger`
- **Source-level `.design.md` updated for output-path changes**:
  - `not applicable`
- **Any new raw `print` introduced?**:
  - `no`

## 9. Deliverables Produced

- [ ] benchmark case updated
- [ ] observed IR updated
- [ ] results observation updated
- [ ] claim/evidence map updated
- [x] changelog updated

## 10. Final Judgment

- **Regression status**:
  - `no regression observed`
- **Open risks**:
  - この run は benchmark JSON の再採取を伴わないため、将来の runtime 変更時には case-level observed IR 再採取が必要。
  - debug print が test 実行時に出ているため、将来的には stdout guard / debug policy の整理対象になりうる。
- **Next action**:
  - 次の実装変更時からは、この記録を baseline として before/after を比較する。
