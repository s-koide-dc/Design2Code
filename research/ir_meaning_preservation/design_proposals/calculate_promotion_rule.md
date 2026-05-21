# CALCULATE Promotion Rule

## 1. Purpose

この文書は、`GENERAL/ACTION` から `CALC/CALCULATE` へ昇格させる最小規則を定義するためのものである。

目的は、`価格を計算する` のような計算ステップを安定して扱えるようにしつつ、安易なキーワードマッチへ戻らないことである。

## 2. Problem Statement

現状の観測では、`CALCULATE` へ上がる主条件が `logic_goals.calculation` の存在に強く依存している。

そのため、

- `target_hint` があっても `CALCULATE` に上がらない
- `property` があっても `CALCULATE` に上がらない
- 計算語彙があっても `logic_goals` が空なら `GENERAL/ACTION` に落ちる

という状態が起きている。

## 3. Design Goal

昇格規則の目標は次の 3 点である。

1. explicit semantic metadata がある計算ステップを確実に `CALCULATE` へ上げる
2. metadata が弱い自然言語ケースでは過剰昇格しない
3. `FILTER`, `TRANSFORM`, `CHECK` と誤衝突しない

## 4. Promotion Inputs

昇格判定に使う候補情報は次の通りとする。

### 4.1 Strong Signals

- `logic_goals` に `type=calculation` がある
- `semantic_roles.target_hint` がある
- `semantic_roles.property` がある
- `semantic_roles.ops` に calculation 系 operation がある

### 4.2 Structural Context

- 前段 `input_link` がある
- 前段 `target_entity` が存在する
- loop body 内で active item がある

### 4.3 Weak Lexical Signal

- 「計算する」「算出する」「求める」などの calculation intent を示す語彙

ただしこれは単独では使わない。

## 5. Core Rule

`CALCULATE` への昇格は、次の条件を満たす場合にだけ許可する。

### Rule A

`logic_goals` に `type=calculation` がある場合は、`intent=CALC`, `role=CALC`, `spec_role=CALCULATE` へ昇格する。

これは現行仕様をそのまま維持する強条件である。

### Rule B

`logic_goals.calculation` がなくても、次の 2 条件を同時に満たす場合は昇格を許可する。

1. `semantic_roles.target_hint` または `semantic_roles.property` がある
2. calculation intent を示す弱語彙シグナルがある

ここで重要なのは、「語彙だけ」でも「target_hint だけ」でも昇格しないことである。

## 6. Explicitly Disallowed Promotions

次のケースでは `CALCULATE` へ上げてはならない。

### 6.1 Filter/Transform Ambiguity

- `ops=select`, `ops=map`, `ops=normalize` など、変換として解釈すべきもの
- collection 全体を変形するだけで数値更新や計算対象が見えないもの

### 6.2 Check Ambiguity

- 「計算結果が 0 より大きいか確認する」のように、主役が判定であるもの

### 6.3 Display Ambiguity

- 「計算結果を表示する」のように、主役が表示であるもの

## 7. Promotion Procedure

昇格判定の順序は次の通りとする。

1. `CHECK` 判定を先に行う
2. `FILTER` / `TRANSFORM` 判定を行う
3. `logic_goals.calculation` を確認する
4. strong metadata + weak calculation signal の組み合わせを確認する
5. どれにも当てはまらなければ `GENERAL/ACTION` のまま残す

この順序により、後付けで `CALCULATE` が他役割を食い潰すことを防ぐ。

## 8. Why This Is Not Cheap Keyword Matching

この規則は calculation 語彙を使うが、単独使用はしない。

昇格には必ず、

- `logic_goals.calculation`
  または
- explicit semantic metadata (`target_hint` / `property`)

が必要である。

したがって、「計算」という単語があるだけで `CALC` に上げる設計ではない。

## 9. Expected Effect On Current Cases

### Case 12

- `target_hint=DiscountedPrice`
- `property=DiscountedPrice`
- text に calculation intent がある

したがって Rule B で `CALCULATE` に昇格できるはずである。

### Case 13

- calculation intent はある
- しかし explicit target metadata がない

したがって昇格させず、`GENERAL/ACTION` に残す。

この差が出るなら、設計意図どおりである。

## 10. Minimal Implementation Boundary

最初の実装変更は `IRGenerator._analyze_step_integrated` 周辺に限定するのが妥当である。

触る候補:

- calculation 昇格条件
- `semantic_roles.target_hint/property` の読み取り
- `spec_role` 決定前の intent 補正

まだ触らない候補:

- `ActionSynthesizer`
- `calc_handler`
- `SemanticBinder`

downstream bridge はすでに存在するため、初回変更は upstream だけで十分である。

## 11. Exit Condition

この設計が成立したと判断する条件は次の通りである。

1. `case_12` が `CALC/CALCULATE` に上がる
2. `case_13` は `GENERAL/ACTION` のまま残る
3. 既存の `FILTER`, `CHECK`, `DISPLAY` ケースに誤昇格が出ない

## 12. Next Step

次にやるべきことは、この規則を `IRGenerator` に最小実装し、`case_12` / `case_13` と既存 `IRGenerator` テストで回帰を確認することである。
