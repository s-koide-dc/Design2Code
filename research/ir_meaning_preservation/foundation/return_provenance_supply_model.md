# Return Provenance Supply Model

## 1. Purpose

この文書は、`RETURN` provenance をどこで・どの条件で supply してよいかを定義するためのものである。

目的は `RETURN` metadata を増やすこと自体ではない。  
`return_value_resolution` を deterministic に与えてよい境界と、weak retention に留めるべき境界を固定することが目的である。

## 2. Core Position

`RETURN` の provenance supply は、次の 3 系統に限定する。

1. explicit literal / explicit source
2. quoted / tokenized literal
3. structural upstream link

それ以外は supply しない。

つまり、

- `true を返す`
- `null を返す`
- `「done」を返す`
- `取得したユーザーを返す`

は deterministic に supply してよいが、

- `結果を返す`
- `値を返す`
- `必要なら返す`

のように source が構造上も明示されないものは weak retention に留める。

## 3. Supply Sources

### 3.1 Explicit Source

許可:

- `semantic_roles.source_var`
- `semantic_roles.return_value`

意味:

- caller または前段整形で既に return target が固定されている

### 3.2 Literal Source

許可:

- quoted literal
- token 上の `true`
- token 上の `false`
- token 上の `null`
- text 中の numeric literal

意味:

- return target 自体が step 文面に explicit に現れている

### 3.3 Structural Upstream Source

許可:

- `input_link` が存在する non-literal `RETURN`

意味:

- return target は自由推測ではなく、IR 上の upstream dependency により供給されている

ただし structural `input_link` が `CHECK` のような構造親を指す場合は、その node 自体ではなく upstream semantic source に引き直す。

## 4. Supply Rules

1. literal / explicit source がある場合はそれを優先する
2. literal でなく `input_link` がある場合は `input_link_var` を付ける
3. `input_link` も literal も無い場合は provenance を supply しない

この順は固定である。

## 5. What This Model Rejects

この supply model は次を明示的に拒否する。

- lexical hint だけで return source を推定する
- `結果`, `値`, `内容` などの汎用語から source var を決める
- history 全体から latest var を provenance として昇格させる
- score / regex / fuzzy match による source 決定

latest-var fallback は downstream の保守的 fallback であって、supply model ではない。

## 6. Contrast Reading

### Supply Success

- `取得したユーザーを返す`
- `input_link=step_1`
- `return_source_node_id=step_1`
- `return_value_resolution=input_link_var`

### Weak Retention

- `結果を返す`
- `input_link=null`
- `return_value_resolution` なし

この contrast により、`RETURN` の弱さを runtime fallback の問題と supply 不足の問題に分けて読める。

## 7. Immediate Benchmark Implication

このモデルがあると、次の 2 系統が benchmark で意味を持つ。

1. upstream link があり `input_link_var` まで上がるケース
2. source が供給されず weak retention に留まるケース

研究上は、これで `RETURN` provenance も alias supply や property provenance と同様に `supply success / supply failure` の軸で説明できる。
