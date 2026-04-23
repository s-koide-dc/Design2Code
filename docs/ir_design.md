# IR (Intermediate Representation) による論理抽象化設計

## 1. 目的
指示文から直接 C# を生成するのではなく、一度「論理構造（IR）」に変換することで、以下を実現する。
- **構造の検証**: ループや条件分岐のネストが論理的に正しいか、コード生成前にチェックする。
- **依存関係の解決**: 必要なパラメータやエンティティの整合性を IR レイヤーで担保する。
- **マルチ言語対応**: 同一の IR から C# だけでなく Python 等の他言語への出力を可能にする。

## 2. IR の構造 (JSON 抽象木)
`schemas/ir_schema.json` に定義されたスキーマに基づき、以下のノードタイプと共通フィールドをサポートする。

### A. ACTION (最小実行単位)
メソッド呼び出しや代入を表す。
- `action_name`: "GetUsers", "SaveData" など
- `target_entity`: "User", "Order" など

### B. WRAPPER (構造的包摂)
Retry や Transaction など、他のアクションを包み込む構造を表す。
- `action_name`: "Retry"
- `children`: ラップされるアクションのリスト

### C. LOOP (反復)
- `target_entity`: 反復対象のエンティティ
- `children`: ループ内で実行されるアクション

### D. CONDITION (分岐)
- `condition_expression`: 評価される論理式
- `children`: true の場合の処理
- `else_children`: false の場合の処理

### E. ELSE / END (構造制御)
- `ELSE`: 直前の `CONDITION` の `else_children` に接続するための構造マーカー。
- `END`: ブロック終了を表すマーカー。IR 生成・整形フェーズでのみ使われる。

### F. TRANSFORM (互換タイプ)
- `TRANSFORM` は intent/role による変換の意味を表すために使われる。
- 互換のため `type` としても許容するが、基本は `intent` と `role` で表現する。

## 2.1 共通フィールド（主要）
- `id`: `step_1` のようなステップID。
- `intent`: `FETCH` / `PERSIST` / `TRANSFORM` / `DISPLAY` など。
- `role`: 合成時の役割（`TRANSFORM` など）。
- `cardinality`: `SINGLE` / `COLLECTION`。
- `output_type`: 出力型（例: `string`, `List<User>`）。
- `source_kind`: `file` / `db` / `http` / `memory` など。
- `source_ref`: データソース参照。
- `input_link`: 参照元ステップID。
- `semantic_map`: `semantic_roles` や `logic` の補助メタ。

## 2.2 自動チェーン
- `FETCH` → `JSON_DESERIALIZE` の自動挿入や、`PERSIST` 前の `JSON_SERIALIZE` などの補助ノードが挿入される場合がある。

## 3. 実装ロードマップ
1. **IR Generator の実装**: `MorphAnalyzer` と `SemanticAnalyzer` を組み合わせ、指示文のリストを `logic_tree` に変換する。
2. **IR Validator の実装**: 生成された IR が、現在の `MethodStore` にあるシンボルで実行可能か検証する。
3. **IR-to-CSharp Emitter の実装**: `CodeSynthesizer` を改修し、IR を入力として C# コードを出力するように変更する。

## 4. 期待される効果 (検証ケース)
### ケース: リトライ付きファイル読み込み
指示文: 「リトライして config.json を読み込む」
IR:
```json
{
  "type": "WRAPPER",
  "action_name": "Retry",
  "body": [
    { "type": "ACTION", "action_name": "ReadAllText", "parameters": { "path": "config.json" } }
  ]
}
```
emitter はこれを見て、`Retry(() => File.ReadAllText("config.json"))` のような適切なネスト構造を生成できるようになる。
