# Return Provenance Observation

## Purpose

この文書は、`RETURN` に対して導入した provenance metadata が、
literal return と value return を IR 上で分離できるかを確認するための観測記録である。

ここでの焦点は runtime codegen そのものではなく、`RETURN` の resolved value と provenance が
cross-role provenance design の枠組みに沿って保存されているかにある。

## Observation Case

- [case_32_return_provenance_contrast.md](research/ir_meaning_preservation/cases/case_32_return_provenance_contrast.md:1)

## Main Observation

### 1. Literal Return

`null を返す。` は次の metadata を保持した。

- `spec_role=RETURN`
- `return_value=null`
- `return_value_resolution=literal_null`

このため、literal return は latest-var fallback に吸収されず、
explicit return として downstream に橋渡しできる。

### 2. Input-Link Return

`取得したユーザーを返す。` は次の metadata を保持した。

- `spec_role=RETURN`
- `input_link=step_2`
- `return_source_node_id=step_1`
- `return_value_resolution=input_link_var`

重要なのは、structural dependency と semantic return source が分かれた点である。

- `input_link=step_2`
  - branch 内の構造依存
- `return_source_node_id=step_1`
  - 実際に返すべき upstream value source

これにより、`RETURN` でも `resolved value + provenance + policy` の読み方が可能になった。

## Interpretation

このケースから言えるのは、`RETURN` では provenance を少なくとも 2 系統に分ける必要があるということだ。

1. `literal_*`
   - return 自体が明示的な literal
2. `input_link_var`
   - return 対象は upstream value だが、構造依存ノードとは別に semantic source を保持する必要がある

前者は `explicit`、後者は `history_based` として provenance-strength policy matrix に自然に対応付く。

## Current Conclusion

現時点では、`RETURN` の provenance path は次の範囲で安定している。

- `literal_boolean`
- `literal_null`
- `literal_numeric`
- `quoted_literal`
- `source_var`
- `input_link_var`

特に `input_link_var` により、branch 内の `RETURN` が構造親 `CONDITION` に引きずられず、
semantic upstream source を別 metadata で保持できるようになったことが重要である。

## Remaining Gap

まだ弱いのは、`input_link_var` にも `source_var` にもならない自由文の return である。

その場合は現状、

- typed latest-var fallback
- または TODO 停止

に留まる。

したがって次段の論点は、
return-side provenance supply をどこまで deterministic に広げるかである。
