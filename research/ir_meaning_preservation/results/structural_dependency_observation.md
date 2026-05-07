# Structural Dependency Observation

## Scope

この文書は、`structural_dependency_rule.md` の検証用に追加した 3 ケースについて、`Observed IR` の初回観測結果を要約するためのものである。

対象:

- `case_09_condition_branch_dependency`
- `case_10_loop_body_dependency`
- `case_11_wrapper_scope_dependency`

## Summary

### Case 09: Condition Branch Dependency

- then 側 first-child: `input_link = step_1`
- then 側 second sibling: `input_link = step_2`
- else 側 first-child: `input_link = step_1`

Reading:

- `CONDITION` の branch base 修正は期待どおり効いている
- `structural_parent_dependency` と `sequential_sibling_dependency` の切替は、このケースでは成立している
- ただし `target_entity`, `source_kind`, `source_ref`, `check_subject` は期待より弱い

### Case 10: Loop Body Dependency

- loop body first-child: `input_link = step_2`
- loop body second sibling: `input_link = step_3`
- nested condition child first-child: `input_link = step_5`

Reading:

- first-child の親依存は成立している
- second sibling の sibling 依存も成立している
- nested condition child の親依存も成立している
- `DISPLAY` に対する collection 優先 input-link 規則より、block 内 sibling 規則を優先することで改善した
- 一方で `CALC` と loop 自体の role はまだ弱いままである

### Case 11: Wrapper Scope Dependency

- wrapper first-child: `input_link = step_1`
- wrapper second sibling: `input_link = step_2`
- nested loop child first-child: `input_link = step_4`

Reading:

- wrapper first-child の親依存は成立している
- wrapper second sibling の sibling 依存も成立している
- nested loop child first-child の親依存も成立している
- wrapper ノード自体も `spec_role=WRAP` を保持できる
- loop ノードも `intent=GENERAL`, `role=ITERATE` へ改善した
- 構造 dependency に加えて、構造 role の保持も一部進んだ

## Initial Conclusion

初回観測から言えるのは次の通りである。

1. `first-child -> structural parent` 規則は `CONDITION`, `LOOP`, `WRAPPER` のいずれでも概ね成立した
2. `second sibling -> previous sibling` 規則も、構造ブロック内部では成立させられることを確認した
3. nested child についても、内側構造親への依存は維持できている

したがって、`structural_dependency_rule` は依存規則としてかなり成立している。

一方で、なお残っているのは

- `CALCULATE` の弱化
- `target_entity` や source 情報の弱さ
- wrapper consumer 未整備

であり、主課題は dependency 規則そのものより role / under-spec 側へ移っている。

## Next Target

次に直すべきなのは、構造 dependency が改善した後に残る `CALCULATE` の role 保持と wrapper 消費設計である。

最初の対象としては、`価格を計算する` のようなケースで `spec_role=CALCULATE` が弱化する発生点を追うのが妥当である。
