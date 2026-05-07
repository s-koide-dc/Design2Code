# Schema Alias Supply Model

## 1. Purpose

この文書は、property-side provenance promotion に必要な alias を、どこに・どの粒度で・どの制約の下で供給するかを定義するためのものである。

ここでの目的は alias を増やすこと自体ではない。`CHECK` / `FILTER` の lexical property token を canonical property へ deterministic に写すための、最小で説明可能な供給面を固定することが目的である。

## 2. Core Position

この研究では、lexical property token の canonicalization を自由推測に委ねない。

alias は次の原則に従う。

1. `entity_schema` に明示されているものだけを使う
2. alias から canonical property への写像は exact match に限る
3. alias 供給は property resolution の前提データであり、runtime 推測規則ではない

つまり、`在庫 -> Stock` や `合計金額 -> Total` は、schema がそう宣言しているから使えるのであって、文字列が似ているから使えるわけではない。

## 3. Supply Location

当面の alias 供給面は `entity_schema` の property 定義に限定する。

canonical shape:

```json
{
  "entities": [
    {
      "name": "Product",
      "properties": [
        { "name": "Stock", "aliases": ["在庫"] },
        { "name": "Name", "aliases": ["名前"] }
      ]
    }
  ]
}
```

この形を標準とする。

## 4. Why Keep Alias Inside Schema

alias を別辞書へ逃がさず `entity_schema` に置く理由は次の 3 点である。

1. owner entity と alias を同時に固定できる  
   `在庫` が `Product.Stock` の alias なのか、別 entity の property なのかを離さずに持てる。

2. provenance promotion と同じ因果に乗せられる  
   `canonical property -> owner uniqueness -> schema_property/history_*` の流れを 1 つの model 内で説明できる。

3. cheap な語彙辞書化を防げる  
   schema と切り離すと、property alias がただの単語対応表になりやすい。

## 5. Allowed Alias Semantics

alias は、同じ property の domain-safe な別表記だけを表す。

許可:

- 日本語 UI/仕様語とコード property の対応
  - `在庫` -> `Stock`
  - `合計金額` -> `Total`
- 略称と正式名
  - `ID` -> `Id`
  - `作成日時` -> `CreatedAt`
- 既存業務用語と property 名の対応

禁止:

- 意味が近いだけの語
- property owner を跨ぐ汎用語
- 処理意図まで含む語
  - 例: `集計結果`, `表示内容`

## 6. Determinism Rules

alias 供給は次の制約を満たさなければならない。

### Rule A: Exact Match Only

canonicalization は alias の exact match に限定する。

許可:

- `在庫` -> `Stock`
- `合計金額` -> `Total`

禁止:

- 部分一致
- prefix/suffix 一致
- ベクトル類似
- スコアリング

### Rule B: One Canonical Property Per Alias

1 つの lexical alias は、schema 全体で 1 つの canonical property にしか写ってはならない。

もし同じ alias が複数 canonical property に割り当たるなら、その alias は supply model として不適切である。

### Rule C: Owner Ambiguity Is Allowed, Canonical Ambiguity Is Not

`Total` のように canonical property 自体は 1 つでも、owner entity が複数あることは許可する。

これが `history_based` 観測の前提になる。

一方で、

- `合計` -> `Total` と `AggregateValue`

のように canonical property 自体が複数候補になる alias は許可しない。

## 7. Boundary With Exact Scope

alias supply model は canonical property までしか担当しない。

その後の

- owner uniqueness
- current target / collection scope
- `schema_property` か `history_*` か

の判定は property-side provenance promotion 側の責務である。

つまり責務分離は次の通り。

1. `schema_alias_supply_model`
   - lexical token -> canonical property
2. `property_side_provenance_promotion_rule`
   - canonical property + scope -> provenance strength

## 8. Minimal Maintenance Rule

alias を追加するときは、少なくとも次の 3 点を同時に満たす必要がある。

1. 実際の design text / benchmark で必要になっている
2. owner entity と一緒に説明できる
3. exact match で十分に決まる

これを満たさない alias は追加しない。

## 9. Benchmark Implication

この supply model があると、次の比較が意味を持つ。

- alias あり
  - `在庫` -> `Stock`
  - `合計金額` -> `Total`
- alias なし
  - lexical token は保持されるが canonicalization されない

したがって、今後の benchmark では「昇格失敗」を provenance promotion の失敗と supply model 不足に分けて読める。

## 10. What This Model Explicitly Rejects

この研究では、次の方向には進まない。

- fuzzy alias generation
- embedding ベース property 推定
- 正規表現ベースの表層吸収
- 単語頻度やスコアリングによる property 決め打ち

これらは一見 coverage を上げるが、meaning preservation の deterministic な説明力を壊す。

## 11. Immediate Next Step

次にやるべきことは、alias 供給モデルを benchmark 上で評価するために、少なくとも次の 2 系統を追加することである。

1. alias ありで canonicalization が成立するケース
2. alias なしで weak provenance に留まる contrast case

研究の流れとしては、これで `supply failure` と `promotion failure` を切り分けられるようになる。
