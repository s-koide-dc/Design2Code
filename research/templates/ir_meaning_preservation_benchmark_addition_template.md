# IR Meaning Preservation Benchmark Addition Template

## 1. Benchmark Identity

- **Case Name**:
- **Topic**:
- **Why this case is needed**:
- **Primary layer**:
  - `role`
  - `provenance`
  - `alias admission timing`
  - `structural dependency`

## 2. Research Connection

- **Primary claim**:
- **Supporting claim**:
- **Failure class targeted**:
- **Relevant design/policy docs**:

## 3. Alias / Admission Context

- **Schema alias involved?**:
- **If yes, admission state**:
  - `Admit Now`
  - `Hold For Evidence`
  - `Reject`
- **Timing root**:
  - `Repeated Spec Use`
  - `Cross-Case Relevance`
  - `Downstream Impact`
  - `External Compatibility`
- **Coverage rationale**:

## 4. Expected IR

- **Expected `spec_role`**:
- **Expected runtime intent/role**:
- **Expected provenance fields**:
- **Expected structural dependency fields**:
- **Expected conservative behavior downstream**:

## 5. Observation Plan

- **Observed IR file path**:
- **Results document to update**:
- **Status table or matrix to update**:
- **Contrast case to compare against**:

## 6. Acceptance Criteria

- [ ] `Expected IR` is fixed before observation
- [ ] observed IR is captured
- [ ] difference is classified
- [ ] result is reflected in table/matrix if relevant
- [ ] claim/evidence link is preserved
- [ ] if implementation changed, output-path classification was checked against `docs/stdout_output_policy.md`
