# Intent Drift Analysis

## 1. Purpose

この文書は、`IR meaning preservation` 研究において最優先論点となった `Intent Drift` を個別に分析するためのものである。

ここでいう `Intent Drift` は、IR ノードの存在自体は維持されているにもかかわらず、仕様上期待した intent や role が、より弱い表現または別種の表現へ変質する現象を指す。

## 2. Why This Is the Primary Issue

初回 5 ケースの比較では、`Intent Drift` は 5 ケース中 4 ケースで主または副次的に観測された。

特に以下の形で再現している。

- `TRANSFORM` が `ACTION` に弱化する
- `FILTER` が `ACTION` に弱化する
- `CHECK` が `ACTION` に弱化する
- `HTTP_REQUEST` の role が `FETCH` ではなく `READ` に寄る
- `PERSIST` の集合性が弱くなり、結果として処理役割の解釈も弱くなる

この傾向は、IR 生成器が構造を壊す前に、意味役割の粒度を落としていることを示す。

## 3. Observed Symptoms by Case

### Case 01: StdinToStdoutTransform

- 期待: `TRANSFORM.role = TRANSFORM`
- 実際: `TRANSFORM.role = ACTION`

### Case 02: ComplexLinqSearch

- 期待: `LINQ.role = FILTER`
- 実際: `LINQ.role = ACTION`

### Case 04: RobustConfigLoader

- 期待: `CONDITION.role = CHECK`
- 実際: `CONDITION.role = ACTION`

### Case 05: SyncExternalData

- 期待: `HTTP_REQUEST.role = FETCH`
- 実際: `HTTP_REQUEST.role = READ`
- 期待: `PERSIST` が集合保存として明示される
- 実際: `PERSIST.cardinality = SINGLE`

## 4. Suspected Hotspots in Implementation

初回調査では、`src/ir_generator/ir_generator.py` の以下が主要候補である。

### 4.1 `_analyze_step_integrated`

この関数は、初期の intent, role, cardinality を決めている。

重要箇所:

- `meta.get("role", "ACTION")` による role 初期化
- `FETCH -> READ`, `PERSIST -> WRITE`, `HTTP_REQUEST -> READ` の変換
- `logic_goals` に基づく `GENERAL -> LINQ` 変換
- `DISPLAY` に対する `output_type = "string"` の付与

研究上の論点は、「ここで付けた role が、仕様上の意味役割なのか、それともコード生成寄りの実装役割なのか」である。

### 4.2 `generate()` 内の `final_intent` 再解釈

この段階では、初期解析の結果に対して後から intent/role の補正が入る。

重要箇所:

- `GENERAL`, `HTTP_REQUEST`, `FILTER` などから `LINQ` へ寄せる処理
- `sql` や `url` の有無による intent 上書き
- `PERSIST`, `FETCH`, `DISPLAY`, `HTTP_REQUEST` に対する role の再設定

研究上の論点は、「intent を確定した後の role 補正が、仕様の意味保存よりも合成都合を優先していないか」である。

### 4.3 `PERSIST` 周辺の cardinality 補正

`PERSIST` に対して scalar 入力や serialization を前提とした補正が後段で入る。

この影響で、仕様上は集合処理として見たいケースでも、IR 上は `SINGLE` 扱いに寄る可能性がある。

これは単なる cardinality の問題ではなく、保存処理の役割解釈にも影響するため、`Intent Drift` と `Under-Spec Capture` の境界に位置する。

## 5. Working Hypotheses

### Hypothesis 1

`role` が仕様意味ではなく、コード生成に都合のよい抽象役割へ寄せられている。

例:

- `TRANSFORM -> ACTION`
- `FILTER -> ACTION`
- `CHECK -> ACTION`

### Hypothesis 2

intent は比較的保持されるが、role の再設定ロジックが一貫していないため、IR の意味粒度が落ちている。

これは「intent は合っているのに role が弱い」ケースが複数あることと整合する。

### Hypothesis 3

`HTTP_REQUEST`, `FETCH`, `READ` のように、仕様意味と実装操作意味が混在している。

研究上は、これらを同じ層で扱うと drift が見えにくくなる。

### Hypothesis 4

後段の chaining / serialization / persistence 補正が、前段で決めた意味役割を侵食している。

特に `PERSIST` の集合性が弱くなるケースは、この仮説と整合する。

## 6. Research Questions

次に詰めるべき問いは以下である。

1. `intent` と `role` は同じ抽象層にあるべきか
2. `role` は仕様意味を表すべきか、生成都合を表すべきか
3. `FETCH/READ`, `PERSIST/WRITE`, `LINQ/FILTER/TRANSFORM` をどう分離するべきか
4. 後段補正は `intent` と `role` のどちらまで変更してよいか

## 7. Immediate Next Checks

次の確認は、改善実装ではなく局所観察に絞る。

1. `_analyze_step_integrated` の出力と `generate()` 最終出力を、同一ケースで並べて比較する
2. `role` が変わるケースだけを抽出し、変更前後を一覧化する
3. `HTTP_REQUEST`, `LINQ`, `DISPLAY`, `PERSIST`, `CONDITION` を対象に、role 再設定規則を表にする
4. `Intent Drift` が発生しても code synthesis 側で補償されているかは別問題として切り分ける

## 8. Current Position

現時点では、`Intent Drift` は単なる誤分類ではなく、IR が「仕様意味の表現」なのか「生成処理の中間表現」なのかが混線していることの症状と考えるのが妥当である。

したがって次段は、精度改善のための小手先のルール追加ではなく、`intent` と `role` の責務分離を観察可能な形で整理する作業になる。
