# CALCULATE Target Entity Ambiguity Rule

## 1. Purpose

この文書は、`CALCULATE` ノードで `semantic_roles.property` または `target_hint` から `target_entity` を補正する際の曖昧性処理を定義するためのものである。

目的は、`Item` のような弱い entity を deterministic に改善しつつ、複数候補がある場合に安易にどれか 1 つへ寄せないことである。

## 2. Problem Statement

property owner を使った `target_entity` 補正は、次の条件では有効である。

- `CALCULATE` に昇格済みである
- `semantic_roles.property` または `target_hint` がある
- `entity_schema` に property 所属が定義されている
- owner entity が一意に決まる

しかし、複数 entity が同じ property 名を持つ場合、単純な property 名一致だけでは owner を決められない。

例:

- `Order.Total`
- `Invoice.Total`

このとき `Totalを計算する` だけから `Order` または `Invoice` を選ぶのは、研究上も実装上も根拠不足である。

## 3. Design Goal

目標は次の 3 点である。

1. 一意 owner がある場合だけ `target_entity` を持ち上げる
2. owner が曖昧な場合は誤補正しない
3. 将来の disambiguation を追加できるように、曖昧だった事実自体は観測可能にする

## 4. Core Rule

`CALCULATE` ノードの `target_entity` 補正は、次の順で判定する。

### Rule A: Unique Property Owner

`entity_schema` 上で property owner が一意に決まる場合だけ、その entity へ補正してよい。

結果:

- `node.target_entity = owner_entity`
- `semantic_roles.target_entity = owner_entity`

### Rule B: Non-Weak Explicit Role Entity

property owner が一意でなくても、`semantic_roles.target_entity` がすでに弱くない entity で埋まっている場合は、それを維持してよい。

これは property 名からの推測ではなく、前段で既に得られている explicit entity を保持するだけである。

### Rule C: Strong History Fallback

上記 2 つが使えない場合、履歴上の直近 non-weak entity を使ってよい。

ただしこれは「owner を確定した」のではなく、「弱い `Item` を維持するより文脈上妥当な entity を残す」ための fallback である。

### Rule D: Ambiguity Preserve

property owner が複数候補に分かれ、explicit entity も履歴上の強い entity もない場合は、`target_entity` を補正してはならない。

この場合は弱い entity を維持する。

## 5. Why Ambiguity Must Be Preserved

曖昧性があるのに片方へ寄せると、次の問題が起こる。

- research 上は meaning preservation ではなく over-interpretation になる
- downstream code synthesis で誤った POCO や property chain を選ぶ
- benchmark 上は成功に見えても、別 schema で再現しない

したがって、曖昧な場合に補正しないこと自体が deterministic design の一部である。

## 6. Observable IR Behavior

曖昧ケースでは、少なくとも次の読み方ができる必要がある。

1. `spec_role=CALCULATE` は保持されている
2. `semantic_roles.property` / `target_hint` は保持されている
3. `target_entity` は弱い entity のまま残る

観測可能性を上げるため、次の観測用フィールドを追加してよい。

- `semantic_roles.entity_resolution`

初回の候補値は次の 4 つで十分である。

- `unique_owner`
- `explicit_entity`
- `history_fallback`
- `ambiguous`

必要なら将来的に `entity_resolution_candidates` を追加してもよいが、初回実装では必須としない。

## 7. Benchmark Requirement

この規則を検証するには、少なくとも次の 2 種類の補助ケースが必要である。

### Case A: Unique Owner

- `Product.DiscountedPrice` だけが schema 上に存在する
- `DiscountedPriceを計算する`
- 期待: `target_entity=Product`

### Case B: Ambiguous Owner

- `Order.Total`
- `Invoice.Total`
- `Totalを計算する`
- 期待: `spec_role=CALCULATE` は維持されるが、`target_entity` は特定 entity に補正されない

## 8. Exit Condition

この規則が成立したと判断する条件は次の通りである。

1. unique owner ケースで `target_entity` が owner entity に補正される
2. ambiguous owner ケースで誤って特定 entity に寄らない
3. unique/ambiguous の観測結果が `entity_resolution` に残る
4. `FILTER`, `CHECK`, `DISPLAY` には影響しない

## 9. Next Step

次にやるべきことは、ambiguous owner の補助ベンチマークを追加し、現行実装が `target_entity` を不当に持ち上げていないかを観測することである。
