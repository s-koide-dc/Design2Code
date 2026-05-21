# Structural Dependency Rule

## 1. Purpose

この文書は、`IR meaning preservation` 研究において、構造ノード配下の `input_link` をどの原理で決めるべきかを定義するためのものである。

これまでの観測では、`CONDITION`, `LOOP`, `WRAPPER` で共通して、「直前ノードチェーン」と「構造親への従属」が混線すると `Dependency Loss` が起きることが分かった。

したがって今後は、構造ノード配下の依存規則を個別バグ修正ではなく、共通ルールとして扱う。

## 2. Core Claim

構造ノードの内側では、すべてのノードが一律に直前ノードへ接続されるべきではない。

少なくとも次の 2 種類を分ける必要がある。

1. `structural_parent_dependency`
2. `sequential_sibling_dependency`

この区別がないと、

- else 側が then 側へ誤接続される
- loop 本体の最初のノードが外側直前ノードに流れる
- wrapper 内の最初のノードが wrapper 自体に従属していることが見えなくなる

という問題が起きる。

## 3. Dependency Classes

### 3.1 Structural Parent Dependency

ノードが、直前 sibling ではなく、その構造親の支配下にあること自体を主要依存として持つ型。

典型例:

- `CONDITION.children` の最初のノード
- `CONDITION.else_children` の最初のノード
- `LOOP.children` の最初のノード
- `WRAPPER.children` の最初のノード

意味:

- 「この処理は親構造が成立した文脈で実行される」

### 3.2 Sequential Sibling Dependency

同一構造ブロック内で、前段 sibling の出力を引き継ぐ型。

典型例:

- `FETCH` の直後の `DISPLAY`
- `TRANSFORM` の直後の `PERSIST`
- loop body 内での逐次処理

意味:

- 「この処理は同じブロック内の前段結果に依存する」

## 4. Rule Statement

研究上の基本規則は次の通りとする。

### Rule 1

構造ブロック配下の最初の実ノードは、既定では `structural_parent_dependency` を持つ。

すなわち、`input_link` の既定先は直前グローバルノードではなく、構造親の branch base である。

### Rule 2

同じブロック内で 2 個目以降の実ノードは、既定では `sequential_sibling_dependency` を持つ。

すなわち、`input_link` の既定先は同一ブロック内の直前 sibling である。

### Rule 3

`structural_parent_dependency` を使うべき場所で `sequential_sibling_dependency` を適用してはならない。

代表例:

- `else_children` 最初のノードを then 側末尾へつなぐこと

### Rule 4

`sequential_sibling_dependency` を使うべき場所で、常に構造親へ戻してもならない。

そうすると block 内逐次処理の意味が消える。

## 5. Parent Types

### 5.1 CONDITION

`children` と `else_children` は別ブロックとして扱う。

- `children` 最初のノード: 条件ノードへ依存
- `else_children` 最初のノード: 条件ノードへ依存
- それ以降: 各ブロック内の直前 sibling へ依存

### 5.2 LOOP

loop body の最初のノードは、loop 構造自体を入力文脈として受ける。

- 最初のノード: loop ノードへ依存
- それ以降: body 内の直前 sibling へ依存

ただし、loop ノード自身が何を反復しているかは、別途 loop の `input_link` で表される。

### 5.3 WRAPPER

wrapper 内の最初のノードは、wrapper が作る実行文脈に属する。

- 最初のノード: wrapper ノードへ依存
- それ以降: wrapper 内の直前 sibling へ依存

## 6. Boundary With Dataflow Semantics

この規則はあくまで「構造文脈の既定依存」を定めるものであり、実データの中身まで十分に表すとは限らない。

たとえば loop body の最初のノードが loop ノードへ依存していても、

- loop 対象集合がどこから来たか
- item の型が何か
- collection が deserialized output か

といった情報は別メタデータで補う必要がある。

したがって、この規則は `Dependency Loss` をゼロにする万能則ではなく、最低限の構造整合ルールである。

## 7. Relation To Current Fixes

現時点で実装に入った修正は、この規則の部分実装とみなせる。

- `ELSE` で branch base を条件ノードへ戻した修正
- `LOOP` / `WRAPPER` 内 first-child の既定 `input_link` を構造親へ寄せた修正

ただし現状は「first-child の既定接続」に留まっており、2 個目以降 sibling の規則や複雑な nested 構造まではまだ十分に固定されていない。

## 8. What This Rule Does Not Decide Yet

まだ未確定なのは次の点である。

- block 内 2 個目以降の sibling が、常に直前ノードでよいか
- `DISPLAY` や `RETURN` のようなノードで sequential dependency を省略してよいか
- nested `CONDITION inside LOOP` のとき、どの親を優先すべきか
- auto-inserted `DESERIALIZE` / `SERIALIZE` を sibling とみなすか補助ノードとみなすか

これらは次段の検証課題である。

## 9. Immediate Research Implication

今後 `Dependency Loss` を評価するときは、単に `input_link` の有無ではなく、

- そのノードは first-child か
- そのブロックの親は何か
- sibling 依存を持つべき段階か

をあわせて判定する必要がある。

## 10. Next Step

この文書の次にやるべきことは、`CONDITION`, `LOOP`, `WRAPPER` それぞれについて、

1. first-child
2. second sibling
3. nested child

の 3 パターンを持つ比較ケースを追加し、この規則が十分かどうかを確かめることである。
