# Schema Alias Admission Threshold

## 1. Purpose

この文書は、`schema_alias_coverage_policy.md` で未確定として残っていた
`owner-confined だが benchmark need が弱い alias` をどう扱うかを定義するためのものである。

ここでの論点は、「deterministic に説明できる alias なら全部入れてよいのか」ではない。
むしろ、deterministic であっても benchmark need が弱いなら、schema maintenance cost の観点から保留すべきかを決めることが目的である。

## 2. Core Position

`owner-confined` と `canonical non-ambiguity` は必要条件だが、十分条件ではない。

alias admission は次の 2 段階で判断する。

1. `can_admit`
   - deterministic に許可可能か
2. `should_admit_now`
   - 現段階で schema に載せる価値があるか

この区別を入れないと、将来必要になるかもしれない alias を先回りで追加し、coverage policy が辞書肥大化へ流れる。

## 3. Decision States

alias 候補は次の 3 状態に分ける。

### State A: Admit Now

次をすべて満たすもの。

- owner-confined
- exact match で十分
- canonical non-ambiguity
- benchmark need が既にある

これは通常の Tier 1 / Tier 2 admission 対象である。

例:

- `受注額 -> OrderAmount`
- `伝票金額 -> OrderAmount`

### State B: Hold For Evidence

次を満たすもの。

- owner-confined
- exact match で十分
- canonical non-ambiguity
- ただし benchmark need がまだ弱い、または spec corpus 上で反復が確認できていない

この状態の alias は「禁止」ではないが、schema にまだ追加しない。
研究上は `admissible but deferred` として扱う。

### State C: Reject

次のいずれかに該当するもの。

- owner explanation ができない
- canonical ambiguity がある
- exact match だけでは足りない
- generic token で coverage 過剰を招く

これは従来どおり reject である。

## 4. Benchmark Need Threshold

`should_admit_now` を true にする最低条件を、次のいずれか 1 つ以上とする。

### Threshold A: Repeated Spec Use

同一 property owner 文脈で、その lexical token が 2 回以上現れる。

### Threshold B: Cross-Case Relevance

複数 benchmark ケースで、同じ lexical token が canonicalization failure の原因として再出する。

### Threshold C: Downstream Impact

その alias が無いことで、`CHECK`, `FILTER`, `CALCULATE` のいずれかで weak retention が残り、研究上の比較を不必要に曖昧にする。

### Threshold D: External Compatibility

legacy field 名や運用帳票語のように、実装ではなく外部制約により維持が必要だと説明できる。

## 5. Hold Rules

次の条件では alias を `Hold For Evidence` に置く。

1. deterministic ではあるが、まだ 1 ケースしか出ていない
2. owner-confined だが、downstream で未使用
3. canonical property へ上げても、研究上の差分が増えない
4. 将来使いそう、という推測しか根拠がない

要するに、「入れても安全」だけでは足りず、「今入れる必要がある」ことが必要になる。

## 6. Research Interpretation

この閾値を入れると、alias coverage の benchmark は次の 4 類型に分けられる。

1. admitted alias
   - canonicalization success
2. admissible but deferred alias
   - deterministic だが hold
3. missing-but-allowable alias
   - supply gap
4. disallowed alias
   - weak retention が正しい

特に `admissible but deferred` を独立させることで、
「policy 上は許可可能だが、まだ schema に入れない」という実務判断を研究上も追跡できるようになる。

## 7. Maintenance Cost View

`should_admit_now` を分ける理由は、schema maintenance cost にある。

alias を 1 つ追加すると、次のコストが増える。

- canonical property との対応維持
- benchmark expectation の更新
- owner explanation の継続確認
- generic token と見分ける review コスト

したがって、cost を払う理由が benchmark 上でまだ弱いなら、admission は保留する。

## 8. Immediate Next Step

次にやるべきことは、この `Hold For Evidence` 状態を benchmark に落とすことである。

少なくとも次の contrast が必要になる。

1. owner-confined で deterministic だが single-case only の alias
2. 同じ alias が repeated spec use を満たして `Admit Now` へ上がるケース

研究の流れとしては、ここからは alias を「許可できるか」だけでなく、
「いつ許可するか」を benchmark ベースで固定する段階に入る。
