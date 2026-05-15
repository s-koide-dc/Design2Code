# IR Case Templates

## Purpose

このディレクトリは、`IR meaning preservation` の各比較ケースについて、人手で期待 IR を定義するための作業領域である。

## Authoring Rules

- 先に `Expected IR` を書き、後から実 IR を見て修正しない
- 期待 IR は現行実装の癖ではなく、`docs/ir_design.md` の表現原則に合わせる
- 曖昧な部分は空欄のままにせず、暫定解を 1 つに固定する
- `Observed IR` と `Diff Notes` は、実 IR 採取後に追記する

## Initial Cases

- `case_01_stdin_to_stdout_transform.md`
- `case_02_complex_linq_search.md`
- `case_03_batch_process_products.md`
- `case_04_robust_config_loader.md`
- `case_05_sync_external_data.md`

## Supplemental CHECK Cases

- `case_06_check_exists_file.md`
- `case_07_check_null_guard.md`
- `case_08_check_numeric_comparison.md`

## Supplemental Structural Dependency Cases

- `case_09_condition_branch_dependency.md`
- `case_10_loop_body_dependency.md`
- `case_11_wrapper_scope_dependency.md`

## Supplemental CALCULATE Cases

- `case_12_calculate_with_target_hint.md`
- `case_13_calculate_without_target_hint.md`
- `case_14_calculate_ambiguous_property_owner.md`
- `case_15_calculate_history_fallback_gap.md`
- `case_35_calculate_history_target_with_explicit_entity.md`
- `case_36_calculate_default_target_retention.md`

## Supplemental Provenance Strength Boundary Cases

- `case_18_check_provenance_strength_boundary.md`
- `case_19_filter_provenance_strength_boundary.md`

## Supplemental Alias Supply Contrast Cases

- `case_20_schema_alias_supplied_canonicalization.md`
- `case_21_schema_alias_missing_weak_retention.md`

## Supplemental Alias Coverage Policy Contrast Cases

- `case_22_allowed_alias_admission.md`
- `case_23_disallowed_generic_alias_rejection.md`
- `case_24_conditional_alias_with_owner_explanation.md`
- `case_25_generic_abbreviation_rejection.md`
- `case_26_legacy_field_bridge_admission.md`
- `case_27_admissible_but_deferred_alias.md`
- `case_28_repeated_spec_use_promotes_alias.md`
- `case_29_cross_case_relevance_threshold.md`
- `case_30_downstream_impact_threshold.md`
- `case_31_external_compatibility_threshold.md`
- `case_32_return_provenance_contrast.md`
- `case_33_return_input_link_supply.md`
- `case_34_return_weak_retention.md`
