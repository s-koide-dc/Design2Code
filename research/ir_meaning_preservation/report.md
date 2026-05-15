# IR Meaning Preservation Research Report

## 1. Research Objective

本研究の目的は、自然言語で記述された設計仕様を IR へ変換する際に、
`どの意味が保存され、どの意味が失われるか`
を決定論的に説明することである。

ここで重視するのは、単純な生成精度ではない。
研究の中心は、

- 何を意味保存の必須 metadata と見なすか
- どこまでを runtime で解決するか
- どこからを schema / policy 側で扱うか

を、benchmark・実装・運用の 3 面で説明可能にすることにある。

最終的な研究問いは、[goal_state.md](research/ir_meaning_preservation/goal_state.md:1) で定義したとおり、

`決定論的な自然言語仕様処理において、意味保存を成立させる最小メタデータ体系と、その runtime / schema / policy の責務分担は何か`

である。

## 2. Initial Hypothesis And Evaluation Frame

初期段階では、意味保存の候補として次を対象に置いた。

- 処理順序
- 入出力依存
- 条件分岐
- 反復構造
- データソース種別
- 副作用種別

評価枠組みは [evaluation.md](research/ir_meaning_preservation/evaluation.md:1) で固定し、benchmark は [benchmark_cases.md](research/ir_meaning_preservation/benchmark_cases.md:1) に集約した。各ケースでは、

- Expected IR
- Observed IR
- Diff Notes
- Failure Mapping

の順で差分を記録し、横断結果は [results/failure_mapping.md](research/ir_meaning_preservation/results/failure_mapping.md:1) に整理した。

## 3. Main Findings

### 3.1 Main Meaning Loss Is Role Weakening

初期観測で明確になったのは、主要な失敗が
`構造全体の collapse`
より
`role weakening`
に集中していることだった。

代表例:

- `FILTER` が `FETCH` に落ちる
- `CHECK` が弱い一般 action に落ちる
- `CALCULATE` が `GENERAL/ACTION` に落ちる
- `RETURN`, `TRANSFORM`, `ITERATE`, `WRAP` が coarse runtime handling に吸収される

この観測は、[intent_drift_analysis.md](research/ir_meaning_preservation/archived_analysis/intent_drift_analysis.md:1)、[focused_role_analysis.md](research/ir_meaning_preservation/archived_analysis/focused_role_analysis.md:1)、[midterm_synthesis.md](research/ir_meaning_preservation/midterm_synthesis.md:1) で整理している。

### 3.2 Provenance Is Required In Addition To Resolved Value

resolved value だけでは downstream を安全に制御できないことも明確になった。

たとえば同じ `Total` でも、

- schema property として一意に決まったのか
- current scope から history-based に継承されたのか
- weak default のままなのか

で、生成してよいコードが変わる。

そのため本研究では、

- `entity_resolution`
- `subject_resolution`
- `predicate_resolution`
- `collection_resolution`
- `calculate_source_resolution`
- `calculate_target_resolution`
- `return_value_resolution`
- `transform_source_resolution`
- `iteration_source_resolution`

のような provenance metadata を役割ごとに導入した。

この層は [resolution_provenance_model.md](research/ir_meaning_preservation/resolution_provenance_model.md:1)、[cross_role_provenance_design.md](research/ir_meaning_preservation/cross_role_provenance_design.md:1)、[provenance_strength_policy_matrix.md](research/ir_meaning_preservation/provenance_strength_policy_matrix.md:1) で共通化している。

### 3.3 Alias Admission Is A Schema/Policy Problem

property alias の問題も、runtime heuristic を増やすより、
`いつ schema に admission するか`
の問題として扱う方が決定論性を保ちやすいと確認した。

本研究では alias admission timing を次の 5 根拠で整理した。

- `Hold For Evidence`
- `Repeated Spec Use`
- `Cross-Case Relevance`
- `Downstream Impact`
- `External Compatibility`

これは [schema_alias_admission_timing_matrix.md](research/ir_meaning_preservation/schema_alias_admission_timing_matrix.md:1) と [results/schema_alias_admission_status_table.md](research/ir_meaning_preservation/results/schema_alias_admission_status_table.md:1) にまとまっている。

## 4. Research Method

方法は、大きく 4 段階だった。

1. benchmark を定義し、期待 IR を固定する
2. Observed IR を採取し、failure mapping を行う
3. 最小 metadata / rule / downstream bridge を実装する
4. benchmark, regression table, playbook で運用可能な形に戻す

この循環を role ごとに繰り返し、個別修正ではなく共通原理へ昇格できるかを確認した。

## 5. Implemented Role Outcomes

現時点で、次の role は `upstream metadata -> downstream bridge/conservatism -> regression artifact` まで揃っている。

### 5.1 CHECK

- `check_kind`
- `check_subject`
- `subject_resolution`

### 5.2 FILTER

- promotion rule
- `predicate_resolution`
- `collection_resolution`
- weak/default provenance に対する保守停止

### 5.3 CALCULATE

- promotion rule
- `entity_resolution`
- `calculate_source_resolution`
- `calculate_target_resolution`
- ambiguous / weak target に対する保守停止

### 5.4 RETURN

- `return_value`
- `return_value_resolution`
- `return_source_node_id`
- literal / input-link / weak retention 境界

### 5.5 TRANSFORM

- weak-intent bridge
- `transform_op_resolution`
- `transform_source_resolution`

### 5.6 ITERATE

- `iteration_source_resolution`
- `iteration_item_entity`
- `iteration_item_var`
- nested child property continuity

### 5.7 WRAP

- deterministic `retry`
- explicit `timeout`
- explicit `transaction`
- retry default-policy provenance

### 5.8 DISPLAY

- item/property continuity と property-side provenance を consumer 側で保持

この状態は [remaining_open_inventory.md](research/ir_meaning_preservation/remaining_open_inventory.md:1) と [results/role_weakening_regression_table.md](research/ir_meaning_preservation/results/role_weakening_regression_table.md:1) に反映されている。

## 6. Runtime / Schema / Policy Boundary

本研究の最も重要な一般化は、意味保存を 1 本の runtime heuristic で扱わず、

- runtime
- schema
- policy

の 3 層に分けた点である。

### 6.1 Runtime

runtime の責務は、
`その specification step から決定論的に materialize できる metadata を IR に残すこと`
である。

ここには、

- `spec_role`
- resolved value
- provenance
- structural continuity
- downstream conservatism を切り替える resolution label

を置く。

### 6.2 Schema

schema の責務は、
`canonical knowledge を宣言的に保持すること`
である。

ここには、

- entity/property ownership
- canonical property 名
- admitted alias

を置く。

### 6.3 Policy

policy の責務は、
`何を admission し、weak metadata をどこまで許可するかを決めること`
である。

ここには、

- alias admission timing
- provenance-strength ごとの許可/停止
- TODO stop と generic fallback の境界

を置く。

この整理は [runtime_schema_policy_boundary.md](research/ir_meaning_preservation/runtime_schema_policy_boundary.md:1) に 1 枚で圧縮している。

## 7. Implementation Connection

研究主張は、文書だけでなく実装にも接続されている。

主要な接続先:

- [ir_generator.py](src/ir_generator/ir_generator.py:1)
- [check_resolution.py](src/ir_generator/check_resolution.py:1)
- [promotion_rules.py](src/ir_generator/promotion_rules.py:1)
- [target_resolution.py](src/ir_generator/target_resolution.py:1)
- [return_resolution.py](src/ir_generator/return_resolution.py:1)
- [transform_resolution.py](src/ir_generator/transform_resolution.py:1)
- [iterate_resolution.py](src/ir_generator/iterate_resolution.py:1)
- [wrapper_resolution.py](src/ir_generator/wrapper_resolution.py:1)
- [action_synthesizer.py](src/code_synthesis/action_synthesizer.py:1)
- [semantic_binder.py](src/code_synthesis/semantic_binder.py:1)
- [calc_ops.py](src/code_synthesis/action_handlers/calc_ops.py:1)
- [ir_emitter.py](src/code_synthesis/ir_emitter.py:1)

主張と根拠と実装の対応は [claim_evidence_implementation_map.md](research/ir_meaning_preservation/claim_evidence_implementation_map.md:1) に整理してある。

## 8. Operationalization

本研究は、単なる分析メモではなく運用入口まで持っている。

整備済みのもの:

- regression checklist
- role weakening regression table
- alias admission regression table
- combined playbook
- regression run template
- benchmark addition template
- validator
- runner

中心文書:

- [schema_alias_role_weakening_regression_checklist.md](research/ir_meaning_preservation/schema_alias_role_weakening_regression_checklist.md:1)
- [combined_regression_playbook.md](research/ir_meaning_preservation/combined_regression_playbook.md:1)
- [results/regression_run_2026_05_07_metadata_baseline.md](research/ir_meaning_preservation/results/regression_run_2026_05_07_metadata_baseline.md:1)
- [run_ir_meaning_preservation_regression.py](scripts/validate/run_ir_meaning_preservation_regression.py:1)
- [validate_ir_meaning_preservation_regression.py](scripts/validate/validate_ir_meaning_preservation_regression.py:1)

これにより、研究成果は変更時の運用フローに直接接続できる。

## 9. Remaining Open Issues

現時点で open issue は限定的である。

1. `WRAP` の non-explicit kind inference を runtime に入れるか
2. role 横断の定量比較をどこまで要求するか
3. final external report でどこまでさらに簡約するか

重要なのは、これらが
`まだ主要 metadata が見つかっていない`
問題ではなく、
`どこで研究を閉じるか`
の問題だという点である。

## 10. Conclusion

本研究の結論は次のように要約できる。

1. 意味損失の中心は structure collapse より role weakening と provenance under-capture にある
2. resolved value だけでなく provenance metadata を保持することで、安全な downstream conservatism を実装できる
3. alias 問題は runtime heuristic ではなく schema/policy の問題として扱う方が決定論性を保ちやすい
4. runtime / schema / policy の 3 層分離によって、意味保存の責務境界を説明可能にできる

したがって、この研究の成果は
`特定ケースの精度改善`
ではなく、
`決定論的な自然言語仕様処理における最小 metadata 体系と責務分担の提示`
にある。
