# Document Map

## Purpose

`research/ir_meaning_preservation/` 配下の文書が増えてきたため、ここでは「どの文書が何の役割を持つか」を分類単位で固定する。

この段階では物理移動を急がず、まずは論点ごとの入口を揃える。必要になった時点で、この分類をそのままディレクトリ構造へ落とす。

## Category Rules

### 1. Foundation

研究の前提、評価軸、共通規則を置く。

- `evaluation.md`
- `role_layer_definition.md`
- `structural_dependency_rule.md`
- `structural_role_bridge.md`
- `check_role_refinement.md`
- `resolution_provenance_model.md`
- `cross_role_provenance_design.md`
- `provenance_strength_policy_matrix.md`
- `calculate_target_entity_ambiguity_rule.md`
- `calculate_entity_resolution_policy.md`

### 2. Archived Analysis

過去の分析過程や初期の提案など、すでに結論が他のポリシーに吸収された文書を `archived_analysis/` 配下に退避している。

- `archived_analysis/intent_drift_analysis.md`
- `archived_analysis/dependency_loss_analysis.md`
- `archived_analysis/focused_role_analysis.md`
- `archived_analysis/filter_fetch_collapse_analysis.md`
- `archived_analysis/calculate_role_analysis.md`
- `archived_analysis/review_adoption.md`
- `archived_analysis/minimal_design_change_proposal.md`
- `archived_analysis/ir_generator_decomposition_plan.md`

### 3. Design Proposal

設計変更案や昇格規則の提案を置く。

- `calculate_promotion_rule.md`
- `filter_promotion_rule.md`
- `property_side_provenance_promotion_rule.md`
- `schema_alias_supply_model.md`
- `schema_alias_coverage_policy.md`
- `schema_alias_admission_threshold.md`
- `schema_alias_admission_timing_matrix.md`

### 4. Cases

個別 benchmark の期待 IR、観測結果、差分メモは `cases/` に置く。

- `cases/case_01_...md` から `cases/case_32_...md`

命名規則:

- 新規ケースは `case_XX_<topic>.md`
- `XX` は連番固定
- 1 文書の中で `Expected IR`, `Observed IR`, `Diff Notes`, `Failure Mapping` を持つ

### 5. Results

横断観測、実装トレース、比較結果を `results/` に置く。

- `results/failure_mapping.md`
- `results/intent_drift_trace.md`
- `results/dependency_loss_trace.md`
- `results/role_mapping_matrix.md`
- `results/structural_dependency_observation.md`
- `results/calculate_case_observation.md`
- `results/schema_alias_admission_status_table.md`
- `results/schema_alias_admission_regression_table.md`
- `results/regression_run_2026_05_07_metadata_baseline.md`
- `results/role_weakening_regression_table.md`
- `results/observed_ir/*.observed.json`

### 6. Summary

中間まとめや研究上の主張整理を置く。

- `calculate_metadata_conservatism_summary.md`
- `executive_summary.md`
- `research_outcome_memo.md`
- `claim_evidence_implementation_map.md`
- `implementation_priority_from_claims.md`
- `schema_alias_role_weakening_regression_checklist.md`
- `combined_regression_playbook.md`
- `goal_state.md`

### 7. Templates

反復運用や benchmark 追加で使う空テンプレートは `research/templates/` に置く。

- `../templates/ir_meaning_preservation_regression_run_template.md`
- `../templates/ir_meaning_preservation_benchmark_addition_template.md`

## Recommended Next Cleanup

今すぐ全部移動する必要はないが、次の順で整理すると壊れにくい。

1. まず README からこの分類へリンクする
2. 新規文書は必ずこのカテゴリに従って追加する
3. 既存文書の物理移動は、参照関係を洗い出してから小分けで行う

## Naming Guidance

- `*_analysis.md`: 局所問題の観測・仮説・原因整理
- `*_rule.md`: 共通規則や禁止事項
- `*_policy.md`: downstream を含む運用方針
- `*_summary.md`: 中間まとめや外向け説明
- `*_trace.md`: 実装レベルの追跡記録

## Immediate Decision

当面はフラット構成を維持する。ただし、読み方はこの文書のカテゴリ順に固定する。
