# Review Adoption Notes

## Purpose

この文書は、外部レビュー `review_ag.md` の提案について、現状研究との整合性を判定し、採用可否を明示するためのものである。

ここでは、単に「良さそうな提案」を並べるのではなく、すでに実施済みの事項、未着手だが妥当な事項、現時点では順序が合わない事項を分けて扱う。

## Adoption Summary

### 1. Dependency Loss の局所分析

- 判定: `採用`
- 理由:
  - 研究の初期定義には `refs`, `input_link`, `source_ref`, `source_kind` が含まれているが、実際の深掘りは role drift に偏っていた
  - `spec_role` が保持されても依存が切れていれば生成結果は壊れるため、独立論点として掘る価値が高い
- 取り込み方:
  - `intent_drift_analysis.md` と並ぶ粒度で `dependency_loss_analysis.md` を作る
  - 主対象は `refs`, `input_link`, `source_ref`, `source_kind`, `children/else_children` を介した接続

### 2. 自動チェーン挿入の妥当性評価

- 判定: `採用`
- 理由:
  - `Over-Inference` はすでに失敗類型として定義済みだが、JSON 自動チェーンを明示仕様ケースと並べて比較するベンチマークは未整備
  - 手書き仕様の `DESERIALIZE` と自動挿入 `DESERIALIZE` を同列に扱うと、`spec_role` の意味境界が曖昧になる
- 取り込み方:
  - 明示 `JSON_DESERIALIZE` ケースと、HTTP/FILE fetch 後の暗黙チェーンケースを対にした比較ケースを後段追加する
  - 研究上の論点は「自動補助ノードに `spec_role` を付けるべきか」ではなく、「付けるならどの条件で許されるか」を固定すること

### 3. LOOP / WRAPPER の構造境界保持

- 判定: `採用`
- 理由:
  - `CHECK` の PoC で条件ノードは改善したが、親 loop が `FETCH/FETCH` に圧縮される問題が残っている
  - これは role 問題だけでなく、構造ノード固有の意味保持問題である
- 取り込み方:
  - `LOOP`, `WRAPPER` について、内部ノードが平坦化されていないか、親子関係が壊れていないかを評価基準で明示する
  - `ITERATE` / `WRAP` は action の一種ではなく、スコープ構造を作るノードとして扱う

### 4. CHECK における否定の扱い

- 判定: `部分採用`
- 理由:
  - `null_check` の `expected_truth=false` から `user == null` を生成する経路はすでに PoC 実装とテストで確認済み
  - ただし、`not exists`, `not null`, `negative comparison` を横断した比較ケースはまだない
- 取り込み方:
  - 新規研究課題としては「否定の正規化」を追加する
  - 実装変更の前に、`expected_truth=false` が二重否定へ崩れないことを補助ケースで確認する

## Not Adopted As-Is

### `CHECK` だけを対象にした PoC を次に進めるべきという提案

- 判定: `不採用`
- 理由:
  - この提案自体は妥当だったが、現状ではすでに完了済みである
  - `IRGenerator` への `check_kind` 追加、downstream 条件生成での消費、補助 3 ケースでの観測まで実施済み

したがって、これは次アクションではなく「完了済みの妥当な方針だった」と整理する。

## Updated Priority

レビュー提案を取り込んだ後の研究優先順は次の通りである。

1. `dependency_loss_analysis.md` を追加し、依存エッジ損失を独立分析する
2. `ITERATE` / `WRAP` の構造境界評価を強化する
3. 明示チェーン vs 自動チェーンの比較ケースを追加する
4. 否定系 `CHECK` の補助ケースを追加する

## Immediate Next Step

このレビューを反映して次にやるべき最小作業は、`Dependency Loss` を role 論点から分離して研究文書化することである。
