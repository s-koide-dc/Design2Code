# Implementation Priority From Claims

## Purpose

この文書は、`claim_evidence_implementation_map.md` を使って
`substantiated`
と
`implemented`
の差分から、次に実装へ進めるべき論点を優先順位付きで整理するためのものである。

ここでの目的は、新しい論点を増やすことではなく、
すでに観測で支えられている主張のうち
`まだ実装へ十分落ちていないもの`
を明示することである。

## Priority Rule

優先順位は次の順で決める。

1. `substantiated` だが downstream や保守性に効く主張
2. `implemented` だが整理不足で再利用しにくい主張
3. 研究上は重要でも、policy 層だけで十分に扱える主張

要するに、次に実装する価値が高いのは
`観測で確かめたが、まだコード上の使い道が薄い主張`
である。

## Current Priority List

### Priority 1: Role-Weakening Claim の実装側明文化

対象主張:

- 「主要な意味損失は structure collapse より role weakening にある」

現在状態:

- `substantiated`

理由:

- 主要知見としては強いが、実装側では `spec_role` や promotion rule に分散しており、単独の enforcement point が弱い
- 今後の regression を考えると、role weakening を横断検出する diagnostics / assertion 層が欲しい

次の実装候補:

- benchmark suite に role-weakening regression table を追加する
- `IRGenerator` regression test を claim 単位で束ねる

### Priority 2: Alias Admission Policy の実装境界明文化

対象主張:

- 「alias admission は runtime heuristic ではなく schema policy として扱うべきである」

現在状態:

- `substantiated`

理由:

- 観測と policy は十分固まったが、runtime 実装上は benchmark schema への alias 定義に依存している
- 実運用へ持ち出すなら、schema 側の admission workflow か review guidance を実装寄りに固定する必要がある

次の実装候補:

- schema alias definition format の validation rule
- admission root を追跡する comment/template か review checklist

### Priority 3: Alias Timing 5類型の保守フロー化

対象主張:

- 「alias timing は 5 根拠で整理できる」

現在状態:

- `substantiated`

理由:

- policy と results は揃ったが、コードに専用 field を作らない設計なので、運用上の入口が曖昧になりやすい
- ここは runtime 実装より、results / benchmark / schema review の運用フロー化が必要である

次の実装候補:

- `schema_alias_admission_status_table.md` を更新する運用規則
- benchmark 追加時に timing root を必須化する template

### Priority 4: Provenance Layer の role 横断整備

対象主張:

- 「provenance metadata は downstream conservatism を制御できる」

現在状態:

- `implemented`

理由:

- すでにコード反映は進んでいるが、`CALCULATE` 中心で `CHECK` / `FILTER` との対称性はまだ薄い
- 新規研究主張というより、既存実装を role 横断で均す段階にある

次の実装候補:

- provenance-strength ごとの共通 helper 化
- `CHECK` / `FILTER` / `CALCULATE` の downstream policy 対応表を code comments か helper 名で揃える

## What Not To Prioritize Now

次は優先しない。

- 新しい alias category の追加
- runtime 側で admission timing を数える実装
- role / provenance / alias を一気に統一する大規模抽象化

理由は、どれも現段階では policy / benchmark で十分であり、
無理に runtime 側へ入れると決定論性より複雑性が増えるからである。

## Recommended Next Step

実装として次に一番筋が良いのは、
`Priority 1` と `Priority 2` の間をつなぐ
`schema alias / role weakening regression checklist`
を作ることである。

これなら runtime を肥大化させずに、
研究主張を regression 運用へ変換できる。
