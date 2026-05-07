# Research Templates

## Purpose

このディレクトリは、研究文書を増やすためではなく、
既存の研究主張・benchmark・観測結果を
再現可能な運用フローへ落とすためのテンプレートを置く場所である。

## Current Templates

- `ir_meaning_preservation_regression_run_template.md`
  - `schema alias / role weakening` の回帰確認を 1 回分記録するテンプレート
- `ir_meaning_preservation_benchmark_addition_template.md`
  - benchmark 追加時に claim, timing root, expected/observed 更新点を固定するテンプレート

## Related Operational Policy

- 出力経路を伴う変更では `docs/stdout_output_policy.md` も確認対象に含める。
- template を埋めるときは、必要なら source-level `.design.md` の `Operational Notes` 更新も deliverable に含める。
- regression run 記録を作ったら `scripts/validate/validate_ir_meaning_preservation_regression.py` で構造整合性を検証する。
- 標準手順をまとめて流す場合は `scripts/validate/run_ir_meaning_preservation_regression.py` を使う。
- regression runner は `Validation Run` 欄へ貼れる markdown block を最後に出力する。
- regression runner はあわせて、run file に対応する `role` / `alias admission` の `Regression Check` も再掲する。
- regression runner は `Role Weakening Check` / `Alias Admission Check` の下書き block も出力する。
- regression runner は `Change Summary` / `Benchmark Coverage` の下書き block も出力する。
- regression runner は `Affected Claims` / `Downstream Conservatism Check` の下書き block も出力する。
- regression runner は `Output Path Check` / `Deliverables Produced` の下書き block も出力する。

## Usage Rule

1. 新しい benchmark や alias admission 変更を行う前にテンプレートを複製して使う。
2. テンプレート自体は空の運用枠として保ち、実際の記録は theme 配下へ置く。
3. チェック項目を増やすときは、既存の research claim と observation 文書に接続できるものだけ追加する。
