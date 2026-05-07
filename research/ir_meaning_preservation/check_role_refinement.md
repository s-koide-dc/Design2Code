# CHECK Role Refinement

## 1. Purpose

この文書は、`spec_role = CHECK` を実装可能な粒度まで細分化し、IR 上で保持すべき判定情報を定義するためのものである。

`CHECK` は `DESERIALIZE` や `FILTER` よりも、構造ノードと条件式生成の両方にまたがるため、単に role 名だけを保持しても downstream で十分に使えない。

したがって本段階では、

1. `CHECK` の下位類型を固定する
2. 各類型に必要な IR メタデータを定義する
3. downstream での利用方針を最小限に整理する

この 3 点を目的とする。

## 2. Core Position

今後の研究では、`CHECK` を単一の意味役割として終わらせない。

最低限、次の 2 層を分ける。

1. `spec_role = CHECK`
2. `check_kind = <subtype>`

`spec_role` は「判定である」ことを示し、`check_kind` は「何をどう判定しているか」を示す。

## 3. CHECK Subtypes

初期定義では、`CHECK` を次の 4 類型に分ける。

### 3.1 `exists_check`

対象の存在有無を判定する。

例:

- `config.json が存在する`
- `該当ユーザーが存在する`
- `レスポンス要素が 1 件以上ある`

典型的な downstream 例:

- `File.Exists(path)`
- `collection.Any()`
- `value != null`

### 3.2 `null_check`

対象が `null` かどうかを判定する。

例:

- `取得結果が null なら`
- `設定値が存在しないなら`

典型的な downstream 例:

- `value == null`
- `value != null`

### 3.3 `comparison_check`

数値・文字列・状態値の比較判定を行う。

例:

- `Points が input より大きい`
- `status が Active である`
- `件数が 0 を超える`

典型的な downstream 例:

- `x > y`
- `x == "Active"`
- `count <= 0`

### 3.4 `state_check`

外部・内部状態が期待条件を満たすかを判定する。

これは `comparison_check` に近いが、単純な比較演算だけではなく、意味的状態判定を含む。

例:

- `認証済みである`
- `設定が有効である`
- `同期対象が更新済みである`

典型的な downstream 例:

- `user.IsAuthenticated`
- `config.Enabled`
- `item.IsSynchronized`

## 4. Boundary Rules

`CHECK` を過剰に拡張しないため、境界を次のように置く。

### 4.1 Included in CHECK

- 分岐条件として使われる判定
- true/false を返すための条件評価
- 存在・null・比較・状態の成立判断

### 4.2 Not Included in CHECK

- 集合から要素を絞る処理
  - これは `FILTER`
- 値の変換そのもの
  - これは `TRANSFORM`
- 件数計算や数値集約
  - これは `CALCULATE` または `AGGREGATE`
- 反復そのもの
  - これは `ITERATE`

## 5. Required IR Fields

`spec_role = CHECK` を downstream で利用可能にするため、少なくとも以下の情報が必要である。

### 5.1 Required Core Fields

- `semantic_map.spec_role`
  - 値: `CHECK`
- `semantic_map.check_kind`
  - 値: `exists_check`, `null_check`, `comparison_check`, `state_check`
- `semantic_map.check_subject`
  - 何を判定対象にしているか
- `semantic_map.expected_truth`
  - `true` / `false`

### 5.2 Optional Supporting Fields

- `semantic_map.check_operator`
  - `==`, `!=`, `>`, `<`, `>=`, `<=`
- `semantic_map.check_value`
  - 比較対象値
- `semantic_map.source_ref`
  - 明示 source がある場合
- `semantic_map.source_kind`
  - file / db / http / env / memory
- `semantic_map.check_property`
  - 対象の特定プロパティを判定する場合

## 6. Canonical IR Shapes

### 6.1 File Existence

```json
{
  "type": "CONDITION",
  "intent": "EXISTS",
  "semantic_map": {
    "spec_role": "CHECK",
    "check_kind": "exists_check",
    "check_subject": "config.json",
    "expected_truth": true,
    "source_ref": "config.json",
    "source_kind": "file"
  }
}
```

### 6.2 Null Check

```json
{
  "type": "CONDITION",
  "intent": "EXISTS",
  "semantic_map": {
    "spec_role": "CHECK",
    "check_kind": "null_check",
    "check_subject": "config",
    "expected_truth": false
  }
}
```

### 6.3 Numeric Comparison

```json
{
  "type": "CONDITION",
  "intent": "EXISTS",
  "semantic_map": {
    "spec_role": "CHECK",
    "check_kind": "comparison_check",
    "check_subject": "Points",
    "check_operator": ">",
    "check_value": "input_1",
    "expected_truth": true
  }
}
```

### 6.4 State Check

```json
{
  "type": "CONDITION",
  "intent": "EXISTS",
  "semantic_map": {
    "spec_role": "CHECK",
    "check_kind": "state_check",
    "check_subject": "user",
    "check_property": "IsAuthenticated",
    "expected_truth": true
  }
}
```

## 7. Downstream Consumption Strategy

最小方針として、downstream では次の順で判定を生成する。

1. `spec_role == CHECK` を確認する
2. `check_kind` を読む
3. `check_kind` ごとの専用変換を適用する

初期実装では、次の対応だけで十分である。

- `exists_check`
  - file source なら `File.Exists(...)`
  - collection subject なら `.Any()`
  - それ以外は `!= null`
- `null_check`
  - `== null` または `!= null`
- `comparison_check`
  - `subject operator value`
- `state_check`
  - `subject.property` または bool property 参照

## 8. Initial Benchmark Additions

`CHECK` を評価するため、次の 3 ケースを優先追加候補とする。

1. ファイル存在確認
2. null 確認
3. 数値比較確認

この 3 つで、`exists_check`, `null_check`, `comparison_check` を最低限カバーできる。

`state_check` は第 2 段階で追加してよい。

## 9. Implementation Order

実装順は次の通りとする。

1. `IRGenerator` に `check_kind` と関連メタデータを追加する
2. `Condition` 系生成経路で `spec_role/check_kind` を優先参照する
3. 比較ケースで `Expected IR -> Observed IR -> Generated condition` を確認する

この順を崩すと、再び条件文面への場当たり依存に戻りやすい。

## 10. Immediate Next Step

この文書の次にやるべきことは、優先 3 ケースの `CHECK` 比較ケースをベンチマークへ追加し、期待 IR 側に `check_kind` を明示することである。
