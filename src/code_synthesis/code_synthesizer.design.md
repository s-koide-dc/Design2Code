# code_synthesizer 設計ドキュメント (Class: CodeSynthesizer)

## 1. 目的 (Purpose)
`CodeSynthesizer` は、`IRGenerator` によって生成された中間表現 (IR) を基に、実行可能な C# ソースコードを自動合成します。ユーザーのコーディングスタイル設定を反映しつつ、複雑な制御構造とデータフローの整合性を高次元で両立させることを目的とします。

## 2. 構造化仕様 (Structured Specification)

### 2.1. 合成パイプライン
1.  **IR生成 & 検証**: `IRGenerator` と `IRValidator` を用い、自然言語から論理木を構築し、静的な整合性を確認。
2.  **再帰的エミット**: `IREmitter` が IR ツリーを走査。ビームサーチの状態をブロック（Loop/If）を跨いで維持。
3.  **後処理**: `_finalize_code` により、インデントの調整、Usings の整理、必要な POCO クラス定義の付加を行う。

### 2.2. 主要機能 (Core Logic)

1.  **ユーザー設定の反映 (User Preferences)**:
    - `config/user_preferences.json` に基づき、`var` キーワードの使用有無や非同期スタイルの統一を制御。
2.  **部品の具象化とバインド**:
    - **コンストラクタ生成**: `is_constructor: true` の部品に対し `new ClassName()` 形式で合成。
    - **インスタンスメソッドの自動バインド**: `{target}` プレースホルダに対し、直近の適合インスタンスを自動割り当て。
    - **自律的例外処理**: `network`, `io` 等の失敗しやすいタグを持つメソッドを自動で `try-catch` 保護。
3.  **高度なスコアリング (Phase 13-14 強化)**:
    - **セマンティック・サチュレーション (Semantic Saturation)**: 既に POCO 等に変換済みのデータに対し、冗長な解析（JSONデシリアライズ等）を行うパスを自動的にスキップ。
    - **終端アクション制約 (Terminal Action Constraint)**: `DISPLAY` インテントの最終ステップにおいて、副作用を持つ `void` メソッド（Console出力等）を強制的に選択。
    - **Async-First**: 非同期コンテキスト内では `Task` 戻り値を優先。
    - **Hallucination Penalty**: 既存変数で引数を満たせない場合の捏造に対し、ペナルティを付与。
4.  **到達性監査 (Reachability Audit)**:
    - `content` / `data` / `accumulator` の Source が `DISPLAY` / `PERSIST` / `RETURN` / `NOTIFICATION` に到達しているかを検証し、未到達なら警告コメントを付与。
    - ステートメントの `consumes` メタデータに含まれる変数は消費済みとして扱う。
    - `raw` ステートメントでも `out_var` 生成時に Source 使用があれば消費済みとみなす。
    - `return` 文として出力された `raw` ステートメントも Sink 到達として扱う。
4.  **パラメータバインディングと変換の精密化**:
    - **ブリッジ変換テンプレート**: `TypeSystem` から提供されるテンプレート（`JsonSerializer.Serialize({var})` 等）を用いて、型不一致を自動的に解消。
    - **プロパティ優先**: ループ内では `item.Name` などの個別アクセスを優先。
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

