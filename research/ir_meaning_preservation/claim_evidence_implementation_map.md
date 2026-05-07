# Claim-Evidence-Implementation Map

## Purpose

この文書は、研究主張、観測根拠、実装箇所を 1 つの表で結び付けるための対応表である。

`research_outcome_memo.md` は成果の要約、
`midterm_synthesis.md` は中間統括、
この文書はそれらの主張が

- どの benchmark / observation に支えられているか
- どの実装変更に反映されているか

を追跡できるようにすることを目的とする。

## Map

| Research Claim | Evidence | Implementation Site | Current Status |
| --- | --- | --- | --- |
| 主要な意味損失は structure collapse より role weakening にある | `results/failure_mapping.md`, `intent_drift_analysis.md`, `results/intent_drift_trace.md` | [ir_generator.py](/C:/workspace/NLP/src/ir_generator/ir_generator.py:1), [spec_role_rules.py](/C:/workspace/NLP/src/ir_generator/spec_role_rules.py:1) | substantiated |
| `CHECK` は kind と subject provenance を保持すべきである | `check_role_refinement.md`, `results/check_case_observation.md`, `cases/case_17_check_subject_provenance.md` | [check_resolution.py](/C:/workspace/NLP/src/ir_generator/check_resolution.py:1), [semantic_binder.py](/C:/workspace/NLP/src/code_synthesis/semantic_binder.py:1) | implemented |
| `FILTER` は lexical fetch ではなく predicate/context によって昇格すべきである | `filter_fetch_collapse_analysis.md`, `filter_promotion_rule.md`, `cases/case_16_filter_predicate_provenance.md` | [promotion_rules.py](/C:/workspace/NLP/src/ir_generator/promotion_rules.py:1), [ir_generator.py](/C:/workspace/NLP/src/ir_generator/ir_generator.py:1) | implemented |
| `CALCULATE` は target hint と resolution provenance を保持すべきである | `calculate_role_analysis.md`, `calculate_promotion_rule.md`, `results/calculate_case_observation.md` | [target_resolution.py](/C:/workspace/NLP/src/ir_generator/target_resolution.py:1), [calc_ops.py](/C:/workspace/NLP/src/code_synthesis/action_handlers/calc_ops.py:1) | implemented |
| provenance metadata は downstream conservatism を制御できる | `cross_role_provenance_design.md`, `provenance_strength_policy_matrix.md`, `calculate_metadata_conservatism_summary.md` | [semantic_binder.py](/C:/workspace/NLP/src/code_synthesis/semantic_binder.py:1), [action_synthesizer.py](/C:/workspace/NLP/src/code_synthesis/action_synthesizer.py:1), [calc_ops.py](/C:/workspace/NLP/src/code_synthesis/action_handlers/calc_ops.py:1) | implemented |
| structural dependency は一般規則として記述できる | `structural_dependency_rule.md`, `results/structural_dependency_observation.md`, `dependency_loss_trace.md` | [ir_generator.py](/C:/workspace/NLP/src/ir_generator/ir_generator.py:1) | implemented |
| alias admission は runtime heuristic ではなく schema policy として扱うべきである | `schema_alias_coverage_policy.md`, `schema_alias_admission_threshold.md`, `schema_alias_admission_timing_matrix.md`, `results/schema_alias_admission_threshold_observation.md` | [target_resolution.py](/C:/workspace/NLP/src/ir_generator/target_resolution.py:1), schema-side alias definitions in benchmark schemas | substantiated |
| alias timing は `Hold`, `Repeated`, `Cross-Case`, `Downstream`, `External` の5根拠で整理できる | `schema_alias_admission_timing_matrix.md`, `results/schema_alias_admission_status_table.md` | policy layer; no dedicated runtime field by design | substantiated |
| `IRGenerator` の肥大化は研究概念ベースで分解可能である | `ir_generator_decomposition_plan.md`, `midterm_synthesis.md` | [check_resolution.py](/C:/workspace/NLP/src/ir_generator/check_resolution.py:1), [promotion_rules.py](/C:/workspace/NLP/src/ir_generator/promotion_rules.py:1), [target_resolution.py](/C:/workspace/NLP/src/ir_generator/target_resolution.py:1), [spec_role_rules.py](/C:/workspace/NLP/src/ir_generator/spec_role_rules.py:1) | implemented |

## Reading Rule

この表の `Current Status` は次の意味で使う。

- `substantiated`
  - benchmark と観測で主張は支えられているが、runtime 側に専用 field や専用 module を持たせる必要はない
- `implemented`
  - 主張が実装変更としても反映され、回帰対象になっている

## Current Best Use

この対応表は、次の用途で使うと価値が高い。

1. 中間報告で、主張が観測だけなのか実装まで到達したのかを短く示す
2. 新しい benchmark を追加するとき、どの claim に効くケースなのかを先に決める
3. 実装整理時に、どの helper/domain がどの研究主張に属しているかを見失わないようにする

## Immediate Next Step

次にやるべきことは、この表を使って
`未実装だが substantiated な主張`
と
`implemented だが未整理な主張`
を切り分けることである。

その整理ができると、研究と実装の次の優先順位をより明確に決められる。
