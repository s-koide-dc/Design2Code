# Regression Runner Draft Bundle

- Source run file: `research/ir_meaning_preservation/results/regression_run_2026_05_07_metadata_baseline.md`
- Test suite: `none`

--- Relevant Regression Checks ---
Role-side:
- CHECK: `check_kind`, `check_subject`, `subject_resolution` が保持されるか
- FILTER: predicate/context 条件なしで昇格しないか、逆に必要ケースで `LINQ` に上がるか
- CALCULATE: `entity_resolution` が適切か、ambiguous case で過剰具体化しないか
- DESERIALIZE: auto `JSON_DESERIALIZE` node と `spec_role=DESERIALIZE` が残るか
- ITERATE: loop node の `spec_role=ITERATE` と child linkage が残るか
- WRAP: wrapper node の `spec_role=WRAP` と child boundary が残るか
Alias-side:
- Downstream Impact / admitted: canonicalization 後に TODO 停止や generic fallback が不要に残っていないか

--- Paste-Ready Summary Draft ---
```md
## 1. Change Summary

- **Date**:
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
```

--- Paste-Ready Claims / Downstream Draft ---
```md
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
  - `semantic_binder.py`
  - `calc_ops.py`
- **Expected stronger concretization**:
  - `schema_property` / `unique_owner` / `explicit_entity` がある場合のみ許可
- **Expected weaker/generic fallback**:
  - `history_subject` / `history_predicate` は exact scope 限定
  - `default_*` は generic path か TODO 停止
- **TODO stop points introduced or removed**:
  - baseline 上の変更なし
```

--- Paste-Ready Check Draft ---
```md
## 3. Role Weakening Check

- **Affected `spec_role` values**:
  - `CHECK`
  - `FILTER`
  - `CALCULATE`
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
  - `CALCULATE`: `entity_resolution` が適切か、ambiguous case で過剰具体化しないか
  - `DESERIALIZE`: auto `JSON_DESERIALIZE` node と `spec_role=DESERIALIZE` が残るか
  - `ITERATE`: loop node の `spec_role=ITERATE` と child linkage が残るか
  - `WRAP`: wrapper node の `spec_role=WRAP` と child boundary が残るか

## 4. Alias Admission Check

- **Alias touched**:
- **Admission state**:
  - `Admit Now`
- **Timing root**:
  - `Downstream Impact`
- **Why this root applies**:
- **Coverage tier**:
- **Regression Check Reference**: `Downstream Impact / admitted` -> canonicalization 後に TODO 停止や generic fallback が不要に残っていないか
```

--- Paste-Ready Output / Deliverables Draft ---
```md
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
```

--- Paste-Ready Final Judgment Draft ---
```md
## 10. Final Judgment

- **Regression status**:
  - `no regression observed`
- **Open risks**:
  - この run は benchmark JSON の再採取を伴わないため、将来の runtime 変更時には case-level observed IR 再採取が必要。
  - debug print が test 実行時に出ているため、将来的には stdout guard / debug policy の整理対象になりうる。
- **Next action**:
  - 次の実装変更時からは、この記録を baseline として before/after を比較する。
```

--- Paste-Ready Validation Block ---
```md
- **regression_runner**:
  - `python scripts/validate/run_ir_meaning_preservation_regression.py --run-file research/ir_meaning_preservation/results/regression_run_2026_05_07_metadata_baseline.md --test-suite none`
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
  - `not run`
- **other checks**:
  - role regression checks:
    - `CHECK`: `check_kind`, `check_subject`, `subject_resolution` が保持されるか
    - `FILTER`: predicate/context 条件なしで昇格しないか、逆に必要ケースで `LINQ` に上がるか
    - `CALCULATE`: `entity_resolution` が適切か、ambiguous case で過剰具体化しないか
    - `DESERIALIZE`: auto `JSON_DESERIALIZE` node と `spec_role=DESERIALIZE` が残るか
    - `ITERATE`: loop node の `spec_role=ITERATE` と child linkage が残るか
    - `WRAP`: wrapper node の `spec_role=WRAP` と child boundary が残るか
  - alias regression check: `Downstream Impact / admitted` -> canonicalization 後に TODO 停止や generic fallback が不要に残っていないか
```