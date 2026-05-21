# Schema Alias Admission Timing Matrix

## 1. Purpose

この文書は、`schema_alias_admission_threshold.md` と
`results/schema_alias_admission_threshold_observation.md` で扱った
admission timing の根拠を、研究全体で横断的に読める matrix に正規化するためのものである。

目的は、個別ケースの結論を再度列挙することではなく、
`どの根拠で alias を schema に入れるのか`
`その結果 IR 上で何が強化されるのか`
を 1 枚で比較可能にすることにある。

## 2. Canonical Matrix

| Admission Timing Root | Meaning | Minimal Evidence | Expected IR Effect | Representative Cases |
| --- | --- | --- | --- | --- |
| `Hold For Evidence` | deterministic だが、まだ schema に入れない | owner-confined かつ canonical non-ambiguity だが benchmark need が弱い | lexical retention のまま残す | `case_27` |
| `Repeated Spec Use` | 同一 owner context で反復使用されている | 同一 lexical token が同一 owner 文脈で 2 回以上使われる | `schema_property` へ昇格 | `case_28` |
| `Cross-Case Relevance` | benchmark 横断で再出する | 複数ケースで同じ lexical token が canonicalization failure 原因として出る | `schema_property` へ昇格 | `case_29` |
| `Downstream Impact` | weak retention が downstream conservatism を強める | lexical retention のままだと `CHECK` / `FILTER` / `CALCULATE` の比較や生成が不必要に弱くなる | `schema_property` へ昇格 | `case_30` |
| `External Compatibility` | 外部帳票語や外部契約との互換が必要 | 実装内部ではなく外部制約で alias 維持が必要と説明できる | `schema_property` へ昇格 | `case_31` |

## 3. IR Reading Rule

admission timing は runtime field として IR に直接書く対象ではない。

この研究での読み方は次の通りである。

1. policy 側で admission timing root を決める
2. schema に alias を入れるか保留するかを決める
3. IR ではその結果として
   - `check_subject`
   - `property`
   - `subject_resolution`
   - `predicate_resolution`
   が lexical retention か canonical property かに分かれる

つまり timing root は IR field ではなく、
`IR をどう読むべきかを支える schema-admission の根拠`
として扱う。

## 4. Research Interpretation

この matrix から、次のことが言える。

1. alias admission の主要論点は `can resolve?` ではなく `should admit now?` に移っている
2. `spec_role` や provenance と同様に、alias admission も upstream runtime heuristic ではなく policy-driven schema management の問題として扱うのが自然である
3. IR meaning preservation の観点では、alias timing を runtime 側へ押し込むより、schema 側で管理した方が決定論性を壊しにくい

## 5. Connection To Broader Research

この matrix は、IR meaning preservation 全体の中では次の位置づけを持つ。

- `role_layer_definition.md`
  - role の意味保存を整理する
- `cross_role_provenance_design.md`
  - provenance の強度を整理する
- `schema_alias_admission_timing_matrix.md`
  - canonical property admission の timing を整理する

要するに、現在の研究は
`role`
`provenance`
`alias admission timing`
の 3 層を別々に整理し、それらを downstream conservatism と結び付ける段階に入っている。

## 6. Immediate Next Step

`Hold For Evidence` を含む current status は
[results/schema_alias_admission_status_table.md](research/ir_meaning_preservation/results/schema_alias_admission_status_table.md:1)
で一貫表現できるようになった。

次にやるべきことは、この matrix と status table を使って
`claim -> evidence -> implementation -> checklist`
の閉路を最終点検することである。
