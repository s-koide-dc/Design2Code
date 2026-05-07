# IR Meaning Preservation Regression Run

## 1. Change Summary

- **Date**: 2026-05-07
- **Changed Area**:
  - `IRGenerator`
  - `CHECK`
  - `FILTER`
  - `CALCULATE`
  - `schema alias`
  - `downstream conservatism`
- **Related Files**:
  - `src/ir_generator/ir_generator.py`
  - `src/ir_generator/check_resolution.py`
  - `src/ir_generator/promotion_rules.py`
  - `src/ir_generator/target_resolution.py`
  - `src/ir_generator/spec_role_rules.py`
  - `src/code_synthesis/action_synthesizer.py`
  - `src/code_synthesis/semantic_binder.py`
  - `src/code_synthesis/action_handlers/calc_ops.py`
- **Why This Change Was Made**:
  - 直近まで進めた metadata-driven IR / synthesis 実装を、テンプレート運用の初回実記録として固定するため。

## 2. Affected Claims

- **Primary Claim**:
  - 主要な意味損失は structure collapse より role weakening と provenance under-capture にある。
- **Secondary Claims**:
  - provenance metadata は downstream conservatism を制御できる。
  - alias admission は runtime heuristic ではなく schema policy として扱うべきである。
- **Claim Map References**:
  - `claim_evidence_implementation_map.md`
  - `implementation_priority_from_claims.md`

## 3. Role Weakening Check

- **Affected `spec_role` values**:
  - `CHECK`
  - `FILTER`
  - `CALCULATE`
  - `DESERIALIZE`
  - `ITERATE`
  - `WRAP`
- **Expected runtime impact**:
  - `spec_role` から runtime dispatch が補正されるが、runtime `role` 自体は必要以上に強化しない。
- **Role weakening risk**:
  - `acceptable`

### Before / After Expectation

- **Expected IR fields that must remain stable**:
  - `semantic_map.spec_role`
  - `check_kind`, `subject_resolution`
  - `entity_resolution`
  - `predicate_resolution`, `collection_resolution`
  - structural `input_link`
- **Expected IR fields that may change**:
  - なし。本 run は baseline fixation であり、新しい振る舞い変更を含まない。
- **Runtime fields that must not weaken**:
  - `LINQ` dispatch for `spec_role=FILTER`
  - `JSON_DESERIALIZE` dispatch for `spec_role=DESERIALIZE`
  - `CHECK` condition generation path
  - `CALC` downstream conservatism path

## 4. Alias Admission Check

- **Alias touched**:
  - なし。既存 policy の回帰確認のみ。
- **Admission state**:
  - `Admit Now`
- **Timing root**:
  - `Downstream Impact`
- **Why this root applies**:
  - 現行 alias policy が downstream concretization と停止条件に直結しているため、運用基準線として確認する価値がある。
- **Coverage tier**:
  - `Tier 1`

## 5. Benchmark Coverage

- **Existing cases used**:
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

## 6. Downstream Conservatism Check

- **Affected consumers**:
  - `action_synthesizer.py`
  - `semantic_binder.py`
  - `calc_ops.py`
- **Expected stronger concretization**:
  - `schema_property` / `unique_owner` / `explicit_entity` がある場合のみ許可
- **Expected weaker/generic fallback**:
  - `history_subject` / `history_predicate` は exact scope 限定
  - `default_*` は generic path か TODO 停止
- **TODO stop points introduced or removed**:
  - baseline 上の変更なし

## 7. Validation Run

- **regression_runner**:
  - `python scripts/validate/run_ir_meaning_preservation_regression.py --run-file research/ir_meaning_preservation/results/regression_run_2026_05_07_metadata_baseline.md --test-suite ir-core`
  - 結果: `OK: IR meaning-preservation regression workflow completed.`
- **sync_project_map**:
  - `python scripts/sync_project_map.py` 実行済み
- **project_consistency**:
  - `python scripts/validate_project_consistency.py`
  - 結果: `OK: All checks passed. Project is consistent.`
- **regression_run_validator**:
  - `python scripts/validate/validate_ir_meaning_preservation_regression.py --run-file research/ir_meaning_preservation/results/regression_run_2026_05_07_metadata_baseline.md`
  - 結果: `OK: Regression run record is structurally consistent.`
- **unit/integration tests**:
  - `python -m unittest tests.unit.test_ir_generator tests.unit.test_semantic_binder_logic tests.unit.test_code_synthesizer_integration`
  - 結果: `Ran 52 tests ... OK`
- **other checks**:
  - なし

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
