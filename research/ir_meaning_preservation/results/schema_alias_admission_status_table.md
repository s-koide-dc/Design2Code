# Schema Alias Admission Status Table

## Purpose

この文書は、alias admission timing を results 側で一貫表現するための一覧表である。

`schema_alias_admission_timing_matrix.md` は policy 上の根拠分類を示す。
それに対してこの文書は、各 representative case が
`schema admission 前`
`schema admission 後`
のどちらにあるかを、IR 上の観測結果と一緒に短く確認するためのものである。

## Table

| Case | Timing Root | Schema Admission State | Canonicalization Result | CHECK Resolution | FILTER Resolution | Reading |
| --- | --- | --- | --- | --- | --- | --- |
| `case_27` | `Hold For Evidence` | not admitted | lexical retained | `explicit_subject` | `logic_goal` | deterministic でも evidence 不足なら hold |
| `case_28` | `Repeated Spec Use` | admitted | canonical property | `schema_property` | `schema_property` | 同一 owner 文脈での反復使用が admission 根拠 |
| `case_29` | `Cross-Case Relevance` | admitted | canonical property | `schema_property` | `schema_property` | benchmark 横断の再出が admission 根拠 |
| `case_30` | `Downstream Impact` | admitted | canonical property | `schema_property` | `schema_property` | weak retention が downstream を弱めるため admission |
| `case_31` | `External Compatibility` | admitted | canonical property | `schema_property` | `schema_property` | 外部帳票語 / 外部契約との互換が admission 根拠 |

## Reading Guidance

この table の目的は、runtime の差を示すことではない。

重要なのは次の 2 点である。

1. `Schema Admission State`
   - alias を schema にまだ入れていないのか、すでに入れているのか
2. `Canonicalization Result`
   - その結果として IR が lexical retention に留まるのか、canonical property path に入るのか

したがって、この table は
`IR 推論規則の表`
ではなく
`schema admission policy の観測表`
として読むべきである。

## Immediate Use

今後 benchmark を追加するときは、alias timing が論点になるケースをこの table に追記する。

そのとき最低限埋める列は次の 4 つで十分である。

- `Timing Root`
- `Schema Admission State`
- `CHECK Resolution`
- `FILTER Resolution`

これで、個別ケースの本文を読まなくても current status を横断把握できる。
