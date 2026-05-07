# Dependency Loss Analysis

## 1. Purpose

この文書は、`IR meaning preservation` 研究における `Dependency Loss` を、role drift とは独立した論点として局所分析するためのものである。

ここでいう `Dependency Loss` は、単に `input_link` が `null` になる場合だけを指さない。仕様上あるはずのデータフローが、

1. 断線する
2. 誤ったノードへ接続される
3. ノード圧縮により追跡不能になる

このいずれかの形で失われることを含む。

## 2. Why Separate This From Role Analysis

`spec_role` が保持されても、依存エッジが壊れていれば downstream の生成結果は正しくならない。

たとえば `CHECK` が `CHECK` として保持されても、

- false 分岐が then 側の出力へぶら下がる
- `DESERIALIZE` が `FETCH` に吸収されて前段出力が見えない
- `PERSIST` がどの集合を保存しているか追えない

という状態では、意味保存は不十分である。

したがって、`Dependency Loss` は `Intent Drift` の副作用ではなく、独立の主要観点として扱うべきである。

## 3. Evaluation Focus

この論点では、ノード単体よりも次のエッジ情報を中心に観察する。

- `input_link`
- `children` / `else_children` を介した親子接続
- `source_ref`
- `source_kind`
- 前段出力を継承しているはずの `target_entity` / `cardinality`

特に構造ノードでは、「そのノードが存在するか」よりも「期待した下流ノードを正しく支配しているか」を優先して見る。

## 4. Dependency Loss Shapes

### 4.1 Edge Break

期待される前段依存が消え、ノードが独立ステップのように見える型。

例:

- `input_link` が `null`
- source を継承すべきノードで `source_ref/source_kind` が空になる

### 4.2 Edge Misbinding

依存自体は残るが、誤ったノードへ接続される型。

例:

- `else` 側ノードが条件ノードではなく `then` 側ノードへ接続される
- loop body が loop 親ではなく前段 fetch へ接続される

### 4.3 Compression-Induced Loss

複数段の意味連鎖が 1 ノードへ圧縮され、前段と後段の境界が見えなくなる型。

例:

- `FETCH -> DESERIALIZE` が単一 `FETCH` ノードに圧縮される
- その結果、どこで source が消え、どこで collection 化したか追えない

### 4.4 Boundary Drift

source / cardinality / entity の継承境界が曖昧になり、依存は残っていても意味上の接続が弱くなる型。

例:

- `HTTP_REQUEST -> JSON_DESERIALIZE -> PERSIST` の直列は保たれているが、`PERSIST.cardinality` が `SINGLE` になり、集合依存が薄れる
- `DESERIALIZE` 後の `target_entity` が `Item` に戻り、前段の型意味を引き継げない

## 5. Case Analysis

### 5.1 Case 04: RobustConfigLoader

最も明確な `Dependency Loss` が出ているケースである。

期待:

- `step_5` は `else_children` 側に属しつつ、条件ノード `step_1` の判定結果に依存する

観測:

- `step_5.input_link = step_3`

読み取り:

- これは `Edge Misbinding` である
- `else` 側メッセージ表示が、条件判定ではなく `then` 側表示の出力へ結び付いている
- 分岐構造自体は残っていても、分岐依存の意味が壊れている

このケースは、`Dependency Loss` が少数でも重く扱うべき理由を最もよく示している。

### 5.2 Case 03: BatchProcessProducts

期待:

- `step_1_fetch -> step_1_deserialize -> step_2(loop)` という 2 段依存

観測:

- 前段が単一 `step_1` に圧縮される
- `step_2.input_link = step_1` はあるが、そこが fetch 結果なのか deserialized collection なのかが追えない

読み取り:

- これは `Compression-Induced Loss` である
- 明示的な断線ではないが、依存境界が不可視化されている
- source 情報と collection 化の境界が同時に失われるため、構造ノード `LOOP` が何を反復しているかの説明力が弱まる

### 5.3 Case 05: SyncExternalData

期待:

- `HTTP_REQUEST -> JSON_DESERIALIZE -> PERSIST` が、source と collection 性を保ったまま直列接続される

観測:

- `input_link` 連鎖自体は保たれている
- ただし `PERSIST.cardinality = SINGLE`
- `RETURN` は最終結果として独立しており、保存結果との関係が IR 上では薄い

読み取り:

- これは主に `Boundary Drift` である
- 依存エッジ自体は切れていないが、前段が collection であることが保存ノードに十分伝わっていない
- `RETURN` の意味も success flag としての依存が弱く、後段条件や verifier で読み取りにくい

### 5.4 Case 02: ComplexLinqSearch

期待:

- file source の fetch から deserialization / LINQ filter / display まで依存連鎖が続く

観測:

- 直列 `input_link` は概ね保たれている
- `source_ref=users.json` が前段で落ちる

読み取り:

- これは軽度の `Edge Break` に近い
- ノード列自体はつながっているが、source anchor が落ちることで、「何の入力に基づく filter か」が弱くなる
- 完全な `Dependency Loss` の主事例ではないが、source 基点の断線として観測価値がある

## 6. Cross-Case Interpretation

現時点の `Dependency Loss` は、すべてが `input_link` 消失という単純な形ではない。

むしろ再現しているのは次の 3 つである。

1. 構造ノードを跨ぐ誤接続
2. 前段圧縮により依存境界が見えなくなること
3. source / cardinality / entity の継承が弱くなること

この意味で、`Dependency Loss` は「エッジがあるかないか」ではなく、「依存が説明可能な形で保持されているか」の問題と読むべきである。

## 7. Relation To Other Failure Types

### 7.1 vs Intent Drift

- `Intent Drift` は役割分類の問題
- `Dependency Loss` は接続関係の問題

両者は併発しうるが、片方を直してももう片方は残りうる。

### 7.2 vs Under-Spec Capture

- `Under-Spec Capture` は仕様粒度が潰れる問題
- `Compression-Induced Loss` はその結果として依存境界も見えなくなる問題

したがって、圧縮ケースでは 2 類型が重なるが、分析目的上は役割粒度と依存不可視化を分けて記述すべきである。

### 7.3 vs Source Drift

- `Source Drift` は source 属性そのものの誤り
- `Dependency Loss` は source が前段依存の基点として機能しなくなる問題

`source_ref` が落ちるケースは両者の境界に位置するため、今後は「属性誤り」と「依存基点断線」を別メモで見分ける必要がある。

## 8. Working Implications

この分析から、次の作業優先順が導かれる。

1. `CONDITION`, `LOOP`, `WRAPPER` のような構造ノードを跨ぐ接続規律を強める
2. `FETCH -> DESERIALIZE` のような前段圧縮で依存境界を失わない表現を検討する
3. `cardinality`, `target_entity`, `source_ref` を依存継承メタとして読む観点を downstream に追加する

特に `CHECK` の PoC 後は、role そのものよりも「構造親と前段出力のどちらに依存しているか」を明示的に見る段階に入っている。

## 9. Next Step

この文書の次にやるべきことは、`Dependency Loss` を実際に再現しやすいケースを 1 つ選び、`IRGenerator` のどの接続規則で misbinding または compression が起きるかを実装レベルで追跡することである。

最初の対象としては、`RobustConfigLoader` の `else_children.input_link` 誤接続が最も適している。
