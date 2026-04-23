# Method Store Spec

本資料は `resources/method_store.json` と `resources/vectors/vector_db/method_store_meta.json` の **構造仕様** を定義する。

## 対象ファイル
1. `C:\workspace\NLP\resources\method_store.json`
2. `C:\workspace\NLP\resources\vectors\vector_db\method_store_meta.json`
3. `C:\workspace\NLP\resources\vectors\vector_db\method_store_vectors.npy`

## 1. ルート構造

### method_store.json
- ルートはオブジェクト。
- 必須キー: `methods`（配列）。

### method_store_meta.json
- ルートは配列。
- 各要素は `method_store.json.methods` の要素と同一構造。
  - `origin`, `id`, `name`, `class` は一致していること。
  - 追加メタがある場合は `method_store.json` 側へ反映する。

## 2. メソッド要素の構造（共通）

### 基本キー（最低限）
- `id` (string)
- `name` (string)
- `class` (string)
- `tags` (array of string)
- `code` (string)

### 拡張キー（品質上は必須）
- `return_type` (string)
- `params` (array)
- `definition` (string)
- `has_side_effects` (boolean)
- `usings` (array of string)
- `role` (string)
- `origin` (string)
- `summary` (string)

### 任意キー
- 追加されても良いが、仕様を更新すること。

### 例
```json
{
  "name": "Query",
  "class": "System.Data.IDbConnection",
  "return_type": "IEnumerable<T>",
  "params": [
    {"name":"cnn","type":"IDbConnection","role":"target"},
    {"name":"sql","type":"string","role":"sql"}
  ],
  "code": "{cnn}.Query<T>({sql}, {param})",
  "definition": "public static IEnumerable<T> Query<T>(this IDbConnection cnn, string sql, object param = null)",
  "tags": ["sql","database","query"],
  "has_side_effects": true,
  "usings": ["System.Data","Dapper"],
  "role": "FETCH",
  "id": "sys.system.data.idbconnection.query",
  "origin": "system",
  "summary": "Standard library method: Query in System.Data.IDbConnection"
}
```

## 3. params 配列要素（拡張キー）

### 必須キー
- `name` (string)
- `type` (string)
- `role` (string)

### role の例
- `target`: 呼び出し対象（`{cnn}` のような receiver）
- `sql`: SQL 文字列
- `param`: パラメータオブジェクト

## 4. code 文字列のプレースホルダ

- `{cnn}` / `{sql}` / `{param}` のような **パラメータ名と一致するプレースホルダ** を使用する。
- `{target}` は **呼び出し対象（レシーバ）** の慣習的プレースホルダとして許容する。
- `definition` の署名と `params` の順序・役割に整合している必要がある。

## 5. role / tags / usings の用途

- `role`: 合成器が意図（FETCH / PERSIST / TRANSFORM など）を判断するために使用。
- `tags`: 検索・意図推定・候補抽出に使用。
- `usings`: 生成コードに必要な `using` を付与するために使用。

## 6. 整合性ルール（推奨）

1. `id` は一意であり、`origin` + `class` + `name` を含む形式を推奨する。
2. `params` に定義される名前は `code` 内のプレースホルダと一致する。
3. `return_type` は `definition` と整合する。
4. `usings` は `code` / `definition` で参照される型に必要な名前空間を含む。
5. `method_store_meta.json` は **vector_db のメタ情報** であり、唯一の正解は `method_store.json`。

## 7. 運用指針

- 拡張キーは **コード生成品質の観点で必須** とみなし、段階的に埋める。
- バリデータはデフォルトで警告、`--strict` で必須違反をエラーにする。
