# Schema Alias Admission Regression Table

## Purpose

この表は、`schema alias admission` を
回帰確認の観点で横断比較するための基準表である。

`schema_alias_admission_timing_matrix.md` は policy 上の根拠分類、
`schema_alias_admission_status_table.md` は current status の観測表であり、
この文書はそれらを実運用の regression check に圧縮した一覧である。

## Reading Rule

- `Timing Root` は alias admission の根拠分類
- `Admission State` は schema に今入っているかどうか
- `IR Effect` は admission の結果として IR 上で何が強くなるか
- `Regression Check` は変更時に最低限確認すべき観点

## Table

| Timing Root | Main Policy Risk | Admission State | Expected IR Effect | Downstream Impact | Baseline Status | Key Evidence | Regression Check |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Hold For Evidence` | 根拠不足の alias を早すぎる admission で入れてしまう | not admitted | lexical retention のまま残す | weak retention が維持されるのが正しい | Stable | `schema_alias_admission_threshold.md`, `case_27`, `schema_alias_admission_status_table.md` | alias を追加していないのに `schema_property` へ上がっていないか |
| `Repeated Spec Use` | 局所反復を見落として admission すべき alias を hold したままにする | admitted | canonical property | `CHECK` / `FILTER` が `schema_property` に上がる | Stable | `case_28`, `schema_alias_admission_threshold_observation.md` | 同一 owner 文脈の反復があるとき canonicalization が成立するか |
| `Cross-Case Relevance` | benchmark 横断で再出する lexical token を放置し、同じ失敗を繰り返す | admitted | canonical property | cross-case で同じ weak retention が消える | Stable | `case_29`, `schema_alias_admission_timing_matrix.md` | 複数ケースで同一 token が再出したとき admission 判断が揺れていないか |
| `Downstream Impact` | weak retention のまま残して downstream conservatism を不必要に強める | admitted | canonical property | comparison / filter / calc の concretization が適切に強化される | Stable | `case_30`, `cross_role_provenance_design.md` | canonicalization 後に TODO 停止や generic fallback が不要に残っていないか |
| `External Compatibility` | 外部帳票語や契約語を generic token 扱いして互換を壊す | admitted | canonical property | 外部語彙でも deterministic に property へ乗る | Stable | `case_31`, `schema_alias_admission_threshold_observation.md` | 外部互換 alias が lexical retention に戻っていないか |

## Current Interpretation

2026-05-07 時点では、
admission timing の 5 類型は benchmark と observed IR で閉じており、
主な回帰リスクは runtime 側の推論不足より
`schema admission state` と `policy root` の取り違えにある。

重要なのは次の 2 点である。

1. alias admission は runtime heuristic ではなく schema policy で決める
2. regression は `schema_property` に上がる/上がらないの差だけでなく、
   その差が正しい timing root に対応しているかで見る

## Relationship To Other Tables

- `schema_alias_admission_timing_matrix.md`
  - root の意味と最小根拠を示す
- `schema_alias_admission_status_table.md`
  - current observation を representative case で示す
- `schema_alias_admission_regression_table.md`
  - 次の変更時に何を壊してはいけないかを示す

## Recommended Use

1. schema alias を追加・削除する前に、対象 alias がどの row に属するかを先に決める。
2. 変更後は `regression_run_template` に、この表の `Regression Check` を転記して使う。
3. 新しい timing root 相当の論点を追加した場合は、まずこの表に行を追加してから case を増やす。
