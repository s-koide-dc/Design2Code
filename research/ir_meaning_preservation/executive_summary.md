# IR Meaning Preservation Executive Summary

## What This Research Is About

この研究は、自然言語で書かれた設計仕様を IR に変換するときに、
`どの意味が保存され、どの意味が失われるか`
を決定論的に説明することを目的としている。

焦点は精度競争ではない。
重要なのは、

- 何を metadata として保持すべきか
- どこまでを runtime で解決すべきか
- どこからを schema / policy 側で扱うべきか

を、benchmark と実装の両方で説明できるようにすることである。

## Main Findings

### 1. Main Meaning Loss Is Role Weakening

初期観測で分かったのは、主要な失敗が
`構造が完全に壊れること`
よりも
`role が弱く表現されること`
にある点である。

代表的には、

- `FILTER` が `FETCH` に落ちる
- `CHECK` が弱くなる
- `CALCULATE` が `GENERAL/ACTION` に落ちる

という形で現れる。

### 2. Provenance Matters as Much as Resolved Value

解決結果だけでは不十分であり、
`なぜそう解決したか`
を保持する provenance metadata が必要であることが確認できた。

この metadata は、意味保存の記録だけでなく、
downstream code synthesis を安全側へ制御する入力としても使える。

### 3. Alias Admission Is a Policy Problem

alias 問題は、runtime heuristic を増やして解くよりも、
`いつ schema alias として採用するか`
を policy と benchmark で管理する方が決定論性を保ちやすい。

この研究では、

- `Hold For Evidence`
- `Repeated Spec Use`
- `Cross-Case Relevance`
- `Downstream Impact`
- `External Compatibility`

の 5 類型で admission timing を整理できた。

## What Has Been Demonstrated

この研究では、少なくとも次を benchmark と実装の両方で確認できた。

- `spec_role` を IR に保持できる
- `CHECK`, `FILTER`, `CALCULATE` で resolution / provenance metadata を保持できる
- provenance 強度によって downstream conservatism を変えられる
- structural dependency を一般規則として扱える
- `IRGenerator` の肥大化を研究概念に沿って整理できる

## Why It Matters

この研究の価値は、
単に特定ケースの生成精度を上げたことではない。

価値があるのは、

- 意味保存に必要な最小 metadata 体系
- runtime と schema / policy の責務分担
- それを検証する benchmark と regression workflow

を、一貫した形で提示できるようになった点にある。

## Current Status

現時点では、

- 理論層は概ね整理済み
- benchmark と observed IR は主要論点を十分に支えている
- 実装との接続も大部分できている
- 運用入口として checklist と status table も整っている

したがって、この研究は
`拡張フェーズ`
より
`圧縮と整合化のフェーズ`
に入っている。

## Final Framing

この研究の最終的な主張は、次の一文に圧縮できる。

`決定論的な自然言語仕様処理では、意味保存は runtime heuristic の追加ではなく、role・provenance・alias admission timing を分離した metadata 設計と schema/policy 管理によって成立する。`
