# CHECK Case Observation

## Scope

この文書は、補助 3 ケースについて `Observed IR` と生成された条件式を対で記録するためのものである。

対象:

- `case_06_check_exists_file`
- `case_07_check_null_guard`
- `case_08_check_numeric_comparison`

## Summary

### Case 06: exists_check

- Observed IR: `check_kind=exists_check` を保持できた
- Generated condition: `File.Exists("config.json")`
- Reading:
  - このケースでは `CHECK` の保存と消費がほぼ一致している
  - ただし `target_entity` は依然として `Item` に寄っている

### Case 07: null_check

- Observed IR: `check_kind=null_check` は保持された
- Generated condition: `user == null`
- Reading:
  - `null_check` 自体は downstream まで届いている
  - `check_subject=user` まで保持できるようになった
  - 条件ノード自体も `intent=EXISTS`, `role=CHECK`, `target_entity=User` に改善した

### Case 08: comparison_check

- Observed IR: `check_kind=comparison_check`, `check_operator=>`, `check_value=100` は保持された
- Generated condition: `x.Points > 100`
- Reading:
  - 比較意味そのものは保持されている
  - 条件ノードの `intent=EXISTS`, `role=CHECK` も期待形へ寄った
  - `target_entity=Item` のままでも、property 逆引きにより loop 変数つき条件へ具体化できた
  - 親 loop ノード自体はまだ `intent=FETCH`, `role=FETCH` に寄っており、`ITERATE` の runtime 側整合は未解決
  - 依然として IR 上の entity 解決は弱いが、downstream 条件生成は改善した

## Initial Conclusion

補助 3 ケースの結果から、`CHECK` については次の段階まで進んだといえる。

1. `spec_role=CHECK` の保持
2. `check_kind` の保持
3. `check_kind` に応じた条件式生成

一方で、まだ弱い点も明確である。

- 条件ノードの `target_entity` が `Item` に寄る問題
- `comparison_check` の `target_entity` が `Item` に寄る問題
- loop ノードの `ITERATE` 意味が runtime 側で `FETCH` に圧縮される問題

## Next Implementation Target

次に直すべきなのは、`CHECK` 自体ではなく「条件ノードと親構造の intent/entity 整合性」である。

優先順は次の通り。

1. `comparison_check` 条件ノードの `target_entity` を `Item` から脱却させる
2. loop ノードの `spec_role=ITERATE` に対応する runtime 側 role/intention を整合させる
3. 条件ノード子孫の `target_entity` 連鎖を強める
4. 補助ケースを実シナリオへ戻したときも同じ改善が出るか確認する
