# CALCULATE Metadata Conservatism Summary

## 1. Purpose

この文書は、`CALCULATE` を題材として、IR metadata が downstream code synthesis の保守性を実際に制御できたかを中間整理するためのものである。

ここでいう保守性とは、「意味が十分に確定したときだけ具体化し、不確定なときは過剰解釈せず停止寄りに振る舞うこと」を指す。

## 2. Research Question

この段階の主問いは次の通りである。

1. `CALCULATE` を `GENERAL/ACTION` から安定して切り出せるか
2. `target_hint` / `property` / `entity_schema` から `target_entity` を deterministic に補正できるか
3. その解決由来を downstream へ渡し、具体化の強さを制御できるか

## 3. What Was Added

### 3.1 Upstream

- `target_hint/property + calculation intent` による `CALCULATE` 昇格規則
- schema-backed property owner 解決
- `semantic_roles.entity_resolution` の導入

### 3.2 Research Benchmarks

- `case_12_calculate_with_target_hint`
- `case_13_calculate_without_target_hint`
- `case_14_calculate_ambiguous_property_owner`

### 3.3 Downstream

- `entity_resolution` に応じた `CALC` synthesis policy
- `ambiguous` での cross-entity fallback 禁止
- 安全に具体化できない場合の TODO 停止

## 4. Current Resolution Model

現時点の `entity_resolution` は次の 4 類型である。

- `unique_owner`
- `explicit_entity`
- `history_fallback`
- `ambiguous`

この分類は、entity 解決結果そのものではなく、「なぜその entity を採ったか」を保持する。

## 5. Observed Outcome

### Case 12

- `CALC/CALCULATE` に昇格
- `target_hint/property` を保持
- unique owner があるときは `target_entity` を owner entity に補正できる

### Case 13

- explicit metadata がないため `GENERAL/ACTION` に留まる
- 単語だけで `CALCULATE` に上げない規則が守られている

### Case 14

- `CALC/CALCULATE` 自体は保持
- property owner が曖昧なため `target_entity` は弱い entity のまま維持
- `entity_resolution=ambiguous` を観測できる
- downstream は arbitrary な `.Total` assignment を作らず TODO 停止へ送れる

### Case 15

- 直前文脈の `Order` は保持される
- upstream 観測でも `entity_resolution=history_fallback` を独立に保持できる
- したがって、4 類型は observation layer と downstream policy の両方で整合する

## 6. Main Result

この段階の主結果は次の 2 点に要約できる。

1. IR metadata は、単に意味保存の記録ではなく、downstream code synthesis の具体化レベルを制御する入力として機能した
2. `CALCULATE` に関しては、「意味が強いほど具体化し、意味が弱いほど保守的に振る舞う」という単調な policy を作れた

これは、`spec_role` や `entity_resolution` のような metadata が runtime 側の安全性制御にも使えることを示している。

## 7. Why This Matters

この結果には研究上 3 つの意味がある。

1. `IR meaning preservation` が単なる比較研究ではなく、生成器設計指針へ接続できた
2. over-interpretation を避けるための保守性を、曖昧性そのものを保持することで実装できた
3. metadata layer を増やすことが、heuristic 補強ではなく deterministic behavior control として機能することを示せた

## 8. Current Boundary

まだできていないことも明確である。

- `entity_resolution` は現状 `CALCULATE` にしか導入していない
- `CHECK`, `FILTER`, `TRANSFORM` へ同様の conservatism policy を広げていない

## 9. Next Step

次に進めるなら、候補は 2 つである。

1. `CHECK` や `FILTER` にも「解決由来に応じて downstream を保守化する」設計を拡張する
2. `entity_resolution` のような由来メタデータを他 role に広げても、過剰設計にならない境界を定義する

この段階では、まず 1 のほうが研究として筋が良い。
