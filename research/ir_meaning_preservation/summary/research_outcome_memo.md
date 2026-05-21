# IR Meaning Preservation Research Outcome Memo

## Purpose

この文書は、`IR meaning preservation` 研究の現時点の成果を 1 ページで把握するための要約メモである。

詳細な根拠やケース差分は個別文書に譲り、ここでは

- 何が分かったか
- 何を実装で確認できたか
- 研究上の主張をどこまで言えるか

だけを短く固定する。

## Core Claim

この研究の中心的な結論は次の 3 点である。

1. 主要な意味損失は structure collapse より `role weakening` と `provenance under-capture` にある
2. `spec_role` や resolution metadata は、意味保存の記録だけでなく downstream conservatism の制御にも使える
3. alias admission は runtime heuristic ではなく policy-driven schema management の問題として扱う方が決定論性を保ちやすい

## Three Organized Layers

### 1. Role Layer

- `spec_role` と `runtime_role` を分離した
- `CHECK`, `FILTER`, `CALCULATE`, `RETURN`, `TRANSFORM`, `ITERATE`, `WRAP`, `DISPLAY` の role weakening / provenance under-capture を観測し、局所 PoC で改善した
- role 保存は upstream IR quality の主問題であり、単なるコード生成後処理ではない

代表文書:

- `role_layer_definition.md`
- `focused_role_analysis.md`
- `minimal_design_change_proposal.md`

### 2. Provenance Layer

- `entity_resolution`, `subject_resolution`, `predicate_resolution`, `collection_resolution` を導入した
- 強い解決と弱い解決を区別し、その強度で downstream を保守化できることを確認した
- provenance は resolved value の補助情報ではなく、解釈可能性と安全生成の中間層になっている

代表文書:

- `cross_role_provenance_design.md`
- `provenance_strength_policy_matrix.md`
- `calculate_metadata_conservatism_summary.md`

### 3. Alias Admission Timing Layer

- alias を「解けるか」ではなく「いつ schema に入れるべきか」で整理した
- `Hold For Evidence`, `Repeated Spec Use`, `Cross-Case Relevance`, `Downstream Impact`, `External Compatibility` の 5 類型を benchmark で固定した
- admission timing は runtime rule ではなく schema policy の根拠分類として扱うのが自然だと確認した

代表文書:

- `schema_alias_admission_threshold.md`
- `schema_alias_admission_timing_matrix.md`
- `results/schema_alias_admission_status_table.md`

## Implementation-Backed Outcomes

少なくとも次は、研究文書と実装変更が対応付いている。

- `spec_role` の IR 保持
- `CHECK` metadata と `check_kind`
- `CHECK.subject_resolution`
- `FILTER` promotion と property-side provenance
- `CALCULATE` promotion と `entity_resolution`
- `CALCULATE` source / target provenance
- weak / ambiguous provenance に対する downstream conservatism
- `RETURN` literal / source provenance
- `TRANSFORM` source provenance
- `ITERATE` collection / item continuity
- `WRAP` retry / timeout / transaction consumer
- `DISPLAY` property-side provenance
- structural dependency の一般規則化
- `IRGenerator` の研究概念ベース分解

## What This Means

現時点での研究価値は、単に個別精度を上げたことではない。

価値があるのは、

- どの metadata を保持すべきか
- その metadata をどう読めば安全な生成制御につながるか
- どの判断を runtime ではなく schema / policy 側へ置くべきか

を、benchmark と実装の両方で説明できるようになった点にある。

## Current Limitation

まだ完全ではない点も明確である。

- role 横断の定量比較は薄い
- provenance は `CALCULATE` から `RETURN` / `TRANSFORM` / `ITERATE` / `WRAP` / `DISPLAY` まで広がったが、cross-role の定量比較はまだ薄い
- alias policy は整理できたが、maintenance cost と運用フローの最終形は未確定である
- wrapper kind の非明示推定や wrapper 一般化はまだ open issue である

補足:

- `runtime_schema_policy_boundary.md` により、`runtime / schema / policy` の責務境界そのものは 1 枚で説明できる状態になった
- したがって残課題は、境界の未定義というより open issue の打ち切り条件をどう置くかに移っている

## Current Best Next Step

次にやるべきことは、新しい role を広げることではなく、

- closed role 群の横断 summary を揃える
- open issue を inventory 化する
- 必要なら外向け報告へさらに圧縮する

の順で研究を閉じに行くことである。
