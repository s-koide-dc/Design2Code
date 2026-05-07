# Schema Alias Admission Threshold Observation

## Scope

この文書は、`schema_alias_admission_threshold.md` における
`Hold For Evidence` と `Repeated Spec Use` の境界が observed IR にどう現れるかを比較するための初回観測結果である。

対象:

- `case_27_admissible_but_deferred_alias`
- `case_28_repeated_spec_use_promotes_alias`
- `case_29_cross_case_relevance_threshold`
- `case_30_downstream_impact_threshold`
- `case_31_external_compatibility_threshold`

## Summary

### Case 27: Admissible But Deferred Alias

- Observed IR:
  - `step_2` は `comparison_check`
  - `step_6` は `LINQ/FILTER`
- Preserved metadata:
  - `check_subject=受注区分`
  - `subject_resolution=explicit_subject`
  - `property=受注区分`
  - `predicate_resolution=logic_goal`

Reading:

- alias candidate `受注区分 -> OrderCategory` は owner-confined かもしれないが、schema にまだ admission していない前提では lexical retention に留まる
- ここで重要なのは、これは rejection ではなく `admissible but deferred` の観測であること
- 現行観測では、`can_admit` と `should_admit_now` を schema admission の有無として分離して読める

### Case 28: Repeated Spec Use Promotes Alias

- Observed IR:
  - `step_2` は `comparison_check`
  - `step_6` は `LINQ/FILTER`
- Preserved metadata:
  - `check_subject=OrderCategory`
  - `subject_resolution=schema_property`
  - `property=OrderCategory`
  - `predicate_resolution=schema_property`

Reading:

- 同じ lexical token `受注区分` を repeated-use で admission した前提では、`CHECK` / `FILTER` の両方で canonical property に上がった
- したがって repeated-use threshold を満たして schema に入った後は、通常の `schema_property` path として扱ってよい

### Case 29: Cross-Case Relevance Threshold

- Observed IR:
  - `step_2` は `comparison_check`
  - `step_6` は `LINQ/FILTER`
- Preserved metadata:
  - `check_subject=OrderCategory`
  - `subject_resolution=schema_property`
  - `property=OrderCategory`
  - `predicate_resolution=schema_property`

Reading:

- `受注区分` は `case_27` / `case_28` に続いて benchmark 横断で再出しているため、`Cross-Case Relevance` により admission 根拠を持つ
- repeated-use をこのケース単独で持たなくても、cross-case relevance を理由に canonical property path へ上げられる整理で矛盾しない

### Case 30: Downstream Impact Threshold

- Observed IR:
  - `step_2` は `comparison_check`
  - `step_6` は `LINQ/FILTER`
- Preserved metadata:
  - `check_subject=InventoryCount`
  - `subject_resolution=schema_property`
  - `property=InventoryCount`
  - `predicate_resolution=schema_property`

Reading:

- `棚卸数量` は lexical retention のままだと downstream comparison / filter generation を weak path に押しやすい alias として admission された前提で canonical property に上がった
- したがって threshold は repeated-use だけでなく、downstream conservatism の強さを減らす必要性でも説明できる

### Case 31: External Compatibility Threshold

- Observed IR:
  - `step_2` は `comparison_check`
  - `step_6` は `LINQ/FILTER`
- Preserved metadata:
  - `check_subject=InvoiceAmount`
  - `subject_resolution=schema_property`
  - `property=InvoiceAmount`
  - `predicate_resolution=schema_property`

Reading:

- `請求金額` は帳票語や外部連携語として互換維持が必要な alias として admission された前提で canonical property に上がった
- したがって threshold は benchmark 内の再出や downstream 影響だけでなく、外部制約そのものでも説明できる

## Cross-Case Interpretation

この contrast から、次のことが明確になった。

1. `owner-confined` で deterministic でも、schema にまだ入れない段階では lexical retention が正しい
2. 同じ alias でも、`Repeated Spec Use`, `Cross-Case Relevance`, `Downstream Impact`, `External Compatibility` のいずれかが揃えば canonical property に上がる
3. したがって threshold の本体は IR 推論規則ではなく、schema admission timing にある
4. threshold の違いは runtime の意味解釈ではなく、alias を schema にいつ載せるかの根拠分類として整理するのが自然である

つまり、この段階の研究課題は「runtime で repeated-use を数えること」ではなく、
「どの時点で schema alias として採用するか」を benchmark と policy の側で説明可能にすることだと整理できる。

## Immediate Conclusion

次段で優先すべきなのは次の 2 点である。

1. admission timing 根拠の 5 類型を `claim -> evidence -> implementation` の流れへ統合する
2. current status table を benchmark 運用の標準入口として固定する

研究の流れとしては、ここから先は alias admission の「可否」ではなく、
「admission timing の根拠」を benchmark 単位で揃えていく段階である。
