# MethodStore 設計ドキュメント

## 1. 目的 (Purpose)
`MethodStore` は収集されたメソッド部品を管理し、検索機能を提供します。建築的な制約（ループ内でのシリアライズ禁止など）をスコアリングで強制し、実績ベースの学習（セマンティック・フィードバック）によって自律的に精度を向上させます。

## 2. 構造化仕様 (Structured Specification)

### 2.1. 検索ロジック (search)
1.  **ハイブリッド検索**: セマンティック（ベクトル）とキーワードのマッチングを統合。
2.  **語彙クリーニング**: `internal` や特殊型（`Span<T>`, `Pointer`）を含むメソッドを自動減点。
3.  **スコアリングルール**:
    - **Intent Boosting**: `FILE_IO`, `DATABASE_QUERY`, `EXISTS` 等の意図に応じたタグマッチ加点。
    - **Loop Body Hard Block**: 意図が `LOOP_BODY` かつ明示的な `DISPLAY` 等のインテントがない場合、`serialize` や `json` を含むメソッドにペナルティ。
    - **Project Priority**: プロジェクト内コード (`reuse`, `manual_override`) を優先。
4.  **依存関係フィルタリング**: `current_project_context.json` を参照し、未参照パッケージに依存するメソッドを完全に除外。

### 2.2. 学習機能
- **セマンティック・フィードバック**: `record_semantic_feedback` により、意図ごとの成功・失敗履歴を記録し、動的にスコアを調整。

### 2.3. 入力 / 出力
- **Input**: `query` (str), `limit` (int), `intent` (str).
- **Output**: スコアリング済みのメソッド候補リスト。

## 3. 依存関係
- `scoring_rules.json`: 基本配点ルール。
- `current_project_context.json`: パッケージ利用状況。
- `LightVectorDB`: 高速な近傍探索。

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.
- 2026-04-21: `method_store_meta.json` / `method_store_vectors.npy` は `config.storage_dir`（`resources/vectors/vector_db`）へ統一し、旧配置（workspace root / `resources` / `cache`）は起動時移行で整理する構成に更新。

