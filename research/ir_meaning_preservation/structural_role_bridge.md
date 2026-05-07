# Structural Role Bridge

## 1. Purpose

この文書は、`WRAP`, `ITERATE`, `CALCULATE` の 3 役割について、`spec_role` から runtime 側へどう橋渡しするべきかを整理するためのものである。

ここで重要なのは、3 つを同一方式で扱わないことである。

- `CALCULATE` は主に操作 role
- `ITERATE` は主に構造 role
- `WRAP` は純粋な構造 role

したがって、「全部 runtime_role に写す」方針は不適切である。

## 2. Current State

### 2.1 CALCULATE

- `IRGenerator` は計算系を `intent=CALC`, `role=CALC`, `spec_role=CALCULATE` に寄せられる場合がある
- `ActionSynthesizer` は `spec_role=CALCULATE` を `runtime_role=CALC` として解釈できる
- つまり橋はすでに部分的に存在する

### 2.2 ITERATE

- `IRGenerator` は `node_type=LOOP` に対して `spec_role=ITERATE` を付ける
- 現在は `intent=GENERAL`, `role=ITERATE` として表現できる
- `ActionSynthesizer` 側では `node_type=LOOP` を直接 `handle_loop` へ送っており、runtime role そのものより node type が主要消費点である

### 2.3 WRAP

- `IRGenerator` は retry wrapper 相当のノードに `spec_role=WRAP` を付けられるようになった
- ただし runtime 側では `role=ACTION` のままであり、専用 consumer はまだない
- したがって `WRAP` は、現時点では「保存はできるが、消費は未整備」の状態にある

## 3. Bridge Principles

### Principle 1

`CALCULATE` は runtime role へ橋渡ししてよい。

理由:

- 計算処理は downstream で method/template 選択に効く
- `CALC` は操作クラスとして意味を持つ

### Principle 2

`ITERATE` は runtime role へ完全写像するより、`node_type=LOOP` として消費するのを主とする。

理由:

- 反復の本質は操作種別ではなく構造境界にある
- runtime role だけで loop body の処理規則を十分に表せない

したがって、`ITERATE` の橋渡しは「runtime role を与えること」より「LOOP ノードとして downstream が正しく消費すること」を優先する。

### Principle 3

`WRAP` は当面 runtime role へ落とし込まない。

理由:

- wrapper は fetch/display/persist のような操作クラスではない
- retry, transaction, audit, timeout など wrapper 種別ごとの意味差が大きい
- 単に `ACTION` 以外の 1 語へ落としても downstream の安定化には直結しない

したがって、まずは `spec_role=WRAP` と `wrapper_kind` を保存し、消費側を別設計で用意するのが筋である。

## 4. Recommended Bridge Table

| `spec_role` | Current Bridge Policy | Primary Consumer |
|---|---|---|
| `CALCULATE` | `runtime_role=CALC` へ橋渡し | `ActionSynthesizer` / `calc_handler` |
| `ITERATE` | `node_type=LOOP` を主に使い、補助的に `role=ITERATE` を保持 | `ActionSynthesizer.handle_loop` |
| `WRAP` | runtime role へは当面橋渡ししない。`spec_role` と `wrapper_kind` を保持 | 将来の wrapper consumer |

## 5. What Was Confirmed

現時点で確認できたのは次の点である。

1. `ITERATE` は IR 上で `role=ITERATE` として保持しても既存 loop 処理を壊さない
2. `WRAP` は `spec_role=WRAP` として保持できる
3. dependency 規則と構造 role 規則は分けて考えるべきである

## 6. Remaining Gaps

### 6.1 CALCULATE Gap

- 計算語彙が弱いケースでは `GENERAL/ACTION` に戻る
- `spec_role=CALCULATE` が常に取れるわけではない

### 6.2 ITERATE Gap

- `target_entity` が `Item` に寄りやすい
- loop 構造は見えるが、反復対象の型意味が弱い

### 6.3 WRAP Gap

- retry wrapper をどう codegen に反映するか未定
- wrapper body の try/catch/retry 展開を誰が担うか未定

## 7. Immediate Recommendation

次段の実装優先順は次の通りである。

1. `CALCULATE` の検出安定化
2. `ITERATE` の entity / source 継承改善
3. `WRAP` は runtime role 化せず、まず wrapper consumer 設計へ進む

## 8. Next Step

この文書の次にやるべきことは、`CALCULATE` を first target として、なぜ `価格を計算する` のようなケースで `GENERAL/ACTION` に戻るのかを局所追跡することである。
