# Failure Taxonomy Mapping

## 1. Purpose

この文書は、優先 5 ケースで観測された差分を、`evaluation.md` で定義した失敗類型へ正式に対応付けるためのものである。

ここでは改善案は扱わず、まず「何がどの種類の失敗か」を固定する。

## 2. Mapping Policy

- `Primary` は、そのケースで最も本質的な差分を表す
- `Secondary` は、補助的だが再現性のある差分を表す
- 1 ケースに複数の差分があっても、列挙の中心は研究上の主要失敗に置く

## 3. Case Mapping

| Case | Primary | Secondary | Rationale |
|---|---|---|---|
| Case 01 `StdinToStdoutTransform` | `Intent Drift` | `Under-Spec Capture` | 直列構造は保持されているが、`TRANSFORM.role` が `ACTION` に弱化し、`DISPLAY.output_type` も期待より弱い。 |
| Case 02 `ComplexLinqSearch` | `Source Drift` | `Intent Drift` | 依存連鎖は保たれている一方、`users.json` の `source_ref` が落ち、`LINQ.role` が `FILTER` にならない。 |
| Case 03 `BatchProcessProducts` | `Under-Spec Capture` | `Source Drift` | 仕様上は `FETCH + JSON_DESERIALIZE` を分けたいが、実 IR は 1 ノードに圧縮して前段意味を十分に捉えていない。source 情報も落ちている。 |
| Case 04 `RobustConfigLoader` | `Dependency Loss` | `Intent Drift` | `else` 側の `input_link` が条件ノードではなく `step_3` に接続され、分岐依存の意味が崩れている。あわせて `CHECK` が `ACTION` に弱化している。 |
| Case 05 `SyncExternalData` | `Intent Drift` | `Under-Spec Capture` | 直列構造は保持されるが、`HTTP_REQUEST.role=READ`、`PERSIST.cardinality=SINGLE` など、処理役割と集合性の表現が弱い。 |

## 4. Cross-Case Aggregation

初回 5 ケースで確認できた失敗類型の出現状況は以下の通りである。

### Frequently Observed

- `Intent Drift`
  - 5 ケース中 4 ケースで主または副次的に観測
  - 特に `role` の弱化として現れる

- `Under-Spec Capture`
  - 5 ケース中 3 ケースで観測
  - 仕様で区別したい意味粒度を IR が潰す形で現れる

### Moderately Observed

- `Source Drift`
  - 5 ケース中 2 ケースで観測
  - file source や source_ref の欠落が中心

- `Dependency Loss`
  - 5 ケース中 1 ケースで観測
  - ただし `RobustConfigLoader` のように分岐で出ると意味損失は大きい

### Not Yet Primary in This Set

- `Structure Loss`
  - 今回の 5 ケースでは主失敗としては未観測
  - `LOOP` や `CONDITION` 自体は保持できている

- `Over-Inference`
  - 今回の 5 ケースでは明確には未観測
  - 初期セットでは過補完より弱表現のほうが目立つ

## 5. Interpretation

初回観測から言えるのは、現行 IR 生成器は「大枠の構造を壊す」よりも、「意味役割を弱く表現する」「仕様で分けた粒度を潰す」方向の失敗が多いということである。

これは研究上かなり重要で、少なくとも現段階の主要課題は `Structure Loss` ではなく、以下の 3 点にある。

1. `Intent Drift`
2. `Under-Spec Capture`
3. `Source Drift`

`Dependency Loss` は件数は少ないが、分岐や条件付き処理では影響が大きいため、重みは高く扱うべきである。

## 6. Phase-1 Status Against Exit Criteria

`evaluation.md` の第 1 段階完了条件に照らすと、以下までは満たせている。

- ベンチマークケースの確定
- 期待 IR の作成
- 実 IR の採取
- ケース単位の失敗類型の分類
- 改善前基準線の言語化

したがって、少なくとも優先 5 ケースについては、改善前分析フェーズの最低条件を満たしたとみなせる。
