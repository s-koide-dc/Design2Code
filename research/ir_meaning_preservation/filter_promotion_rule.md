# FILTER Promotion Rule

## 1. Purpose

この文書は、`FETCH` と衝突しやすい曖昧語彙を含む step でも、十分な semantic evidence がある場合にだけ `LINQ/FILTER` へ昇格させる最小規則を定義するためのものである。

目的は、`case_16_filter_predicate_provenance` を成立させつつ、`抽出` のような fetch 的にも使われる語彙を安易に `FILTER` へ固定しないことである。

## 2. Problem Statement

現状の観測では、次の 2 条件が重なって `FILTER` が成立しない。

1. `抽出` が `FETCH` と `LINQ` の両方の語彙集合に入っている
2. logic goal に比較 predicate があっても、`intent == "GENERAL"` のときしか `LINQ/FILTER` へ上げ直せない

この結果、`Points が input_1 より大きいユーザーを抽出する。` は predicate 情報を持ちながら `FETCH/FETCH` に留まる。

## 3. Design Goal

昇格規則の目標は次の 3 点である。

1. 比較 predicate と upstream collection context を持つ step を `FILTER` へ上げる
2. `ユーザーを抽出する` のような fetch 的文面は `FETCH` のまま残す
3. `CHECK`, `DISPLAY`, `CALCULATE` を誤って `FILTER` に食わせない

## 4. Promotion Inputs

昇格判定に使う候補情報は次の通りとする。

### 4.1 Strong Semantic Signals

- `logic_goals` に `numeric`, `string`, `logic` の predicate がある
- `semantic_roles.property` がある
- `semantic_roles.ops` に filter 系 operation がある

### 4.2 Structural Context

- 前段 `input_link` がある
- 直前文脈が `COLLECTION`
- 直前 `output_type` が collection 型である

### 4.3 Ambiguous Lexical Signals

- `抽出`, `選択`, `select`, `where`

これらは単独では使わない。

## 5. Core Rule

`FILTER` への昇格は、次の条件を満たす場合にだけ許可する。

### Rule A

現在 intent が `GENERAL` で、predicate 型 `logic_goals` がある場合は `LINQ/FILTER` へ上げる。

これは現行ルールの維持である。

### Rule B

現在 intent が `FETCH` または `TRANSFORM` であっても、次の 3 条件を同時に満たす場合は `LINQ/FILTER` へ上げる。

1. ambiguous lexical signal がある
2. predicate 型 `logic_goals` がある
3. upstream collection context がある

この 3 条件が揃ったときだけ、先着した `FETCH` を巻き戻して `FILTER` を優先する。

## 6. Explicitly Disallowed Promotions

次のケースでは `FILTER` へ上げてはならない。

### 6.1 Pure Fetch

- `ユーザーを抽出する`
- `結果を抽出して取得する`

predicate が無い場合は `FETCH` に留める。

### 6.2 Check Ambiguity

- `Points が 100 より大きいか確認する`

主役が判定である場合は `CHECK` を優先する。

### 6.3 Display Ambiguity

- `抽出結果を表示する`

主役が表示である場合は `DISPLAY` を優先する。

### 6.4 Calculate Ambiguity

- `抽出件数を計算する`

主役が集約や計算である場合は `CALCULATE` を優先する。

## 7. Promotion Procedure

昇格判定の順序は次の通りとする。

1. `CHECK` 判定
2. `DISPLAY` 判定
3. `CALCULATE` 判定
4. `FETCH/TRANSFORM` の初期判定
5. Rule A / Rule B による `FILTER` 巻き戻し判定
6. どれにも当てはまらなければ元 intent を維持

この順序により、`FILTER` が後付けで他役割を食い潰すことを防ぐ。

## 8. Why This Is Not Cheap Keyword Matching

この規則は `抽出` のような語彙を使うが、単独使用はしない。

昇格には必ず、

- predicate 型 `logic_goals`
 かつ
- upstream collection context

が必要である。

したがって、単語だけで `FILTER` へ上げる設計ではない。

## 9. Expected Effect On Current Cases

### Case 16

- `抽出` という曖昧語彙がある
- numeric predicate の `logic_goals` がある
- 前段 `FETCH` が collection を返している

したがって Rule B で `LINQ/FILTER` に上がるべきである。

### Pure Fetch Contrast

- `ユーザーを抽出する`

曖昧語彙はあるが predicate がないため、`FETCH` のまま残す。

## 10. Minimal Implementation Boundary

最初の変更は `IRGenerator._analyze_step_integrated` と、その前段の intent 補正に限定するのが妥当である。

触る候補:

- `logic_goals` と collection context を使った `FILTER` 再昇格条件
- ambiguous lexical signal 判定
- `semantic_roles.property` の最小保持

まだ触らない候補:

- `ActionSynthesizer`
- `linq_handler`
- downstream provenance policy

## 11. Exit Condition

この設計が成立したと判断する条件は次の通りである。

1. `case_16` が `LINQ/FILTER` に上がる
2. `predicate_resolution=logic_goal` と `collection_resolution=explicit_input_link` を保持できる
3. `ユーザーを抽出する` のような contrast case は `FETCH` のまま残る
4. 既存 `CHECK`, `DISPLAY`, `CALCULATE` ケースに誤昇格が出ない

## 12. Next Step

次にやるべきことは、この規則を `IRGenerator` に最小実装し、`case_16` と contrast case の両方で回帰確認することである。
