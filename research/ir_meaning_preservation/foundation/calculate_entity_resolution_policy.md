# CALCULATE Entity Resolution Policy

## 1. Purpose

この文書は、`CALCULATE` ノードに付与された `semantic_roles.entity_resolution` を downstream でどう扱うかを統一するためのものである。

目的は、IR 上で観測できる entity 解決由来を、そのまま code synthesis の保守性へ接続することである。

## 2. Resolution Kinds

`entity_resolution` の初期値は次の 4 種類である。

- `unique_owner`
- `explicit_entity`
- `history_fallback`
- `ambiguous`

## 3. Downstream Policy Matrix

### 3.1 `unique_owner`

- 意味: property owner が schema 上で一意に決まった
- 扱い:
  - exact entity binding を許可する
  - property 解決を許可する
  - 通常の `CALCULATE` 合成を許可する

### 3.2 `explicit_entity`

- 意味: すでに node または semantic metadata に non-weak entity がある
- 扱い:
  - exact entity binding を許可する
  - property 解決を許可する
  - 通常の `CALCULATE` 合成を許可する

### 3.3 `history_fallback`

- 意味: property owner は確定していないが、直近文脈の non-weak entity を継承した
- 扱い:
  - target entity 自体は使ってよい
  - ただし cross-entity の再推定はしない
  - exact target に対する property 解決は許可する
  - 「別 entity へ勝手に乗り換える fallback」は禁止する

### 3.4 `ambiguous`

- 意味: property owner 候補が複数あり、一意に決められない
- 扱い:
  - property owner を決め打ちしない
  - cross-entity fallback を禁止する
  - exact assignment や property expression を安全に組めない場合は、保守的な TODO 停止へ送る

## 4. Core Principle

`entity_resolution` が弱くなるほど、downstream は「より少ないことだけをする」べきである。

つまり、policy は次の単調性を持つ。

- `unique_owner` / `explicit_entity`: 通常合成
- `history_fallback`: exact target 限定の保守合成
- `ambiguous`: 停止寄りの保守合成

## 5. Minimal Implementation Rule

初回実装では、少なくとも次の 2 点を守ればよい。

1. `history_fallback` / `ambiguous` では、active scope から無関係な別 entity を拾う fallback をしない
2. `ambiguous` では、property assignment を安全に組めないときに TODO 停止へ送る

## 6. Exit Condition

この方針が揃ったと判断する条件は次の通りである。

1. `unique_owner` は通常の property-aware `CALCULATE` を生成できる
2. `history_fallback` は exact target がある限り通常処理できる
3. `ambiguous` は arbitrary な POCO/property selection をしない
4. 4 類型の差が research 文書と unit test の両方で読める
