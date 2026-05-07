# Combined Regression Playbook

## Purpose

この文書は、
`role weakening`
と
`schema alias admission`
の 2 系統の回帰確認を、
1 つの実行手順として束ねるための playbook である。

目的は、新しい主張を追加することではなく、
すでに整理済みの

- role regression
- alias admission regression
- regression run template
- validation commands

を、毎回同じ順序で使えるように固定することにある。

## Inputs

この playbook を使う前提は次のいずれかである。

- `IRGenerator` の intent / role / structural dependency / bridge node を変更した
- `CHECK`, `FILTER`, `CALCULATE` の metadata や provenance を変更した
- schema alias を追加・削除・保留状態変更した
- benchmark case や observed IR を更新した

## Core Assets

### Regression Tables

- `results/role_weakening_regression_table.md`
- `results/schema_alias_admission_regression_table.md`

### Operation Template

- `../templates/ir_meaning_preservation_regression_run_template.md`

### Supporting Policy / Status

- `schema_alias_role_weakening_regression_checklist.md`
- `schema_alias_admission_timing_matrix.md`
- `results/schema_alias_admission_status_table.md`
- `claim_evidence_implementation_map.md`

## Standard Procedure

### Step 1. Identify the change type

最初に、今回の変更が主にどちらの系統に属するかを決める。

- role 側が主: `spec_role`, promotion, runtime dispatch, structural role
- alias 側が主: canonical property, alias supply, admission timing, coverage
- 両方にまたがる場合: 2 系統とも実施する

### Step 2. Open the relevant regression table first

コードを見る前に、該当する表の行を決める。

- role 側:
  - `results/role_weakening_regression_table.md`
- alias 側:
  - `results/schema_alias_admission_regression_table.md`

ここで確認するのは次の 3 点だけでよい。

1. `Main Drift Risk`
2. `Baseline Status`
3. `Regression Check`

alias 側では、run record の `Admission state` は運用語彙
(`Admit Now`, `Hold For Evidence`, `Reject`) で書き、
regression table との照合時には
`Admit Now -> admitted`,
`Hold For Evidence/Reject -> not admitted`
へ正規化して読む。

### Step 3. Copy the run template

`research/templates/ir_meaning_preservation_regression_run_template.md`
を複製し、今回の run 記録を作る。

最低限埋める項目:

- `Affected Claims`
- `Role Weakening Check`
- `Alias Admission Check`
- `Validation Run`
- `Final Judgment`

### Step 4. Decide benchmark coverage

今回の変更が次のどれに当たるか決める。

- 既存 benchmark だけで十分
- contrast case が必要
- observed IR の再採取が必要

判断に迷う場合は次で決める。

- role が drift しうる -> `role_weakening_regression_table.md` の `Regression Check` を優先
- alias state が変わる -> `schema_alias_admission_status_table.md` の更新を必須

### Step 5. Run validation

最低限、次を実行する。

推奨は、以下の helper を使ってまとめて流すこと。

1. `python scripts/validate/run_ir_meaning_preservation_regression.py --run-file research/ir_meaning_preservation/results/<run_file>.md --test-suite <suite>`

この helper は最低限次を順に実行する。

1. `python scripts/sync_project_map.py`
2. `python scripts/validate_project_consistency.py`
3. `python scripts/validate/validate_ir_meaning_preservation_regression.py --run-file research/ir_meaning_preservation/results/<run_file>.md`

実行後は、`Validation Run` 欄へ貼り付けられる markdown block も出力される。
加えて、今回の run file に対応する `role` / `alias admission` の `Regression Check` 行も再掲される。
さらに、`Role Weakening Check` と `Alias Admission Check` の下書き block も出力される。
同じく、`Change Summary` と `Benchmark Coverage` の下書き block も出力される。
加えて、`Affected Claims` と `Downstream Conservatism Check` の下書き block も出力される。
最後に、`Output Path Check` と `Deliverables Produced` の下書き block も出力される。

実装変更がある場合は、さらに対象テストを実行する。

例:

- `python scripts/validate/run_ir_meaning_preservation_regression.py --run-file research/ir_meaning_preservation/results/<run_file>.md --test-suite ir-core`
- `python scripts/validate/run_ir_meaning_preservation_regression.py --run-file research/ir_meaning_preservation/results/<run_file>.md --test-suite ir-generator`
- `python scripts/validate/run_ir_meaning_preservation_regression.py --run-file research/ir_meaning_preservation/results/<run_file>.md --test-suite binder`

出力経路を変更した場合は、さらに次を確認する。

- `docs/stdout_output_policy.md` で `stdout / stderr / debug_print / logger` の分類が妥当か
- 変更したモジュールの source-level `.design.md` に出力契約が反映されているか

### Step 6. Update the right result artifact

更新先は変更種別で分ける。

#### Role-side change

- `results/role_weakening_regression_table.md`
- 必要なら `results/role_mapping_matrix.md`
- run record

#### Alias-side change

- `results/schema_alias_admission_regression_table.md`
- `results/schema_alias_admission_status_table.md`
- 必要なら `schema_alias_admission_timing_matrix.md`
- run record

### Step 7. Close the loop

最後に、次の閉路が成立しているか確認する。

1. `claim`
2. `evidence`
3. `implementation`
4. `regression artifact`
5. `checklist/template`

どれか 1 つでも欠ける場合は、変更を閉じたとはみなさない。

## Decision Rules

### When role table is enough

次の変更では role table だけでよい。

- `spec_role` bridge の補正
- `CHECK` / `FILTER` / `CALCULATE` の dispatch 修正
- structural role の保持確認

### When alias table is enough

次の変更では alias table だけでよい。

- schema alias の追加・削除
- `Hold` -> `Admit Now` の状態変更
- timing root の再分類

### When both are required

次の変更では両方使う。

- property canonicalization が `FILTER` / `CHECK` / `CALCULATE` の concretization を変える
- alias admission の変更が downstream conservatism を変える
- role promotion と canonical property promotion が同時に関係する

## Minimal Done Condition

この playbook に沿った run が done と言えるのは、少なくとも次を満たしたときである。

- run record が 1 本ある
- relevant regression table が確認または更新されている
- project consistency が通っている
- regression run validator が通っている
- 必要な tests が通っている
- changelog が更新されている
- 出力経路を変えた場合は `stdout_output_policy.md` と source-level `.design.md` が同期している

## Recommended Next Use

次に `IRGenerator` または schema alias を変更するときは、
最初にこの playbook を開き、
対応する regression table の行を決めてから実装へ入る。
