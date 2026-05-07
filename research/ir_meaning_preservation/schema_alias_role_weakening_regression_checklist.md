# Schema Alias / Role Weakening Regression Checklist

## Purpose

この文書は、`role weakening` と `schema alias admission` に関する研究主張を、
実装変更や benchmark 追加のたびに再確認できる regression checklist として固定するためのものである。

目的は 2 つある。

1. runtime 側の if 分岐を増やさずに、研究主張を保守フローへ落とす
2. 新しいケースや schema alias を追加するとき、何を確認すれば regression を防げるかを明示する

## When To Use

次のいずれかを行うときに使う。

- `IRGenerator` の intent / role / promotion を変更するとき
- `CHECK`, `FILTER`, `CALCULATE` の provenance / resolution を変更するとき
- `entity_schema` に alias を新規追加するとき
- benchmark case を追加・更新するとき
- downstream conservatism の条件を変えるとき

## A. Role Weakening Checklist

### A1. Claim Alignment

- 変更対象は、どの role claim に関係するかを先に特定したか
- `CHECK`, `FILTER`, `CALCULATE`, `WRAP`, `ITERATE`, `DISPLAY`, `FETCH` のどれが影響を受けるかを書いたか
- `claim_evidence_implementation_map.md` の該当 claim を参照したか

### A2. Expected IR Side

- `spec_role` が期待どおり保持されるか確認したか
- `runtime role` が弱化していないか確認したか
- 変更後も `Expected IR -> Observed IR` 比較で role weakening が増えていないか見たか

### A3. Benchmark Coverage

- 少なくとも 1 つの既存 benchmark を使って before/after を見たか
- 必要なら contrast case も追加したか
- `results/failure_mapping.md` 上の失敗類型が悪化していないか確認したか

### A4. Downstream Effect

- role の変化が `semantic_binder.py` / `action_synthesizer.py` / handler 層にどう効くか確認したか
- stronger role にした結果、over-interpretation が起きていないか見たか
- weaker role に落ちた結果、不要な TODO 停止や generic path 増加が起きていないか見たか

## B. Schema Alias Admission Checklist

### B1. Admission Root

- 新規 alias がどの timing root に属するか決めたか
  - `Hold For Evidence`
  - `Repeated Spec Use`
  - `Cross-Case Relevance`
  - `Downstream Impact`
  - `External Compatibility`
- root を決めずに alias を追加していないか

### B2. Coverage Policy

- `owner-confined` を 1 文で説明できるか
- `canonical non-ambiguity` があるか
- `exact-match sufficiency` があるか
- generic token や partial match に依存していないか

### B3. Admission Timing

- `can_admit` と `should_admit_now` を分けて考えたか
- `Hold For Evidence` なら schema にまだ入れない判断を明示したか
- `Admit Now` ならその根拠を benchmark / external constraint / downstream impact のいずれかで説明したか

### B4. Observation Update

- case 文書の `Expected IR` を固定したか
- `Observed IR` を採り直したか
- `results/schema_alias_admission_status_table.md` を更新したか
- `results/schema_alias_admission_threshold_observation.md` または関連 observation 文書を更新したか

## C. Minimal Deliverables

変更を 1 回進めたら、最低限次のどれかは残す。

- benchmark case
- observed IR JSON
- results table / observation update
- claim/evidence/implementation map の更新

これらが何も無い変更は、研究上の traceability が弱い。

## D. Do Not Do

- alias admission root を曖昧にしたまま schema へ追加しない
- role weakening を「テストが通るから」で見逃さない
- generic token を coverage のためだけに canonical property へ寄せない
- admission timing を runtime heuristic で代替しない
- benchmark 更新なしに研究主張だけを書き換えない

## E. Recommended Workflow

1. claim を決める
2. admission root / affected role を決める
3. expected case を固定する
4. observed IR を採る
5. results table と claim map を更新する
6. 必要なら runtime 実装を直す
7. 出力経路を変えた場合は `docs/stdout_output_policy.md` と source-level `.design.md` を更新する
8. 標準手順は `scripts/validate/run_ir_meaning_preservation_regression.py` で流す
9. run record を作ったら `scripts/validate/validate_ir_meaning_preservation_regression.py` を通す

この順序を守ると、場当たり的な修正に戻りにくい。

## F. Operational Templates

繰り返し運用では、以下のテンプレートを複製して使う。

- `research/templates/ir_meaning_preservation_regression_run_template.md`
- `research/templates/ir_meaning_preservation_benchmark_addition_template.md`

出力経路を変えた変更では、あわせて `docs/stdout_output_policy.md` を確認する。
