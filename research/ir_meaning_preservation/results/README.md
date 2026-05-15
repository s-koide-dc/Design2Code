# IR Results

## Purpose

このディレクトリは、IR meaning preservation の実行結果を保存するための領域である。

## Structure

- `observed_ir/`: 実装から採取した実 IR
- `diff_summary.md`: ケース横断の初回差分要約
- `failure_mapping.md`: 差分を失敗類型へ対応付けた正式マッピング
- `intent_drift_trace.md`: 初期解析結果と最終 IR を比較した drift 発生点の観測
- `dependency_loss_trace.md`: `Dependency Loss` の代表事例を `IRGenerator` 実装レベルで追跡した記録
- `role_mapping_matrix.md`: `spec_role` と観測済み `runtime_role` の対応表
- `check_case_observation.md`: 補助 3 ケースにおける `CHECK` 保存と条件式生成の観測
- `structural_dependency_observation.md`: 構造親依存補助ケースにおける `Observed IR` の初回観測
- `calculate_case_observation.md`: `CALCULATE` 補助ケースにおける target hint あり/なし比較と property-owner ambiguity 観測
- `observed_ir/case_35_calculate_history_target_with_explicit_entity.observed.json`: explicit entity と ambiguous owner が同居する `CALCULATE` で `history_target` を観測した実 IR
- `observed_ir/case_36_calculate_default_target_retention.observed.json`: target metadata を持たない `CALCULATE` で `default_target` を観測した実 IR
- `return_provenance_observation.md`: `RETURN` 補助ケースにおける literal return と upstream value return の provenance 観測
- `return_provenance_supply_observation.md`: `RETURN` provenance の supply success / weak retention contrast を観測した結果
- `provenance_strength_boundary_observation.md`: `schema_backed` / `history_based` 境界ケースにおける `Observed IR` の初回観測
- `schema_alias_supply_observation.md`: alias 供給あり/なし contrast における `Observed IR` の初回観測
- `schema_alias_coverage_observation.md`: alias coverage の admission / rejection contrast における `Observed IR` の初回観測
- `schema_alias_tier2_observation.md`: alias coverage policy の `Tier 2` admission / rejection contrast における `Observed IR` の初回観測
- `schema_alias_admission_threshold_observation.md`: alias admission timing の 5 類型における `Observed IR` の初回観測
- `schema_alias_admission_status_table.md`: alias admission timing の current status を横断比較する table
- `schema_alias_admission_regression_table.md`: alias admission timing を policy root / IR effect / regression check 単位で横断比較する回帰用の基準表
- `regression_run_2026_05_07_metadata_baseline.md`: 現行 metadata-driven IR / synthesis 実装を基準線として固定した初回 regression run 記録
- `role_weakening_regression_table.md`: role weakening を role 単位で横断比較する regression 用の基準表

依存エッジ損失そのものの分析は、結果要約ではなく研究本文側の `dependency_loss_analysis.md` に切り出して扱う。

## Validation

- 標準手順は `scripts/validate/run_ir_meaning_preservation_regression.py` で実行する。
- regression run 記録を追加・更新したら `scripts/validate/validate_ir_meaning_preservation_regression.py` を実行して構造整合性を確認する。
- draft を保存する場合、既定の出力先は `regression_run_*.runner_draft.md` である。
- run file 自体を runner から更新する場合は `--update-run-file` を使う。
