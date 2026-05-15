# IR Meaning Preservation Midterm Synthesis

## 1. Position

この文書は、`IR meaning preservation` 研究の中間統括である。

現時点の位置づけは、探索段階を終え、以下を一通り完了した段階にある。

1. 評価基準の固定
2. benchmark と期待 IR の整備
3. 実 IR の観測
4. 主要失敗類型の局所化
5. 最小設計変更と PoC 実装
6. `IRGenerator` 内部構造の研究概念ベース整理

したがって現在地は、`妥当性確認` の段階ではなく、`局所知見を一般原理としてまとめ始める段階` である。

## 2. Research Question

この研究の中心問いは次の 3 つに整理できる。

1. 設計仕様のどの意味要素が IR 上で保存され、どこで失われるのか
2. 意味損失は表現力の限界か、生成器実装の問題か
3. 保存した metadata は downstream code synthesis の保守性制御にも使えるか

## 3. What Is Now Established

### 3.1 Evaluation Baseline Is Fixed

少なくとも初期研究基盤は固定できている。

- 保存対象の観点は [evaluation.md](research/ir_meaning_preservation/evaluation.md:1) で定義済み
- benchmark coverage は [benchmark_cases.md](research/ir_meaning_preservation/benchmark_cases.md:1) で整理済み
- 初回 5 ケースの失敗分類は [failure_mapping.md](research/ir_meaning_preservation/results/failure_mapping.md:1) で固定済み

これにより、改善前後を比較するための基準面はすでに成立している。

### 3.2 Main Failure Modes Are No Longer Vague

主要失敗は、少なくとも次の 4 系統に絞れている。

- `Intent Drift`
- `Under-Spec Capture`
- `Dependency Loss`
- `Source Drift`

特に初期 5 ケースでは、`Structure Loss` よりも `Intent Drift` と `Under-Spec Capture` が中心であることが観測された。

### 3.3 Several Local Questions Have Reached PoC

次の論点では、観測だけでなく設計変更と再観測まで進んでいる。

- `CHECK`
- `CALCULATE`
- `FILTER`
- `RETURN`
- `TRANSFORM`
- `ITERATE`
- `WRAP`
- `DISPLAY`
- structural dependency
- `spec_role` / `runtime_role` separation

これは研究全体が、単なる diff 調査ではなく、設計仮説を実装で検証する段階に入っていることを意味する。

## 4. Main Findings

### 4.1 Meaning Loss Is More About Weakening Than Collapsing

初期観測の主結果は、現行系の失敗が「大構造を完全に壊す」より、「役割を弱く表現する」ことに寄る点である。

つまり主要課題は、

- `LOOP` や `CONDITION` が消えること
- 仕様全体が平坦化されること

ではなく、

- `FILTER` が `FETCH` に落ちる
- `CHECK` が `ACTION` に落ちる
- `CALCULATE` が `GENERAL/ACTION` に落ちる

という role-level weakening である。

### 4.2 Provenance Matters, Not Just Resolved Value

`CALCULATE` の `entity_resolution` で分かったことは、最終的な `target_entity` だけでは不十分だという点である。

必要なのは、

- `unique_owner`
- `explicit_entity`
- `history_fallback`
- `ambiguous`

のような「なぜそう解決したか」の保持である。

同じ発想は、`CHECK.subject_resolution` や `FILTER.predicate_resolution / collection_resolution` にも広げられることが確認できた。

### 4.3 Alias Admission Timing Is a Policy Layer, Not a Runtime Heuristic

alias 問題を追って分かったことは、
`解決できるか` と `今 schema に入れるべきか` は別問題だという点である。

特に admission timing は、

- `Hold For Evidence`
- `Repeated Spec Use`
- `Cross-Case Relevance`
- `Downstream Impact`
- `External Compatibility`

の 5 類型に整理でき、これは runtime の意味推定規則ではなく、
schema management の根拠分類として扱う方が自然である。

この整理により、alias coverage を辞書追加競争にせず、
決定論性を維持したまま運用できることが見えてきた。

representative case の current status は
`results/schema_alias_admission_status_table.md`
で横断確認できるようになった。

### 4.4 Metadata Can Control Downstream Conservatism

この研究の中で、最も重要な中間成果の一つは、IR metadata が downstream behavior を実際に制御できたことである。

代表例は `CALCULATE` である。

- 強い意味があるときだけ具体化する
- 曖昧なときは over-interpretation せず停止寄りに振る舞う

という policy を、`entity_resolution` を通じて作ることができた。

これは「意味保存のための注釈」が「安全な生成制御の入力」にもなりうることを示している。

### 4.5 Structural Dependency Can Be Expressed as a General Rule

`ELSE` 誤接続の修正と `LOOP` / `WRAPPER` への展開を通じて、依存規則は個別バグではなく、次の原理として記述できるところまで来た。

- 構造ブロック最初の子は structural parent に依存する
- 同一ブロック内の後続 sibling は直前 sibling に依存する

この原理は [structural_dependency_rule.md](research/ir_meaning_preservation/structural_dependency_rule.md:1) に固定され、実装側にも反映済みである。

## 5. What Has Been Implemented As Research-Backed Change

少なくとも以下は、研究文書と実装が対応付いた変更である。

- `spec_role` の保持
- `CHECK` metadata と `check_kind`
- `CHECK.subject_resolution`
- `CALCULATE` promotion
- `CALCULATE.entity_resolution`
- `CALCULATE` source / target provenance
- downstream conservatism for ambiguous `CALCULATE`
- `FILTER` promotion with predicate/context conditions
- `RETURN` literal / source provenance
- `TRANSFORM` source provenance
- `ITERATE` collection / item continuity
- `WRAP` retry / timeout / transaction consumer
- `DISPLAY` property-side provenance
- structural dependency repair for `ELSE` and block siblings
- `IRGenerator` decomposition aligned to research domains

この点は重要で、現時点の研究は「文書だけ」でも「コードだけ」でもなく、両者の往復として成立している。

## 6. What Is Not Yet Fully Established

### 6.1 Cross-Role Generalization Is Better, But Not Final

`entity_resolution` 相当の由来 metadata は、当初は `CALCULATE` で最も成熟していたが、現在は `RETURN`, `TRANSFORM`, `ITERATE`, `WRAP`, `DISPLAY` までかなり広がっている。

ただし、

- すべての role で定量比較があるわけではない
- wrapper kind の非明示推定は未実施である
- `runtime / schema / policy` の最終境界主張はまだ圧縮余地がある

### 6.2 Summary-Level Claim Is Stronger Than Paper-Level Claim

中間段階としては十分な知見があるが、論文化レベルの強さにはまだ不足がある。

不足しているのは主に次の点である。

- role 横断の統一理論
- 失敗改善の定量比較
- 他 role への一般化境界

### 6.3 IRGenerator Decomposition Is Advanced but Not Final

[ir_generator_decomposition_plan.md](research/ir_meaning_preservation/ir_generator_decomposition_plan.md:1) に沿って、domain helper 化と in-file decomposition はかなり進んだ。

ただしこれは最終アーキテクチャではない。

現時点の意味は、

- 研究概念と実装責務の対応が見えるようになった
- 今後の service-level extraction の候補が明確になった

という点にある。

## 7. Current Thesis-Level Claims

現時点で、かなり自信を持って言える中間主張は次の 4 点である。

1. このプロジェクトの主要な意味損失は structure collapse より role weakening と provenance under-capture にある
2. `spec_role` や resolution provenance のような metadata は、meaning preservation の記録だけでなく downstream conservatism の制御にも使える
3. alias admission timing は runtime heuristic ではなく policy-driven schema management の問題として扱う方が決定論性を保ちやすい
4. `IRGenerator` の肥大化問題は、研究概念に沿った decomposition によって整理可能であり、少なくとも `CHECK`, `Promotion`, `Target Resolution`, `Spec Role`, structural dependency の単位は安定している

## 8. Current Phase Assessment

研究フェーズとしては次のように評価できる。

- `Phase 1: baseline construction`
  - 完了
- `Phase 2: major failure localization and PoC`
  - 完了に近い
- `Phase 3: generalization and synthesis`
  - 後半

したがって、今は「次のケースを増やすこと」そのものより、「どの知見を一般原理として主張し、どこで閉じるか」を整理する優先度が高い。

## 9. Recommended Next Step

中間統括の次にやるべきことは、次のどれかである。

1. closed role 群の横断 summary と未解決 inventory を揃える
2. `claim -> evidence -> implementation -> checklist` の一貫性を最終点検する
3. ここまでの成果を外向け報告用にさらに圧縮する

現段階では、新論点を広げるより、この 3 つで研究を閉じに行く方が価値が高い。
