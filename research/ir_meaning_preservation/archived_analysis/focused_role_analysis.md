# Focused Role Analysis: DESERIALIZE / FILTER / CHECK

## 1. Purpose

この文書は、優先 5 ケースの中でも特に drift が目立った `DESERIALIZE`, `FILTER`, `CHECK` の 3 役割に絞って、どこで失われるのかを局所的に分析するためのものである。

ここでの目的は改善案の実装ではなく、失われ方の型を固定し、次段の設計変更を議論できるようにすることである。

## 2. Why These Three Roles

`role_mapping_matrix.md` の結果から、次の性質が見えている。

- `DESERIALIZE`
  - `ACTION` または `FETCH` に吸収されやすい
- `FILTER`
  - `ACTION` に圧縮されやすい
- `CHECK`
  - `ACTION` に圧縮されやすい

この 3 つは、いずれも仕様上は独立した意味役割を持つが、現行の `runtime_role` では十分に分離されていない。

## 3. DESERIALIZE

### 3.1 Observed Cases

- `ComplexLinqSearch`
  - 期待 `spec_role`: `DESERIALIZE`
  - 観測 `runtime_role`: `ACTION`
- `SyncExternalData`
  - 期待 `spec_role`: `DESERIALIZE`
  - 観測 `runtime_role`: `ACTION`
- `BatchProcessProducts`
  - 期待 `spec_role`: `DESERIALIZE`
  - 観測 `runtime_role`: `FETCH` に吸収

### 3.2 Code-Level Clues

`src/ir_generator/ir_generator.py` では、`JSON_DESERIALIZE` は intent としては立つが、初期 role は独立 role として明示されにくい。

観測できる点:

- `analysis["role"]` は `ACTION` のまま残りやすい
- 自動チェーン挿入では `json_node["role"] = "TRANSFORM"` が設定される
- つまり、手書き設計由来の `JSON_DESERIALIZE` と、自動チェーン由来の `JSON_DESERIALIZE` で role 扱いが一致しない

### 3.3 Failure Shape

`DESERIALIZE` は、次の 2 パターンで失われる。

1. ノードは存在するが role が `ACTION` に弱化する
2. 前段 `FETCH` と同一ノードに圧縮され、独立役割として立たない

### 3.4 Interpretation

この役割が失われる理由は、現行実装が `JSON_DESERIALIZE` を「仕様意味 role」ではなく、「補助的な変換 intent」程度にしか扱っていないためと考えられる。

## 4. FILTER

### 4.1 Observed Cases

- `ComplexLinqSearch`
  - `step_3`, `step_4`
  - 期待 `spec_role`: `FILTER`
  - 観測 `runtime_role`: `ACTION`

### 4.2 Code-Level Clues

`_infer_intent_role_cardinality` では、変換系の語彙に対して `intent = "LINQ"`, `role = "TRANSFORM"` を返す経路がある。

一方で、`_analyze_step_integrated` では、`intent == "GENERAL" and logic_goals` の場合にのみ `role = "FILTER"` を付ける分岐がある。

つまり、`FILTER` が立つためにはかなり限定的な条件が必要で、明示 intent が `LINQ` のケースでは `FILTER` role に上がらない可能性が高い。

### 4.3 Failure Shape

`FILTER` は次の順で失われている可能性が高い。

1. 初期解析で `LINQ` intent は立つ
2. しかし role は `FILTER` ではなく `ACTION` または `TRANSFORM` 系に寄る
3. 後段補正では `LINQ` role を再構成しない

### 4.4 Interpretation

現行設計では、`LINQ` は intent として扱われても、「絞り込み」という仕様意味 role は独立して保持されていない。

その結果、`FILTER` と `TRANSFORM` が runtime 側で十分に区別されない。

## 5. CHECK

### 5.1 Observed Cases

- `RobustConfigLoader`
  - 条件ノード
  - 期待 `spec_role`: `CHECK`
  - 観測 `runtime_role`: `ACTION`

### 5.2 Code-Level Clues

`_infer_intent_role_cardinality` には、存在確認語彙に対して `intent = "EXISTS"`, `role = "CHECK"` を返す経路がある。

しかし観測では、`step_1` は初期段階から `EXISTS / ACTION` になっていた。

これは少なくとも次のどちらかを示している。

1. このケースでは `_infer_intent_role_cardinality` の `CHECK` 経路に入っていない
2. あるいは、その後の初期 role 決定で `ACTION` に戻されている

### 5.3 Failure Shape

`CHECK` は、条件ノードであるにもかかわらず次のように失われる。

1. `CONDITION` 構造自体は保持される
2. しかし role は `CHECK` にならず、一般的な `ACTION` に留まる
3. 後段でも `EXISTS -> CHECK` の補正が存在しない

### 5.4 Interpretation

現行実装は、条件構造の存在は表現できるが、「何を条件として判定しているか」という仕様意味 role を十分に保持していない。

つまり `CHECK` の問題は、構造 loss ではなく意味 role loss である。

## 6. Common Failure Pattern Across the Three Roles

`DESERIALIZE`, `FILTER`, `CHECK` に共通するのは、以下である。

1. 仕様上は独立役割である
2. 実装上は生成都合で一般 role に寄りやすい
3. 後段補正の対象外になりやすい
4. その結果、`ACTION` または近縁の粗い runtime role に圧縮される

## 7. Stronger Working Hypothesis

現行実装の role 補正体系は、`FETCH`, `DISPLAY`, `PERSIST` のような後段コード生成で直接効く役割を優先しており、`DESERIALIZE`, `FILTER`, `CHECK` のような仕様理解上重要だが生成上は補助的に見える役割を保存していない。

したがって、これら 3 役割の drift は偶然ではなく、体系的な設計結果とみなすべきである。

## 8. Next Research Step

ここまで観測したうえで次に進むなら、論理的には以下のどちらかになる。

1. `spec_role` を明示的に IR へ保持する最小設計変更案をまとめる
2. `DESERIALIZE`, `FILTER`, `CHECK` の 3 役割に対して、現行ロジックのどの分岐が role を弱化しているかをコードコメント付きでさらに局所追跡する

研究の流れとしては、次は 1 のほうが収まりがよい。
