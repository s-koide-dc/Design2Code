# Role Layer Definition

## 1. Purpose

この文書は、`IR meaning preservation` 研究における `role` の責務を分離し、`spec_role` と `runtime_role` を別概念として定義するためのものである。

`Intent Drift` の観測結果から、現行実装では仕様意味としての役割と、コード生成・実行都合としての役割が同じ `role` フィールドに混在していることがわかった。ここではその混線を解き、比較・改善の基準面を作る。

## 2. Core Principle

今後の研究では、`role` を単一概念として扱わない。

代わりに、少なくとも以下の二層を区別する。

1. `spec_role`
2. `runtime_role`

この 2 つは同一であってもよいが、同一であることを前提にはしない。

## 3. Definition of `spec_role`

`spec_role` は、設計仕様の意味構造の中で、そのステップがどの役割を持つかを表す。

これは研究上の意味保存評価の対象であり、コード生成の便宜よりも、自然言語仕様の論理的役割を優先する。

### 3.1 Characteristics

- 自然言語仕様の意味に忠実である
- コード生成言語やライブラリ都合に引きずられない
- 比較可能性と説明可能性を優先する
- 役割はできるだけ意味的に直交させる

### 3.2 Candidate `spec_role` Set

初期定義では、以下を `spec_role` 候補とする。

- `FETCH`
  - 外部または明示 source からデータを取得する
- `DESERIALIZE`
  - 文字列やバイト列から構造化データへ変換する
- `SERIALIZE`
  - 構造化データから文字列やバイト列へ変換する
- `TRANSFORM`
  - 値や構造を変換する
- `FILTER`
  - 条件に基づいて候補集合を絞る
- `AGGREGATE`
  - 複数要素から集約値を作る
- `CALCULATE`
  - 数値や状態を計算・更新する
- `CHECK`
  - 条件成立や存在有無を判定する
- `ITERATE`
  - 集合要素に対する反復処理の構造を持つ
- `DISPLAY`
  - 人間向けに値を提示する
- `PERSIST`
  - 外部永続先へ保存する
- `RETURN`
  - 呼び出し元へ返す
- `WRAP`
  - 他処理を構造的に包む

## 4. Definition of `runtime_role`

`runtime_role` は、生成・合成・実行の都合で、そのノードをどの操作クラスとして扱うかを表す。

これは研究上の意味保存そのものではなく、後段処理に必要な実務的分類である。

### 4.1 Characteristics

- 生成器や emitter の都合を反映してよい
- 同じ `spec_role` が複数の `runtime_role` に落ちることを許容する
- 操作クラスとしての粗さを持ってよい
- 仕様意味と完全一致しなくてもよいが、変換理由は説明可能であるべき

### 4.2 Candidate `runtime_role` Set

初期定義では、以下を `runtime_role` 候補とする。

- `READ`
- `WRITE`
- `ACTION`
- `DISPLAY`
- `PERSIST`
- `CALC`
- `FETCH`
- `TRANSFORM`
- `CHECK`

この集合自体は将来見直してよい。ただし、意味保存研究では `runtime_role` の変更より、`spec_role` の保持を優先する。

## 5. Mapping Principle

`intent` と `role` の関係は、今後は次の順に考える。

1. ステップ意味から `spec_role` を定める
2. 必要に応じて `runtime_role` へ写像する
3. 後段補正で変更してよいのは原則 `runtime_role` 側だけとする

これにより、仕様意味を後段の都合で直接破壊しない。

## 6. Initial Mapping Table

| Intent / Step Meaning | Preferred `spec_role` | Possible `runtime_role` | Notes |
|---|---|---|---|
| File/DB/HTTP fetch | `FETCH` | `READ`, `FETCH` | source 種別は別メタで保持する |
| JSON deserialize | `DESERIALIZE` | `ACTION`, `TRANSFORM` | 現状は `ACTION` に落ちやすい |
| Generic transform | `TRANSFORM` | `ACTION`, `TRANSFORM` | 仕様意味では `TRANSFORM` を保持したい |
| LINQ filter | `FILTER` | `ACTION`, `TRANSFORM` | `FILTER` を `TRANSFORM` に畳まない |
| Aggregate | `AGGREGATE` | `CALC`, `ACTION` | 集約と単純計算は分ける |
| Numeric/state update | `CALCULATE` | `CALC`, `ACTION` | 状態更新もここに含む |
| Exists/condition check | `CHECK` | `CHECK`, `ACTION` | 条件ノードに特に重要 |
| Loop body structure | `ITERATE` | `ACTION` | 構造ノード側で補う |
| Human-facing output | `DISPLAY` | `DISPLAY` | できれば一致を保つ |
| Persist/save | `PERSIST` | `WRITE`, `PERSIST` | 保存先は別メタで管理する |
| Return literal/value | `RETURN` | `ACTION` | runtime では粗くてもよい |
| Retry/wrapper | `WRAP` | `ACTION` | ラッパーは構造優先 |

## 7. Allowed and Disallowed Transformations

### 7.1 Allowed

- `spec_role` を保持したまま `runtime_role` を具体化すること
  - 例: `FETCH -> READ`
  - 例: `PERSIST -> WRITE`

- `spec_role` を保持したまま cardinality や source 情報を補うこと

- 生成都合で `runtime_role` を再解釈すること
  - ただし、その理由が局所的に説明可能である場合に限る

### 7.2 Disallowed

- 後段で `spec_role` を黙って弱化すること
  - 例: `FILTER -> ACTION`
  - 例: `CHECK -> ACTION`
  - 例: `TRANSFORM -> ACTION`

- source 情報の欠落を role の一般化で隠すこと

- cardinality 補正の副作用で、仕様意味の役割まで変更してしまうこと

## 8. Reinterpretation of Current Problems

現行の `Intent Drift` は、単なる分類ミスではなく、以下の問題として読み替えられる。

### 8.1 Missing `spec_role`

現行 IR は、実質的に `runtime_role` 相当しか持っていないため、仕様意味 role が保存されにくい。

### 8.2 Implicit Collapsing

`TRANSFORM`, `FILTER`, `CHECK`, `DESERIALIZE` などが、明示的な役割として保持されず、`ACTION` に暗黙圧縮される。

### 8.3 Inconsistent Runtime Repair

後段で `FETCH`, `DISPLAY`, `PERSIST` だけが部分修復されるため、role 体系が不均一になる。

## 9. Working Recommendation for Research

研究段階では、比較対象の IR を読む際に、以下のように扱う。

- 期待 IR では `spec_role` を主に書く
- 実 IR の既存 `role` は、当面 `runtime_role` 相当として読む
- 差分評価では、`spec_role` が保持されたかを優先判定する
- 実装改善を始めるときは、`spec_role` を新設するか、`semantic_map` 内へ退避する案を比較する

## 10. Immediate Next Step

この定義の次に行うべきことは、優先 5 ケースについて期待 IR の各ノードに `spec_role` を明示し、実 IR との比較時に「何が保持され、何が runtime 側へ潰れたか」を見える化することである。

## 11. Current Adoption

優先 5 ケースの期待 IR では、`semantic_map.semantic_roles.spec_role` を用いて `spec_role` を明示する方針を採用した。

この表現は実装スキーマの必須項目ではなく、研究上の比較補助メタデータとして扱う。
