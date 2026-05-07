# IR Meaning Preservation

## Purpose

このテーマは、自然言語で記述された設計仕様を IR に変換する際に、どの意味情報が保存され、どの意味情報が失われるかを明らかにすることを目的とする。

ここでいう「意味保存」は、コード生成結果の見た目ではなく、仕様の論理構造が IR 上で保持されているかどうかを指す。

## Initial Scope

初期段階では、以下の要素を保存対象候補として扱う。

- 処理順序
- 入出力依存
- 条件分岐
- 反復構造
- データソース種別
- 副作用の種別

## First Questions

- どの設計書要素を IR の必須意味情報と見なすべきか
- 現行 IR はどの要素を安定して保持できているか
- どの種類の仕様で意味損失が起こりやすいか
- 意味損失は IR 表現の限界か、生成器実装の問題か

## Immediate Next Steps

1. 意味保存の評価観点を定義する
2. `scenarios/` から比較用ケースを選ぶ
3. ケースごとに期待 IR を人手で定義する
4. 現行 IR 生成結果との差分を分類する

## Current Documents

- `document_map.md`: 文書の分類規約と整理方針

### Foundation

- `evaluation.md`: 評価単位、保存対象、失敗類型、フェーズ 1 の完了条件
- `role_layer_definition.md`: `spec_role` と `runtime_role` の責務分離定義
- `structural_dependency_rule.md`: 構造親依存と sibling 依存を分ける `input_link` 規則
- `structural_role_bridge.md`: `WRAP`, `ITERATE`, `CALCULATE` の橋渡し方針
- `check_role_refinement.md`: `CHECK` を `check_kind` 単位で細分化し、IR 保持項目と downstream 利用方針を定義
- `resolution_provenance_model.md`: `CALCULATE` の解決由来 metadata を `CHECK` / `FILTER` へ拡張する共通モデル
- `cross_role_provenance_design.md`: `CHECK`, `FILTER`, `CALCULATE` を `resolved value + provenance + policy` の共通枠組みで読むための横断設計
  - 初期実装として、`CALCULATE` に加えて `CHECK` / `FILTER` にも provenance-strength ベースの downstream conservatism を最小適用済み
  - `history_based` provenance についても、停止一辺倒ではなく exact-scope / generic-logic 限定の中間 policy を導入済み
- `provenance_strength_policy_matrix.md`: provenance-strength を `CHECK` / `FILTER` / `CALCULATE` 横断で許可操作・禁止操作・exact-scope rule に対応付けた判定表
- `calculate_target_entity_ambiguity_rule.md`: `CALCULATE` の property owner が一意でない場合に `target_entity` を誤補正しない規則
- `calculate_entity_resolution_policy.md`: `entity_resolution` の 4 類型を downstream でどう扱うかの統一方針

### Analysis

- `intent_drift_analysis.md`: 最優先失敗類型としての Intent Drift の局所分析
- `dependency_loss_analysis.md`: 依存エッジ損失を role 論点から分離した局所分析
- `focused_role_analysis.md`: `DESERIALIZE`, `FILTER`, `CHECK` の局所分析
- `filter_fetch_collapse_analysis.md`: `FILTER` が provenance 前段で `FETCH` に落ちる原因の局所分析
- `calculate_role_analysis.md`: `CALCULATE` が `GENERAL/ACTION` に弱化する発生条件の局所分析
- `review_adoption.md`: 外部レビュー提案の採用可否と今後の研究優先順

### Design Proposal

- `minimal_design_change_proposal.md`: `spec_role` を IR に保持するための最小設計変更案
- `calculate_promotion_rule.md`: `CALCULATE` へ昇格させる最小規則の設計
- `filter_promotion_rule.md`: 曖昧語彙を含む step を `FILTER` へ上げる最小規則の設計
- `property_side_provenance_promotion_rule.md`: `CHECK` / `FILTER` の property-side provenance を `schema_backed` / `history_based` へ持ち上げる最小規則
  - first implementation として、schema 上の canonical property 名または explicit alias が直接得られるケースでは `subject_resolution` / `predicate_resolution` を昇格できる状態にした
- `schema_alias_supply_model.md`: lexical property token を canonical property へ deterministic に写すための alias 供給モデル
- `schema_alias_coverage_policy.md`: alias をどこまで `entity_schema` に追加してよいか、その coverage 境界と admission/rejection rule
- `schema_alias_admission_threshold.md`: owner-confined でも benchmark need が弱い alias をいつ admission するかの閾値定義
- `schema_alias_admission_timing_matrix.md`: alias admission timing の 5 類型を横断比較する matrix
- `ir_generator_decomposition_plan.md`: 肥大化した `IRGenerator` を研究概念ごとに整理する段階的分割方針
- 現在の分割進捗: `src/ir_generator/check_resolution.py`, `src/ir_generator/promotion_rules.py`, `src/ir_generator/target_resolution.py`, `src/ir_generator/spec_role_rules.py` まで module-level helper 化済み
- structural dependency はまだ `generate()` 主経路に残しつつ、chaining / block attachment 判定まで in-file helper 化済み
- あわせて `final intent/runtime-role coercion` と `node emission` 前段の source/cardinality/node-shape も in-file helper 化済み
- auto-inserted `JSON_DESERIALIZE` / serialize bridge node の挿入も in-file helper 化済み
- `Phase 3` の role-specific semantic resolution も helper に束ね、structure role / CHECK / CALCULATE の処理を主経路から分離済み
- `ELSE` / `END`, duplicate `DATABASE_QUERY` skip, context-history 更新も helper 化し、`generate()` はほぼ orchestration skeleton 化済み

### Cases

- `benchmark_cases.md`: 初期比較ケースの選定とカバレッジ整理
- `cases/`: benchmark ごとの期待 IR、Observed IR、差分、失敗類型
- 優先 5 ケースの期待 IR には `semantic_map.semantic_roles.spec_role` を付与済み
- `cases/case_16_filter_predicate_provenance.md` と `case_17_check_subject_provenance.md`: provenance metadata を `FILTER` / `CHECK` へ広げる次段ケース

### Results

- `results/`: 採取した実 IR とケース横断の差分要約
- `results/failure_mapping.md`: ケースごとの失敗類型の正式整理
- `results/intent_drift_trace.md`: `_analyze_step_integrated` と最終 IR の比較観測
- `results/dependency_loss_trace.md`: `RobustConfigLoader` の誤接続を `IRGenerator` 実装レベルで追跡した記録
- `results/role_mapping_matrix.md`: 期待 `spec_role` と観測 `runtime_role` の対応整理
- `results/structural_dependency_observation.md`: 構造親依存規則の観測結果
- `results/calculate_case_observation.md`: `CALCULATE` 補助ケースの観測結果
- `results/provenance_case_observation.md`: provenance metadata 拡張ケースの初回観測結果
- `results/provenance_strength_boundary_observation.md`: provenance-strength の `schema_backed` / `history_based` 境界を観測した結果
- `results/schema_alias_supply_observation.md`: schema alias 供給あり/なし contrast を観測した結果
- `results/schema_alias_coverage_observation.md`: alias coverage の admission / rejection contrast を観測した結果
- `results/schema_alias_tier2_observation.md`: alias coverage policy の `Tier 2` admission / rejection contrast を観測した結果
- `results/schema_alias_admission_threshold_observation.md`: alias admission timing の 5 類型を観測した結果
- `results/schema_alias_admission_status_table.md`: alias admission timing の current status を表形式で整理した結果
- `results/schema_alias_admission_regression_table.md`: alias admission timing を policy root / IR effect / regression check 単位で横断比較する回帰用の基準表
- `results/regression_run_2026_05_07_metadata_baseline.md`: 現行 metadata-driven 実装を baseline として固定した初回 regression run 記録
- `results/role_weakening_regression_table.md`: role weakening を role 単位で横断比較する regression 用の基準表

### Summary

- `calculate_metadata_conservatism_summary.md`: `CALCULATE` を題材に、IR metadata が downstream の保守性を制御できたことの中間まとめ
- `midterm_synthesis.md`: 研究全体の現在地、主要知見、未解決課題、次段の論点を横断整理した中間統括
- `research_outcome_memo.md`: `role / provenance / alias admission timing` の 3 層を 1 ページで要約した成果メモ
- `executive_summary.md`: 外向け説明向けにさらに圧縮した短い要約
- `claim_evidence_implementation_map.md`: 研究主張、観測根拠、実装箇所の対応表
- `implementation_priority_from_claims.md`: claim/evidence/implementation の差分から導いた次の実装優先順位
- `schema_alias_role_weakening_regression_checklist.md`: schema alias と role weakening の回帰確認に使う checklist
- `combined_regression_playbook.md`: role weakening と alias admission の 2 系統を 1 つの回帰実行手順へ束ねた playbook
- `../../scripts/validate/run_ir_meaning_preservation_regression.py`: playbook の最小手順を 1 コマンドで実行する helper
- `../../scripts/validate/validate_ir_meaning_preservation_regression.py`: regression run 記録の構造と関連成果物を半自動で検証する補助スクリプト
- `goal_state.md`: この研究の done 条件と着地点を明文化した文書
- `../templates/ir_meaning_preservation_regression_run_template.md`: schema alias / role weakening の回帰確認を 1 回分記録するテンプレート
- `../templates/ir_meaning_preservation_benchmark_addition_template.md`: benchmark 追加時に claim, timing root, observation 更新点を固定するテンプレート

## Related Sources

- `docs/ir_design.md`
- `docs/generate_from_design_dataflow.md`
- `src/ir_generator`
- `src/code_synthesis`
