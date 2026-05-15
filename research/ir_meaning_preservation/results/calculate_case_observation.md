# CALCULATE Case Observation

## Scope

この文書は、`CALCULATE` 補助ケースについて、`target_hint` の有無と property owner の曖昧性が upstream detection / entity 補正にどう影響するかを観測するためのものである。

対象:

- `case_12_calculate_with_target_hint`
- `case_13_calculate_without_target_hint`
- `case_14_calculate_ambiguous_property_owner`
- `case_15_calculate_history_fallback_gap`
- `case_35_calculate_history_target_with_explicit_entity`
- `case_36_calculate_default_target_retention`

## Summary

### Case 12: Calculate With Target Hint

- Observed IR: `intent=CALC`, `role=CALC`, `spec_role=CALCULATE`
- Preserved metadata: `semantic_roles.target_hint=DiscountedPrice`, `property=DiscountedPrice`

Reading:

- explicit target hint と calculation intent の組み合わせで `CALCULATE` へ昇格できた
- `logic_goals.calculation` がなくても、metadata-aware promotion が機能することを確認した
- `target_hint` は metadata として残るだけでなく、intent/role/spec_role に反映された

### Case 13: Calculate Without Target Hint

- Observed IR: `intent=GENERAL`, `role=ACTION`, `spec_role=ACTION`
- Preserved metadata: 追加計算メタなし

Reading:

- implicit phrase だけでは `CALCULATE` に上がらない
- Case 12 との差は、`target_hint/property` が昇格条件として働くかどうかにある

### Case 14: Calculate Ambiguous Property Owner

- Observed IR: `intent=CALC`, `role=CALC`, `spec_role=CALCULATE`
- Preserved metadata: `semantic_roles.target_hint=Total`, `property=Total`
- Resolution metadata: `semantic_roles.entity_resolution=ambiguous`
- Target provenance: `semantic_roles.calculate_target_resolution=explicit_target`
- Entity result: `target_entity=Item` のまま維持

Reading:

- `CALCULATE` 昇格自体は成立する
- ただし property owner が `Order.Total` / `Invoice.Total` に分かれるため、`target_entity` は特定 entity に補正されない
- したがって、現行実装は ambiguity preserve を満たしている

### Case 15: Calculate History Fallback Gap

- Observed IR: `intent=CALC`, `role=CALC`, `spec_role=CALCULATE`
- Preserved metadata: `semantic_roles.target_hint=Total`, `property=Total`
- Resolution metadata: `semantic_roles.entity_resolution=history_fallback`
- Target provenance: `semantic_roles.calculate_target_resolution=explicit_target`
- Entity result: `target_entity=Order`

Reading:

- 直前文脈の `Order` は保持されている
- `history_fallback` が upstream 観測でも独立に残るようになった
- 一般の `target_entity` 推定と `CALCULATE` 専用 resolution の責務を分離したことで、history 由来の補正を `explicit_entity` に吸収しなくなった
- ただし `semantic_roles.target_entity` は no-history base を保持するため、後続 `DISPLAY` の metadata では `Item` に留まる

### Case 35: Calculate History Target With Explicit Entity

- Observed IR: `intent=CALC`, `role=CALC`, `spec_role=CALCULATE`
- Preserved metadata: `semantic_roles.target_entity=Order`, `target_hint=Total`, `property=Total`
- Resolution metadata:
  - `semantic_roles.entity_resolution=explicit_entity`
  - `semantic_roles.calculate_target_resolution=history_target`
  - `semantic_roles.calculate_source_resolution=input_link_var`

Reading:

- property owner 自体は `Order.Total` / `Invoice.Total` に分かれるため schema-backed target にはならない
- ただし current exact scope は explicit `target_entity=Order` で与えられているため、property-side provenance は `history_target` まで上げられる
- これは natural-language only の case 15 と異なり、entity 側と target-side provenance 側を別々に説明できるケースである

### Case 36: Calculate Default Target Retention

- Observed IR: `intent=CALC`, `spec_role=CALCULATE`
- Preserved metadata:
  - `semantic_roles.target_entity=Item`
  - `semantic_roles.calculate_target_resolution=default_target`
  - `semantic_roles.calculate_source_resolution=default_scope_var`

Reading:

- `CALCULATE` role 自体は explicit intent から成立している
- ただし target/property metadata が無いため、target-side provenance は `default_target` に留まる
- source 側も upstream source を持たないため `default_scope_var` に留まり、target/source の両方が weak retention である最小ケースになっている

## Initial Conclusion

初回観測から言えるのは次の通りである。

1. `target_hint` は保持できる
2. `target_hint/property + calculation intent` の組み合わせで `CALCULATE` に昇格できる
3. explicit metadata がない場合は `GENERAL/ACTION` に留まる

したがって、昇格規則の最小形は成立したとみなせる。

一方で初回観測では、

- `target_entity` が弱い `Item` に留まる
- `CALCULATE` と `TRANSFORM` / `FILTER` / `DISPLAY` の誤衝突が本当に出ないか追加確認が必要

である。

## Follow-up Result

追加実装と回帰確認の結果、次の点が確認できた。

1. `entity_schema` に property 所属がある場合、`semantic_roles.property` または `target_hint` から owner entity を一意に逆引きできる
2. その場合、`CALCULATE` ノードの `target_entity` と `semantic_roles.target_entity` は弱い `Item` ではなく owner entity に補正される
3. 同じ履歴を後続 `DISPLAY` が引き継ぐため、計算結果の表示ノードも owner entity に寄る
4. `DISPLAY` ノードは `target_hint/property` を持っていても `CALC` に誤昇格しない
5. property owner が曖昧な場合は、`CALCULATE` を維持しつつ `target_entity` を weak entity のまま残せる
6. unique/ambiguous の違いは `semantic_roles.entity_resolution` で観測できる
7. downstream code synthesis では、`entity_resolution=ambiguous` の `CALCULATE` を無理に property assignment へ落とさず、保守的な TODO 停止へ送れる
8. `history_fallback` は upstream 観測でも独立に分離できるようになった

Reading:

- `target_entity` 改善は語彙依存ではなく、`entity_schema` にある explicit property ownership を使った補正として成立した
- したがって、この改善は research 上も deterministic metadata bridge として説明できる
- `CALCULATE` の昇格と `target_entity` 補正は別段階になっており、schema がないケースや owner ambiguity があるケースでは `Item` に留まる
- `history_fallback` は downstream policy だけでなく、upstream 観測上の説明変数としても独立に扱えるようになった

## Source Provenance Follow-up

`CALCULATE` の source 側でも、success と weak retention の境界を明示した。

- explicit `source_var` がある場合は `calculate_source_resolution=source_var`
- structural upstream source がある場合は `calculate_source_resolution=input_link_var`
- どちらも無い場合は silent fallback にせず `calculate_source_resolution=default_scope_var`

Reading:

- `default_scope_var` は source 推定の失敗ではなく、weak provenance を観測可能に残した状態である
- downstream はこの状態で exact upstream source を捏造せず、`active_scope_item` に留まる
- したがって `CALCULATE` の source continuity も `RETURN` / `TRANSFORM` と同じく `supply success` と `weak retention` に分けて説明できる

## Target Provenance Follow-up

target 側でも、entity 補正とは別に property/target の強さを切り出した。

- canonical property owner が一意な場合は `calculate_target_resolution=schema_property`
- canonical property は複数 owner にまたがり current target entity が exact scope で決まる場合は `calculate_target_resolution=history_target`
- explicit `target_hint/property` はあるが canonical property へ上がらない場合は `calculate_target_resolution=explicit_target`
- target metadata 自体が無い manual / weak case は `calculate_target_resolution=default_target`

Reading:

- `entity_resolution` は entity 側の強さ、`calculate_target_resolution` は property/target 側の強さであり、役割を分けて読む
- `explicit_target` は weak retention であり、schema-backed property-aware concretization を意味しない

## Next Target

次にやるべきことは、分離済みの `entity_resolution` モデルを `FILTER` / `CHECK` のような他 role へ広げるかどうかを判断することと、`FILTER` / `CHECK` / `DISPLAY` の既存 benchmark へ広い回帰確認を反映することである。
