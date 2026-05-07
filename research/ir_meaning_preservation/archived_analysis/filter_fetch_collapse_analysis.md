# Filter Fetch Collapse Analysis

## 1. Purpose

この文書は、`case_16_filter_predicate_provenance` で `FILTER` が provenance metadata に到達する前に `FETCH` へ落ちる原因を、実装レベルで局所化するためのものである。

ここでの目的はまだ修正ではない。`FILTER` provenance の前提条件として、なぜ `LINQ/FILTER` が成立しないのかを deterministic に説明できる状態にすることを目的とする。

## 2. Observed Symptom

対象 step:

- `Points が input_1 より大きいユーザーを抽出する。`

`case_16` の observed IR では、この step は次の形になっている。

- `intent=FETCH`
- `role=FETCH`
- `spec_role=FETCH`
- `logic` には numeric goal が残る

つまり、predicate 情報は存在するが、node 全体は `FILTER` ではなく `FETCH` として固定されている。

## 3. Direct Reproduction

`IRGenerator._infer_intent_role_cardinality(...)` を単体で観測すると、上記 step に対して次を返す。

- `('FETCH', 'FETCH', None)`

同じ step を `_analyze_step_integrated(...)` に通しても、結果は `intent=FETCH`, `role=FETCH` のままである。

したがって問題は後段の `final_intent` 補正ではなく、より手前の初期 intent/role 判定で発生している。

## 4. Code-Level Cause

`src/ir_generator/ir_generator.py` の `_infer_intent_role_cardinality(...)` では、語彙集合が次のように定義されている。

- `fetch_nouns = {"取得", "検索", "読み込み", "読込", "読取", "抽出", "取得", "一覧"}`
- `transform_nouns = {"変換", "変形", "変化", "選択", "抽出"}`

ここで `抽出` が `fetch_nouns` と `transform_nouns` の両方に入っている。

さらに判定順は次の通りである。

1. `DISPLAY`
2. `PERSIST`
3. `FETCH`
4. `EXISTS`
5. `LINQ`

そのため、`抽出する` は `LINQ` に到達する前に `FETCH` として確定する。

## 5. Why Logic Goals Do Not Recover FILTER

`_analyze_step_integrated(...)` には次の補正がある。

- `elif intent == "GENERAL" and logic_goals: intent = "LINQ"; role = "FILTER"`

しかし今回の step は、すでに `_infer_intent_role_cardinality(...)` で `FETCH` になっている。

したがって、

- logic goal は抽出される
- だが `intent == "GENERAL"` 条件を満たさない
- 結果として `LINQ/FILTER` へ上がれない

つまり、logic goal は残っていても、それを `FILTER` 昇格に使う経路が `GENERAL` に限定されていることが第二の原因である。

## 6. Failure Shape

`FILTER` が `FETCH` に落ちる失敗は、次の 2 段で説明できる。

1. 語彙衝突
   - `抽出` が `FETCH` と `LINQ` の両方に属する
2. 補正経路不足
   - logic goal があっても、`GENERAL` でないと `FILTER` へ再昇格できない

## 7. Research Interpretation

これは単純なキーワード誤判定というより、「曖昧語彙を粗い intent に先着で割り当て、その後に richer semantic evidence を使って巻き戻す設計が無い」という構造問題である。

重要なのは、ここで安易に `抽出 -> LINQ` と決め打ちすることではない。`抽出` は実際に fetch 的にも使われ得るため、語彙置換で直すのは研究的にも実装的にも筋が悪い。

## 8. Stronger Working Hypothesis

`FILTER` を成立させるために必要なのは、語彙そのものの置換ではなく、次の優先順位変更である。

1. ambiguous lexeme がある
2. logic goal が比較 predicate を持つ
3. upstream collection context がある
4. この 3 条件が揃う場合に限り、`FETCH` より `LINQ/FILTER` を優先する

つまり修正対象は語彙辞書ではなく、「曖昧語彙 + semantic evidence + collection context」を束ねる昇格規則である。

## 9. Immediate Next Step

次にやるべきことは、`FILTER` 専用の昇格規則を設計文書として先に固定することである。

最低限、次の受け入れ条件が必要である。

1. `case_16` は `LINQ/FILTER` に上がる
2. 単なる `ユーザーを抽出する` のような fetch 的文面は `FETCH` に残せる
3. `DISPLAY` や `CHECK` を誤って `FILTER` へ上げない
