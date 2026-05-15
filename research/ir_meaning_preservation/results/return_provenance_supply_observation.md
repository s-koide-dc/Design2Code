# Return Provenance Supply Observation

## Scope

この文書は、`return_provenance_supply_model.md` に従って
`RETURN` provenance supply の有無が observed IR にどう現れるかを比較する初回観測結果である。

対象:

- `case_33_return_input_link_supply`
- `case_34_return_weak_retention`

## Summary

### Case 33: Input-Link Supply

- Observed IR:
  - `step_2` は `RETURN`
- Preserved metadata:
  - `return_source_node_id=step_1`
  - `return_value_resolution=input_link_var`

Reading:

- non-literal `RETURN` でも upstream dependency が明示されていれば、supply success として provenance を付けてよい
- ここでの supply source は lexical hint ではなく structural `input_link` である

### Case 34: Weak Retention

- Observed IR:
  - `step_1` は `RETURN`
- Preserved metadata:
  - `spec_role=RETURN`
  - `return_value_resolution` なし
  - `return_source_node_id` なし

Reading:

- `RETURN` intent 自体は保持される
- しかし source provenance は deterministic に supply されない
- したがって lexical surface だけから返却 source を発明していない

## Cross-Case Interpretation

この contrast から、次のことが明確になった。

1. `RETURN` provenance も `supply success` と `weak retention` に分けて観測できる
2. `input_link_var` は free-text 推定ではなく structural dependency に依存する deterministic supply である
3. source を十分に説明できない step は `RETURN` に上がっても provenance なしで止めるべきである

## Immediate Conclusion

したがって、`RETURN` の残課題は runtime fallback の改善そのものではなく、
`input_link` も literal も無い自由文 return をどこまで deterministic に supply できるかの境界である。

研究の流れとしては、次に必要なのは keyword 追加ではなく、
return-side supply を許可する構造条件をさらに形式化できるかの検討である。
