# IR Meaning Preservation Benchmark Cases

## 1. Purpose

この文書は、`IR meaning preservation` の第 1 段階で使用する比較ケースを確定するためのものである。

選定方針は、生成成功率の高いケースを集めることではなく、IR が保持すべき意味構造の境界条件を偏りなく含めることである。

## 2. Selection Policy

今回の初期ベンチマークでは、以下の観点が最低 1 回以上現れるようにケースを選ぶ。

- 直列処理
- 条件分岐
- ループ
- データ依存の連鎖
- ファイル I/O
- DB ソース
- HTTP ソース
- env/stdin のような非ファイル入力
- JSON 自動チェーンが発生しやすいケース
- `refs` や input link が崩れたときに検出しやすいケース

## 3. Selected Cases

### Case 01: `StdinToStdoutTransform.design.md`

用途:

- 最小の直列変換ケース
- `FETCH -> TRANSFORM -> DISPLAY` の基本連鎖確認
- `stdin` という非ファイル source の保持確認

主な確認点:

- source_kind=`stdin` が保持されるか
- 変換処理が独立ノードとして表現されるか
- 依存関係が直列に接続されるか

### Case 02: `EnvConfigToConsole.design.md`

用途:

- 複数 source を単一の変換へ束ねるケース
- `env` source と整形 `ops` の保持確認

主な確認点:

- 複数 `FETCH` の結果が 1 つの `TRANSFORM` に集約されるか
- source_kind=`env` が保持されるか
- `ops:format_kv` 相当の意味が落ちないか

### Case 03: `ComplexLinqSearch.design.md`

用途:

- JSON 読み込みからフィルタ連鎖までの標準的な逐次処理ケース
- `FETCH -> JSON_DESERIALIZE -> LINQ -> LINQ -> DISPLAY` の多段依存確認

主な確認点:

- JSON デシリアライズを明示ノードとして保持できるか
- `LINQ` が前段結果に依存して直列接続されるか
- `semantic_roles.property` が意味情報として残るか

### Case 04: `BatchProcessProducts.design.md`

用途:

- `LOOP` と `END` を含む最小反復ケース
- ループ内部ノードのぶら下がり方の確認

主な確認点:

- `LOOP` が構造ノードとして保持されるか
- ループ本体の `DISPLAY` が `children` 側へ正しく入るか
- 平坦化されずにネスト構造が維持されるか

### Case 05: `RobustConfigLoader.design.md`

用途:

- `CONDITION / ELSE / END` を含む最小分岐ケース
- 構造制御ノードの接続確認

主な確認点:

- `CONDITION` と `ELSE` が 1 つの分岐として保持されるか
- `then` 側と `else` 側のステップが取り違えられないか
- 条件ノードへの依存が後続処理に残るか

### Case 06: `FetchProductInventory.design.md`

用途:

- DB source を持つ最小ケース
- `DATABASE_QUERY -> DISPLAY` の単純な外部ソース利用確認

主な確認点:

- source_kind=`db` と source_ref が保持されるか
- `semantic_roles.sql` が IR の意味補助情報へ残るか
- 外部ソース読み出しが一般 `FETCH` と混同されないか

### Case 07: `StateUpdatePersist.design.md`

用途:

- `DATABASE_QUERY -> CALC -> PERSIST` の状態更新ケース
- 読み取り結果に基づく更新と保存の境界確認

主な確認点:

- `FETCH/QUERY` と `PERSIST` の境界が保持されるか
- 更新対象の状態変更が中間計算として表現されるか
- 保存ステップが前段の取得結果に依存したまま残るか

### Case 08: `SyncExternalData.design.md`

用途:

- `http` と `db` の複数データソースを跨ぐ同期ケース
- `HTTP_REQUEST -> JSON_DESERIALIZE -> PERSIST` の連鎖確認

主な確認点:

- source_kind=`http` と source_kind=`db` の両方が崩れず保持されるか
- HTTP 取得結果が JSON 変換を経て保存へ接続されるか
- source_ref や refs の取り違えが起きないか

### Case 09: `SecureOrderProcessing.design.md`

用途:

- `DATABASE_QUERY -> LINQ -> LOOP -> HTTP_REQUEST` の複合ケース
- フィルタ後の集合をループ処理する構造確認

主な確認点:

- フィルタ結果が loop 対象として接続されるか
- loop 内の `HTTP_REQUEST` が子ノードになるか
- 集合処理から副作用処理への流れが壊れないか

### Case 10: `InputLinkDropRepro.design.md`

用途:

- `refs` と input link の崩れを意図的に観察する再現ケース
- 失敗類型の分類基準づくりに使う

主な確認点:

- 不自然な `refs` がどのように IR に反映されるか
- dependency loss や source drift をどう検出するか
- 正常系ベンチマークとは別に、差分分類用ケースとして扱えるか

## 4. Coverage Summary

各ケースが主にカバーする観点を以下にまとめる。

| Case | Serial | Condition | Loop | File/StdIO/Env | DB | HTTP | JSON Chain | Dependency Stress |
|---|---|---|---|---|---|---|---|---|
| StdinToStdoutTransform | Yes | No | No | stdin | No | No | No | Low |
| EnvConfigToConsole | Yes | No | No | env | No | No | No | Medium |
| ComplexLinqSearch | Yes | No | No | file | No | No | Yes | Medium |
| BatchProcessProducts | Yes | No | Yes | file | No | No | Yes | Medium |
| RobustConfigLoader | Yes | Yes | No | file | No | No | No | Medium |
| FetchProductInventory | Yes | No | No | No | Yes | No | No | Low |
| StateUpdatePersist | Yes | No | No | No | Yes | No | No | Medium |
| SyncExternalData | Yes | No | No | No | Yes | Yes | Yes | High |
| SecureOrderProcessing | Yes | No | Yes | No | Yes | Yes | No | High |
| InputLinkDropRepro | Yes | No | No | file | Yes | No | No | Very High |

## 5. Cases Deferred for Later

今回の初期セットには含めないが、後段で追加候補とするケースは以下である。

- `CalculateOrderDiscount.design.md`
  理由: 条件計算の意味表現として有用だが、初期段階では `CONDITION` 明示ケースを優先する。
- `InferThenFreezeMinimal.design.md`
  理由: 設計補完研究との境界が強く、IR 単体の意味保存評価と混ざりやすい。
- `CsvSalesAggregation.design.md`
  理由: 集約系の評価には有効だが、初期の構造保持評価より一段後に回す。
- `ExplicitJsonDeserialize.design.md` と暗黙 JSON chain の対比較
  理由: 明示仕様ノードと自動補助ノードの境界、および `Over-Inference` の評価に有効。
- `RetryWrapperMinimal.design.md`
  理由: `WRAPPER` が対象ステップを正しく包むかを独立に評価するため。
- `NegativeCheckPair.design.md`
  理由: `not exists` / `not null` の否定条件が二重否定へ崩れないかを比較しやすい。
- `CalculateAmbiguousPropertyOwner.design.md`
  理由: `CALCULATE` の property owner が複数 entity にまたがるとき、`target_entity` を誤補正しないことを独立に評価するため。

## 6. Next Action

次の作業では、上記 10 ケースのうち優先度の高い 5 件から期待 IR を人手で定義する。

優先着手順:

1. `StdinToStdoutTransform.design.md`
2. `ComplexLinqSearch.design.md`
3. `BatchProcessProducts.design.md`
4. `RobustConfigLoader.design.md`
5. `SyncExternalData.design.md`

## 7. CHECK-Focused Supplemental Cases

`CHECK` の研究は、上記 10 ケースだけでは `check_kind` 単位の比較に十分ではない。

そのため、実装前の補助ベンチマークとして次の 3 ケースを追加する。

### Check Case A: File Exists Check

用途:

- `exists_check` を単独で観察する
- file source と条件ノードの結合を確認する

主な確認点:

- `spec_role=CHECK` が保持されるか
- `check_kind=exists_check` が明示されるか
- `source_ref/source_kind` が条件ノードに残るか

対応ケース:

- `research/ir_meaning_preservation/cases/case_06_check_exists_file.md`

### Check Case B: Null Guard Check

用途:

- `null_check` を単独で観察する
- fetch 結果に対する null guard を条件ノードとして保持できるか確認する

主な確認点:

- `check_kind=null_check` が明示されるか
- `check_subject` と `expected_truth` が保持されるか
- `then/else` の分岐先が guard 意味に沿って接続されるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_07_check_null_guard.md`

### Check Case C: Numeric Comparison Check

用途:

- `comparison_check` を単独で観察する
- 比較演算と比較対象値が IR に保持されるか確認する

主な確認点:

- `check_kind=comparison_check` が明示されるか
- `check_operator` と `check_value` が保持されるか
- `FILTER` と `CHECK` の境界が崩れないか

対応ケース:

- `research/ir_meaning_preservation/cases/case_08_check_numeric_comparison.md`

## 8. Provenance-Focused Supplemental Cases

`CALCULATE` で成立した provenance model を他 role に広げるため、次段では次の 2 ケースを追加する。

### Provenance Case A: Filter Predicate Provenance

用途:

- `FILTER` の predicate がどの根拠から解決されたかを観察する
- `logic_goal` 由来と `explicit_ops` 由来の境界を固定する

主な確認点:

- `spec_role=FILTER` が保持されるか
- `predicate_resolution` が `logic_goal` / `explicit_ops` を区別できるか
- `collection_resolution` が前段集合への明示依存を保持できるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_16_filter_predicate_provenance.md`

### Provenance Case B: Check Subject Provenance

用途:

- `CHECK` の subject がどの根拠から解決されたかを観察する
- `quoted_literal` 由来と `history_subject` 由来の境界を固定する

主な確認点:

- `spec_role=CHECK` が保持されるか
- `subject_resolution` が `quoted_literal` / `history_subject` / `default_subject` を区別できるか
- downstream condition generation の保守性に差が付けられるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_17_check_subject_provenance.md`

## 9. Provenance Strength Boundary Cases

`provenance_strength_policy_matrix.md` の妥当性を確かめるため、`schema_backed` と `history_based` の境界を直接観測する補助ケースを追加する。

### Boundary Case A: Check Exact-Scope Boundary

用途:

- `CHECK` で `schema_backed` と `history_based` の差を観察する
- global には曖昧な property が、current target scope に閉じたときだけ解決されることを確認する

主な確認点:

- unique property owner では `subject_resolution=schema_property` を保持できるか
- ambiguous property owner では global reverse lookup に滑らず `history_subject` に留まるか
- downstream comparison generation が exact target scope を越えないか

対応ケース:

- `research/ir_meaning_preservation/cases/case_18_check_provenance_strength_boundary.md`

### Boundary Case B: Filter Exact-Scope Boundary

用途:

- `FILTER` で `schema_backed` と `history_based` の差を観察する
- unique property owner と current collection scope 依存の property resolution を比較する

主な確認点:

- unique property owner では `predicate_resolution=schema_property` を保持できるか
- ambiguous property owner では `history_predicate` に留まり、global reverse lookup に滑らないか
- `history_based` で strong shortcut を避けつつ generic logic path へ落とせるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_19_filter_provenance_strength_boundary.md`

## 10. Alias Supply Contrast Cases

`schema_alias_supply_model.md` を benchmark 上で評価するため、alias 供給の有無を直接比較する補助ケースを追加する。

### Alias Case A: Alias-Supplied Canonicalization

用途:

- schema に explicit alias があるとき、lexical property token が canonical property へ deterministic に写るかを確認する
- supply model が成立しているケースを固定する

主な確認点:

- lexical property token が canonical property へ正しく変換されるか
- `CHECK` / `FILTER` の property-side provenance が `schema_property` または `history_*` へ昇格できるか
- alias 供給と provenance promotion の責務が分離して読めるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_20_schema_alias_supplied_canonicalization.md`

### Alias Case B: Alias-Missing Weak Retention

用途:

- schema に alias が無いとき、lexical property token が weak provenance に留まることを確認する
- supply failure を promotion failure と区別するための contrast case とする

主な確認点:

- canonical property が決まらないときに無理な昇格が起きないか
- `CHECK` は `explicit_subject` / `default_subject` に留まるか
- `FILTER` は `logic_goal` / `default_predicate` に留まるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_21_schema_alias_missing_weak_retention.md`

## 11. Alias Coverage Policy Contrast Cases

`schema_alias_coverage_policy.md` を benchmark 上で評価するため、`許可 alias` と `拒否 alias` の contrast を追加する。

### Coverage Case A: Allowed Alias Admission

用途:

- Tier 1 / Tier 2 の許可 alias が canonicalization に使われてよいことを確認する
- alias supply と provenance promotion の結合が policy 上も妥当であることを確認する

主な確認点:

- allowed alias が canonical property へ deterministic に写るか
- `CHECK` / `FILTER` の property-side provenance が `schema_property` または `history_*` へ上がるか
- owner explanation を持つ alias だけが admission されているか

対応ケース:

- `research/ir_meaning_preservation/cases/case_22_allowed_alias_admission.md`

### Coverage Case B: Disallowed Generic Alias Rejection

用途:

- Tier 3 の拒否 alias が weak retention に留まることを確認する
- coverage を上げるために generic alias を入れない判断が正しいことを観測する

主な確認点:

- generic alias が canonical property へ誤って写らないか
- `CHECK` は `explicit_subject` / `default_subject` に留まるか
- `FILTER` は `logic_goal` / `default_predicate` に留まるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_23_disallowed_generic_alias_rejection.md`

## 12. Revised Next Action

`CHECK` と構造依存に続く `CALCULATE` 系の次段では、次の 2 系統を優先する。

1. unique property owner ケース
2. ambiguous property owner ケース

特に後者は、`CALCULATE` を上げられることよりも、「上げたあとに誤って entity を決め打ちしないこと」を評価対象とする。

対応ケース:

- unique owner: `research/ir_meaning_preservation/cases/case_12_calculate_with_target_hint.md`
- ambiguous owner: `research/ir_meaning_preservation/cases/case_14_calculate_ambiguous_property_owner.md`
- history fallback gap: `research/ir_meaning_preservation/cases/case_15_calculate_history_fallback_gap.md`

`CHECK` 実装へ進む前に、上記 3 補助ケースで期待 IR を固定し、`check_kind` が必要になる比較単位を先に確定する。

## 13. Post-CHECK Additions

`CHECK` の PoC 後に追加すべき比較テーマとして、次を固定する。

1. `Dependency Loss` を観察するための edge-focused ケース
2. 明示チェーン vs 自動チェーンの比較ケース
3. `LOOP` / `WRAPPER` の構造境界を観察するケース
4. 否定系 `CHECK` の比較ケース

## 14. Structural Dependency Supplemental Cases

`structural_dependency_rule.md` の妥当性を確かめるため、次の 3 ケースを追加する。

### Structural Case A: Condition Branch Dependency

用途:

- `CONDITION.children` と `CONDITION.else_children` の first-child / second sibling を同時に観察する
- `structural_parent_dependency` と `sequential_sibling_dependency` の切替規則を確認する

主な確認点:

- then 側 first-child が条件ノードへ依存するか
- else 側 first-child が条件ノードへ依存するか
- then 側 second sibling が first-child へ依存するか

対応ケース:

- `research/ir_meaning_preservation/cases/case_09_condition_branch_dependency.md`

### Structural Case B: Loop Body Dependency

用途:

- loop body の first-child / second sibling / nested child を観察する
- loop 親依存と body 内逐次依存を区別できるか確認する

主な確認点:

- body first-child が loop ノードへ依存するか
- body second sibling が first-child へ依存するか
- loop 内 nested condition の first-child が nested 構造親へ依存するか

対応ケース:

- `research/ir_meaning_preservation/cases/case_10_loop_body_dependency.md`

### Structural Case C: Wrapper Scope Dependency

用途:

- wrapper 配下で first-child / second sibling / nested child を観察する
- wrapper が作る実行文脈が children に反映されるか確認する

主な確認点:

- wrapper first-child が wrapper ノードへ依存するか
- wrapper second sibling が first-child へ依存するか
- wrapper 内 nested loop の first-child が nested loop 親へ依存するか

対応ケース:

- `research/ir_meaning_preservation/cases/case_11_wrapper_scope_dependency.md`

## 15. CALCULATE Supplemental Cases

`calculate_role_analysis.md` の検証用に、次の 2 ケースを追加する。

### Calculate Case A: Explicit Target Hint

用途:

- `semantic_roles.target_hint` 相当の計算対象が明確な場合に `CALCULATE` が立つかを観察する
- downstream bridge 以前の upstream detection 安定性を確認する

主な確認点:

- `intent=CALC` に上がるか
- `role=CALC` が保持されるか
- `spec_role=CALCULATE` が保持されるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_12_calculate_with_target_hint.md`

### Calculate Case B: Implicit Calculation Phrase

用途:

- 「価格を計算する」のような曖昧な自然言語だけで `CALCULATE` が立つかを観察する
- explicit metadata なしでの弱化条件を比較する

主な確認点:

- `GENERAL/ACTION` に落ちるか
- `logic_goals` が空のままになるか
- `target_hint` 不足が検出安定性にどう影響するか

対応ケース:

- `research/ir_meaning_preservation/cases/case_13_calculate_without_target_hint.md`

## 16. Alias Coverage Tier 2 Cases

`schema_alias_coverage_policy.md` の `Tier 2: Conditionally Allowed` を benchmark で閉じるため、次の 2 ケースを追加する。

### Alias Coverage Case A: Conditional Alias With Owner Explanation

用途:

- owner explanation が可能な conditional alias が admission されるかを確認する
- abbreviation 自体ではなく owner-confined / benchmark-driven 条件が効いているかを観察する

主な確認点:

- `受注No -> OrderNumber` が canonical property へ上がるか
- `CHECK.subject_resolution` が `schema_property` まで上がるか
- `FILTER.predicate_resolution` が `schema_property` まで上がるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_24_conditional_alias_with_owner_explanation.md`

### Alias Coverage Case B: Generic Abbreviation Rejection

用途:

- owner explanation を欠く generic abbreviation が conditional alias として admission されないことを確認する
- coverage 過剰による誤 canonicalization を防げているかを観察する

主な確認点:

- `No` が lexical token のまま残るか
- `CHECK.subject_resolution` が `explicit_subject` に留まるか
- `FILTER.predicate_resolution` が `logic_goal` に留まるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_25_generic_abbreviation_rejection.md`

### Alias Coverage Case C: Legacy Field Bridge Admission

用途:

- `Tier 2` の `legacy field bridge` が `compound-part shorthand` と同じ admission 条件で説明できるかを確認する
- category の違いではなく deterministic admission 条件が本質であることを観察する

主な確認点:

- `伝票金額 -> OrderAmount` が canonical property へ上がるか
- `CHECK.subject_resolution` が `schema_property` まで上がるか
- `FILTER.predicate_resolution` が `schema_property` まで上がるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_26_legacy_field_bridge_admission.md`

## 17. Alias Admission Threshold Cases

`schema_alias_admission_threshold.md` の `Hold For Evidence` と `Repeated Spec Use` を benchmark で閉じるため、次の 2 ケースを追加する。

### Alias Threshold Case A: Admissible But Deferred

用途:

- owner-confined かつ deterministic でも、evidence が弱ければ lexical retention に留めるべきことを確認する
- `can_admit` と `should_admit_now` を分けて読めるようにする

主な確認点:

- `受注区分` が lexical token のまま残るか
- `CHECK.subject_resolution` が `explicit_subject` に留まるか
- `FILTER.predicate_resolution` が `logic_goal` に留まるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_27_admissible_but_deferred_alias.md`

### Alias Threshold Case B: Repeated Spec Use Promotion

用途:

- 同一 owner context で lexical token が反復使用されると `Admit Now` へ上がる基準を確認する
- threshold が単なる owner-confined 条件ではなく evidence accumulation を含むことを観察する

主な確認点:

- `受注区分 -> OrderCategory` が canonical property に上がるか
- `CHECK.subject_resolution` が `schema_property` まで上がるか
- `FILTER.predicate_resolution` が `schema_property` まで上がるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_28_repeated_spec_use_promotes_alias.md`

### Alias Threshold Case C: Cross-Case Relevance

用途:

- 同じ lexical token が複数 benchmark で再出すること自体を admission timing の根拠として扱えるかを確認する
- repeated-use がなくても benchmark 横断の relevance で schema admission を説明できるようにする

主な確認点:

- `受注区分 -> OrderCategory` が canonical property に上がるか
- `CHECK.subject_resolution` が `schema_property` まで上がるか
- `FILTER.predicate_resolution` が `schema_property` まで上がるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_29_cross_case_relevance_threshold.md`

### Alias Threshold Case D: Downstream Impact

用途:

- lexical retention が downstream conservatism を不必要に強める alias を admission 根拠にできるかを確認する
- runtime semantics ではなく code synthesis 影響を threshold の一部として扱えるようにする

主な確認点:

- `棚卸数量 -> InventoryCount` が canonical property に上がるか
- `CHECK.subject_resolution` が `schema_property` まで上がるか
- `FILTER.predicate_resolution` が `schema_property` まで上がるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_30_downstream_impact_threshold.md`

### Alias Threshold Case E: External Compatibility

用途:

- 外部帳票語や legacy integration 名のように、外部制約そのものを admission timing の根拠として扱えるかを確認する
- repeated-use や cross-case relevance が弱くても、互換要件で schema admission を説明できるようにする

主な確認点:

- `請求金額 -> InvoiceAmount` が canonical property に上がるか
- `CHECK.subject_resolution` が `schema_property` まで上がるか
- `FILTER.predicate_resolution` が `schema_property` まで上がるか

対応ケース:

- `research/ir_meaning_preservation/cases/case_31_external_compatibility_threshold.md`
