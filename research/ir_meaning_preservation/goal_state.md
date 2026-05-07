# IR Meaning Preservation Goal State

## 1. Purpose

この文書は、`IR meaning preservation` 研究の着地点を明文化し、
`どこまで進めばこの研究を一段落と見なせるか`
を固定するためのものである。

ここでの goal は、
個別改善を増やし続けることではなく、
研究として十分な主張・根拠・実装接続・運用入口が揃った状態を定義することにある。

## 2. Final Research Question

この研究の最終的な問いは次のように定義する。

`決定論的な自然言語仕様処理において、意味保存を成立させる最小メタデータ体系と、その runtime / schema / policy の責務分担は何か`

つまり、単に `IR の精度が高いか` ではなく、

- 何を意味保存の必須 metadata とするか
- どこまでを runtime で解決するか
- どこからを schema / policy 側で扱うか

を説明できることが着地点になる。

## 3. Goal State

この研究が一段落したと言えるのは、少なくとも次の 4 条件を満たしたときである。

### Goal A: Theory Is Stated

次の 3 層が、独立した理論単位として説明できる。

1. `role`
2. `provenance`
3. `alias admission timing`

期待状態:

- role weakening が主要失敗として定義されている
- provenance が resolved value と区別されている
- alias admission が runtime heuristic ではなく policy 層として定義されている

### Goal B: Benchmark Evidence Is Sufficient

主張が benchmark と observed IR で再現的に支えられている。

期待状態:

- 主要失敗類型ごとに代表ケースがある
- `Expected IR -> Observed IR -> Diff -> Failure Mapping` の流れがある
- alias timing 5類型まで benchmark 上で固定されている

### Goal C: Implementation Is Connected

研究主張が実装へ接続されている。

期待状態:

- 主要 metadata は IR / downstream に保持・利用されている
- `claim_evidence_implementation_map.md` で claim と code の対応が追える
- `IRGenerator` の整理が研究概念に沿っている

### Goal D: Operational Entry Exists

研究成果が運用に落ちる入口を持っている。

期待状態:

- regression checklist がある
- admission timing の status table がある
- 新規 benchmark 追加時の読み方が固定されている

## 4. What Is Not Required For Done

次は、この研究の done 条件には含めない。

- すべての自然言語仕様で高精度に動くこと
- 全 role で完全な定量比較を出すこと
- runtime 側で alias timing を自動推定すること
- `IRGenerator` の最終アーキテクチャを確定すること

理由は、この研究の価値が
`全部解けること`
ではなく
`何をどう管理すべきかを原理として示すこと`
にあるからである。

## 5. Concrete Done Signals

次のシグナルが揃えば、少なくとも研究としては一段落とみなしてよい。

1. `research_outcome_memo.md` が更新され、主張が 1 ページで読める
2. `claim_evidence_implementation_map.md` で主要 claim が全部追える
3. `schema_alias_admission_timing_matrix.md` と `results/schema_alias_admission_status_table.md` で alias timing が横断的に読める
4. `schema_alias_role_weakening_regression_checklist.md` で運用入口がある
5. `midterm_synthesis.md` とこの文書の内容に矛盾がない

## 6. Current Assessment Against Goal

現時点では、次のように評価できる。

- Goal A: largely satisfied
- Goal B: largely satisfied
- Goal C: mostly satisfied
- Goal D: satisfied at workflow-entry level

したがって、今の研究は
`まだ始まったばかり`
ではなく、
`done の輪郭が見えていて、残りは圧縮と整合化の段階`
にある。

## 7. Best Next Step

この goal state を前提にすると、次にやるべきことは新論点の追加ではない。

最も筋が良いのは次のどちらかである。

1. ここまでの成果を外向け報告用にさらに圧縮する
2. `claim -> evidence -> implementation -> checklist` の一貫性を最終点検する

つまり今後は、
`広げる`
より
`閉じる`
フェーズに入るのが自然である。
