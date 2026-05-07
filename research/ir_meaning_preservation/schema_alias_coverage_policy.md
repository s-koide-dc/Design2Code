# Schema Alias Coverage Policy

## 1. Purpose

この文書は、`entity_schema` に property alias をどこまで追加してよいか、その coverage 境界を定義するためのものである。

`schema_alias_supply_model.md` で供給面の形式は固定できた。次に必要なのは、`どの alias を追加対象と見なし、どの alias を拒否するか` を benchmark 可能な基準にすることである。

## 2. Core Position

alias coverage は、coverage 最大化ではなく deterministic 説明力の維持を優先する。

したがって、alias 追加は次の順に審査する。

1. domain-safe か
2. owner-confined か
3. exact-match で十分か
4. benchmark 上の必要性があるか

この 4 条件のどれかを満たさない alias は追加しない。

## 3. Coverage Tiers

### Tier 1: Strongly Allowed

次の alias は積極的に許可してよい。

- UI/仕様書で安定して使われる業務語
  - `在庫` -> `Stock`
  - `合計金額` -> `Total`
- property 名の日本語正式表記
  - `作成日時` -> `CreatedAt`
- property owner を跨がない略称
  - `ID` -> `Id`

条件:

- 1 property にだけ対応する
- 同じ owner context で反復使用される
- exact match で十分

### Tier 2: Conditionally Allowed

次の alias は条件付きで許可する。

- domain-specific abbreviation
- legacy field 名との橋渡し
- 複合語の一部だが、実運用上は単独で property を指すもの

条件:

- benchmark で必要性が確認されている
- owner entity を添えれば曖昧でない
- alias 単独ではなく property definition と一緒に記録できる

### Tier 3: Disallowed

次の alias は coverage 目的でも追加しない。

- 意味が広すぎる語
  - `情報`, `内容`, `結果`
- owner entity を跨いで使われる一般語
  - `名前`, `番号`, `日付` を無差別に共通 alias とする
- 処理意図や UI 文脈を含む語
  - `表示内容`, `集計結果`, `検索条件`
- exact match では足りず、部分一致や推測が必要な語

## 4. Admission Rules

alias を新規追加する条件は次の通り。

### Rule A: Benchmark-Driven Need

少なくとも 1 つの benchmark または実仕様例で、その alias が無いと canonicalization できないことが確認されている。

### Rule B: Owner Explanation

その alias が、どの owner entity のどの property に属するかを 1 文で説明できる。

悪い例:

- `番号` -> `Number`

これだけでは `Order.Number`, `Invoice.Number`, `User.Number` のどれか説明できない。

### Rule C: Exact-Match Sufficiency

その alias は exact match だけで canonical property に写る必要がある。

悪い例:

- `金額` を `TotalAmount`, `LineAmount`, `TaxAmount` の共通 alias にする

### Rule D: Canonical Non-Ambiguity

1 つの alias が複数 canonical property を指すなら、その alias は coverage 追加対象にしない。

owner ambiguity は許可するが、canonical ambiguity は許可しない。

## 5. Rejection Rules

次の alias は、必要に見えても追加してはならない。

1. alias を入れると canonical property ambiguity が生まれる
2. alias の意味が owner entity によって変わる
3. exact match 以外の補助規則が必要になる
4. benchmark ではなく「念のため」で入れようとしている

## 6. Example Decisions

### Accept

- `在庫` -> `Stock`
  - owner-confined
  - exact match
  - benchmark で必要

- `合計金額` -> `Total`
  - canonical property は一意
  - owner ambiguity は `history_based` 観測に使える

### Reject

- `金額`
  - `Total`, `LineAmount`, `Price` など複数 canonical property に滑る

- `名前`
  - entity を跨いで普遍的すぎる
  - canonicalization より owner ambiguity が先に来る

- `結果`
  - property ではなく UI 文脈語

## 7. Benchmark Consequence

この policy があると、alias coverage の benchmark は少なくとも次の 3 類型に分けられる。

1. allowed alias
   - canonicalization success
2. missing-but-allowable alias
   - supply gap
3. disallowed alias
   - weak retention のまま残すのが正しい

この 3 類型を分けることで、coverage 不足と coverage 過剰を同時に監視できる。

## 8. Immediate Next Step

次にやるべきことは、この policy を benchmark に落とすために、少なくとも次の contrast を追加することである。

1. allowed alias case
2. disallowed generic alias case

研究の流れとしては、ここまで来たら alias supply は「増やす」より「どこで止めるか」を観測できるようにするのが重要である。
