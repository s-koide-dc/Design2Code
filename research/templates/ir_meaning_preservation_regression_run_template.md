# IR Meaning Preservation Regression Run Template

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
- **Why This Change Was Made**:

## 2. Affected Claims

- **Primary Claim**:
- **Secondary Claims**:
- **Claim Map References**:
  - `claim_evidence_implementation_map.md`
  - `implementation_priority_from_claims.md`

## 3. Role Weakening Check

- **Affected `spec_role` values**:
- **Expected runtime impact**:
- **Role weakening risk**:
  - `none`
  - `acceptable`
  - `needs contrast case`

### Before / After Expectation

- **Expected IR fields that must remain stable**:
- **Expected IR fields that may change**:
- **Runtime fields that must not weaken**:

## 4. Alias Admission Check

- **Alias touched**:
- **Admission state**:
  - `Admit Now`
  - `Hold For Evidence`
  - `Reject`
  - validator では `Admit Now -> admitted`, `Hold For Evidence/Reject -> not admitted` と正規化して regression table と照合する
- **Timing root**:
  - `Repeated Spec Use`
  - `Cross-Case Relevance`
  - `Downstream Impact`
  - `External Compatibility`
- **Why this root applies**:
- **Coverage tier**:
  - `Tier 1`
  - `Tier 2`
  - `Tier 3`

## 5. Benchmark Coverage

- **Existing cases used**:
- **New contrast case added?**:
- **Observed IR files updated**:
- **Results tables updated**:

## 6. Downstream Conservatism Check

- **Affected consumers**:
  - `action_synthesizer.py`
  - `semantic_binder.py`
  - `calc_ops.py`
- **Expected stronger concretization**:
- **Expected weaker/generic fallback**:
- **TODO stop points introduced or removed**:

## 7. Validation Run

- **regression_runner**:
- **sync_project_map**:
- **project_consistency**:
- **regression_run_validator**:
- **unit/integration tests**:
- **other checks**:

## 8. Output Path Check

- **Touched modules with output-path changes**:
- **Output classification checked against `docs/stdout_output_policy.md`**:
  - `Formal CLI stdout`
  - `Formal CLI stderr`
  - `debug_print`
  - `logger`
- **Source-level `.design.md` updated for output-path changes**:
- **Any new raw `print` introduced?**:

## 9. Deliverables Produced

- [ ] benchmark case updated
- [ ] observed IR updated
- [ ] results observation updated
- [ ] claim/evidence map updated
- [ ] changelog updated

## 10. Final Judgment

- **Regression status**:
  - `no regression observed`
  - `acceptable tradeoff`
  - `needs follow-up`
- **Open risks**:
- **Next action**:
