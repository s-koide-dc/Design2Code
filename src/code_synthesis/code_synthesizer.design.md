# code_synthesizer 設計ドキュメント (Class: CodeSynthesizer)

## 1. 目的 (Purpose)
`CodeSynthesizer` は、`IRGenerator` によって生成された中間表現 (IR) を基に、実行可能な C# ソースコードを自動合成します。ユーザーのコーディングスタイル設定を反映しつつ、複雑な制御構造とデータフローの整合性を高次元で両立させることを目的とします。

## 2. 構造化仕様 (Structured Specification)

### 2.1. 合成パイプライン
1.  **IR生成 & 検証**: `IRGenerator` と `IRValidator` を用い、自然言語から論理木を構築し、静的な整合性を確認。
2.  **再帰的エミット**: `IREmitter` が IR ツリーを走査。ビームサーチの状態をブロック（Loop/If）を跨いで維持。
3.  **後処理**: `_finalize_code` により、インデントの調整、Usings の整理、必要な POCO クラス定義の付加を行う。
4.  **未完成コードの禁止**: 構造化仕様を実装できない場合、設計ステップをTODOコメントだけに変換したコードは生成しない。
5.  **解決不能nodeの報告**: Action/Return/Filter/Calculate nodeを構造的に解決できない場合は空のコードと `synthesis_resolution_failed` を返し、`unresolved_nodes` にnode ID・intent・対象・理由を格納する。
6.  **後追い補完の制限**: `IREmitter` 後に未完了 node が残る場合でも、UKB 補完は intent / role / source_kind / target_entity / return_type の構造制約を満たす候補に限定する。引数不足を `null`、空文字、空 SQL で埋める補完は行わず、解決不能 node として報告する。
7.  **設計書内 entity schema**: `StructuredSpec.entity_specs` がある場合は合成中だけ既存 `entity_schema` へ一時マージし、IR 生成と POCO 生成に使う。
8.  **CodeBuilder依存性注入**: `builder_client` が渡された場合はそれを使用し、指定がない場合だけ標準の外部.NET `CodeBuilderClient` を生成する。設計解決の高速テストはインプロセス実装を注入でき、外部プロセス連携は専用テストで検証する。

### 2.2. 主要機能 (Core Logic)

1.  **ユーザー設定の反映 (User Preferences)**:
    - `config/user_preferences.json` に基づき、`var` キーワードの使用有無や非同期スタイルの統一を制御。
2.  **部品の具象化とバインド**:
    - **コンストラクタ生成**: `is_constructor: true` の部品に対し `new ClassName()` 形式で合成。
    - **インスタンスメソッドの自動バインド**: `{target}` プレースホルダに対し、直近の適合インスタンスを自動割り当て。
    - **自律的例外処理**: `network`, `io` 等の失敗しやすいタグを持つメソッドを自動で `try-catch` 保護。
3.  **構造制約に基づく合成制御**:
    - **セマンティック・サチュレーション (Semantic Saturation)**: 既に POCO 等に変換済みのデータに対し、冗長な解析（JSONデシリアライズ等）を行うパスを自動的にスキップ。
    - **終端アクション制約 (Terminal Action Constraint)**: `DISPLAY` インテントの最終ステップにおいて、副作用を持つ `void` メソッド（Console出力等）を強制的に選択。
    - **Async-First**: 非同期コンテキスト内では `Task` 戻り値を優先。
    - **引数捏造の禁止**: 既存変数、semantic roles、明示 literal で引数を満たせない場合は、スコア減点ではなく解決不能として扱う。
4.  **到達性監査 (Reachability Audit)**:
    - `content` / `data` / `accumulator` の Source が `DISPLAY` / `PERSIST` / `RETURN` / `NOTIFICATION` に到達しているかを検証し、未到達なら警告コメントを付与。
    - ステートメントの `consumes` メタデータに含まれる変数は消費済みとして扱う。
    - `raw` ステートメントでも `out_var` 生成時に Source 使用があれば消費済みとみなす。
    - `return` 文として出力された `raw` ステートメントも Sink 到達として扱う。
4.  **パラメータバインディングと変換の精密化**:
    - **ブリッジ変換テンプレート**: `TypeSystem` から提供されるテンプレート（`JsonSerializer.Serialize({var})` 等）を用いて、型不一致を自動的に解消。
    - **プロパティ優先**: ループ内では `item.Name` などの個別アクセスを優先。
    - **既定 semantic 語彙の共通化**: list input を `StructuredSpec` に正規化する際の `kind/intention` 既定値と最終ステップ返却型判定の semantic intent は `src.utils.semantic_intents` の共通定数を使う。
    - **list 入力の明示メソッド保持**: 補助 C# プロジェクト不在時の軽量経路でも、メソッド名またはIDの完全一致から明示メソッド ID を `StructuredSpec` へ引き継ぐ。
    5.  **決定論的な論理合成 (Strict Deterministic Logic)**:
        -   **ハード・インテント・フィルタ (Hard Intent Filters)**: `EXISTS` (bool), `DISPLAY` (void), `LINQ` (IEnumerable) といったインテントに対し、戻り値の型が不一致なメソッドを検索段階で厳格に除外。
        -   **厳格なリテラル・ロール束縛 (Strict Literal Role Binding)**: 指示文内のパス (`path`) や URL (`url`) といった特別な役割を持つリテラルは、メソッド部品側の同じ役割を持つ引数にのみバインドを許可。
        -   **プロパティ抽出の優先 (Prioritized Property Extraction)**: LINQ や条件分岐において、変数自体の存在チェック（Shortcut）よりも、指示文内の述語に基づいたプロパティ操作（`x.Price > 100`等）の抽出を優先。
    

### 2.3. 入力 (Input) / 出力 (Output)
- **Input**: `method_name`, `design_steps`, `return_type`, `intent` 等。
- **Output**: 合成された C# コード、依存 NuGet リスト、推論された POCO 情報。

## 3. 依存関係
- `src/ir_generator/ir_generator.py`
- `src/code_synthesis/ir_emitter.py`
- `src/code_synthesis/method_store.py`
- `src/code_synthesis/type_system.py`

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.
- 2026-03-31: StructuralMemory receives VectorEngine and MorphAnalyzer when available.
- 2026-06-04: `ActionSynthesizer` / `StatementBuilder` / `TemplateRegistry` / `UnifiedKnowledgeBase` の internal semantic intent 比較と role 優先度比較を `src.utils.semantic_intents` の共通語彙へ寄せた。
- 2026-06-04: `AutonomousSynthesizer` の `SET_METHOD_NAME` / `FILE_WRITE` / recovery task 連携で残っていた action intent の文字列直書きを `src.utils.action_intents` に統一した。
- 2026-06-30: 補助 C# プロジェクト不在時の軽量経路にも明示メソッド解決を追加した。
- 2026-07-01: 未使用のTODOコメント生成フォールバック `_synthesize_heuristic_code` を削除した。
- 2026-07-01: 解決不能なIRをTODOや `NotImplementedException` として出力せず、構造化エラーとして返すよう変更した。
- 2026-07-07: 後追い UKB 補完に role / source_kind / return_type を渡すよう変更。paramless/SQL-like の最小 fallback が `null` や空 SQL で引数不足を埋める経路を廃止し、未消費 node は `node_not_synthesized` として報告する。
- 2026-07-10: `StructuredSpec.entity_specs` を一時 schema として扱い、既存 schema にない entity の生成品質回帰を追加した。
