# Intent Drift Trace

## 1. Purpose

この文書は、`Intent Drift` が実際にどの段階で発生しているかを観測した結果をまとめたものである。

比較対象は、同一ステップに対する以下の 2 点である。

1. `IRGenerator._analyze_step_integrated` の初期解析結果
2. `IRGenerator.generate()` の最終 IR ノード

## 2. Main Observation

初回観測では、`Intent Drift` は主に次の 2 段で発生している。

### 2.1 Early Weakening in `_analyze_step_integrated`

多くのケースで、仕様上期待した role は、この段階ですでに弱い。

代表例:

- `TRANSFORM -> ACTION`
- `DISPLAY -> ACTION`
- `LINQ -> ACTION`
- `HTTP_REQUEST -> READ`
- `PERSIST -> WRITE`

つまり、`generate()` の後段で role が壊れるというより、初期解析がすでに「仕様意味」ではなく「実装寄りの操作意味」を返している。

### 2.2 Partial Repair in `generate()`

後段の `generate()` では、一部の role は補正される。

代表例:

- `FETCH: READ -> FETCH`
- `DISPLAY: ACTION -> DISPLAY`
- `PERSIST: WRITE -> PERSIST`

一方で、以下は補正されない、または別方向に寄る。

- `TRANSFORM: ACTION -> ACTION`
- `LINQ: ACTION -> ACTION`
- `HTTP_REQUEST: READ -> READ`
- `EXISTS/CHECK` 系: 条件ノードで `ACTION` のまま残ることがある

したがって、現在の処理は「初期段階で弱い role を作り、一部だけ後から修正する」構造になっている。

## 3. Trace by Case

### Case 01: StdinToStdoutTransform

| Step | Initial Intent/Role | Final Intent/Role | Observation |
|---|---|---|---|
| step_1 | `FETCH / READ` | `FETCH / FETCH` | 後段で補正される |
| step_2 | `TRANSFORM / ACTION` | `TRANSFORM / ACTION` | drift が初期段階から固定される |
| step_3 | `DISPLAY / ACTION` | `DISPLAY / DISPLAY` | 後段で補正される |

要点:

- `TRANSFORM` の role 弱化は `_analyze_step_integrated` 時点で起きている
- `DISPLAY` は初期段階では弱いが後で補正される

### Case 02: ComplexLinqSearch

| Step | Initial Intent/Role | Final Intent/Role | Observation |
|---|---|---|---|
| step_1 | `FETCH / READ` | `FETCH / FETCH` | 後段で補正される |
| step_2 | `JSON_DESERIALIZE / ACTION` | `JSON_DESERIALIZE / ACTION` | role が弱いまま残る |
| step_3 | `LINQ / ACTION` | `LINQ / ACTION` | drift が固定される |
| step_4 | `LINQ / ACTION` | `LINQ / ACTION` | drift が固定される |
| step_5 | `DISPLAY / ACTION` | `DISPLAY / DISPLAY` | 後段で補正される |

要点:

- `LINQ` の role 弱化は初期段階で確定し、その後も直らない
- `FETCH` と `DISPLAY` だけが後段補正の恩恵を受ける

### Case 04: RobustConfigLoader

| Step | Initial Intent/Role | Final Intent/Role | Observation |
|---|---|---|---|
| step_1 | `EXISTS / ACTION` | `EXISTS / ACTION` | `CHECK` に上がらず固定される |
| step_2 | `FETCH / READ` | `FETCH / FETCH` | 後段で補正される |
| step_3 | `DISPLAY / ACTION` | `DISPLAY / DISPLAY` | 後段で補正される |
| step_5 | `DISPLAY / ACTION` | `DISPLAY / DISPLAY` | 後段で補正される |

要点:

- `CONDITION` 系の role は初期段階ですでに弱い
- `EXISTS -> CHECK` という仕様意味への補正が後段に存在しない

### Case 05: SyncExternalData

| Step | Initial Intent/Role | Final Intent/Role | Observation |
|---|---|---|---|
| step_1 | `HTTP_REQUEST / READ` | `HTTP_REQUEST / READ` | 初期段階から最終段まで同じ |
| step_2 | `JSON_DESERIALIZE / ACTION` | `JSON_DESERIALIZE / ACTION` | role 弱化が固定される |
| step_3 | `PERSIST / WRITE` | `PERSIST / PERSIST` | 後段で補正される |
| step_4 | `RETURN / ACTION` | `RETURN / ACTION` | role は変化しない |

要点:

- `HTTP_REQUEST` は `FETCH` 的に扱いたくても、現実装では `READ` に固定される
- `PERSIST` は role 自体は補正されるが、cardinality は別途弱化する

## 4. What This Means

今回の観測から、`Intent Drift` は単一の後段バグではない。むしろ以下の二層問題として整理すべきである。

### 4.1 Semantic Role Design Problem

`_analyze_step_integrated` が返している role は、仕様意味というより実装操作に近い。

そのため、研究上期待した以下のような role が、最初から十分に区別されない。

- `TRANSFORM`
- `FILTER`
- `CHECK`
- `FETCH` としての `HTTP_REQUEST`

### 4.2 Inconsistent Repair Problem

後段では role 補正が部分的にしか行われない。

補正されるもの:

- `FETCH`
- `DISPLAY`
- `PERSIST`

補正されないもの:

- `TRANSFORM`
- `LINQ`
- `JSON_DESERIALIZE`
- `HTTP_REQUEST`
- `EXISTS`

結果として、role の体系が一貫しない。

## 5. Stronger Hypotheses After Trace

### Hypothesis A

現行実装では、`role` が単一概念として使われているが、実際には少なくとも 2 種類ある。

1. 仕様意味 role
2. 実装操作 role

この 2 つが分離されていないため drift が発生している。

### Hypothesis B

`generate()` の後段補正は、コード生成に必要な一部 intent だけを対象にしており、IR 研究で必要な意味一貫性を保証する設計ではない。

### Hypothesis C

`Intent Drift` を減らすには、後段での if 文追加より前に、`_analyze_step_integrated` が返す role の責務定義を見直す必要がある。

## 6. Next Research Step

次に行うべきなのは、改善実装ではなく role 体系の分解である。

具体的には以下を整理する。

1. 期待したい `spec_role` 一覧
2. 現行実装が使っている `runtime_role` 一覧
3. `intent -> spec_role -> runtime_role` の対応表
4. どの段階でどの変換が許されるかの制約

ここを定義しない限り、`Intent Drift` の改善は場当たり的な role 上書きに戻る。
