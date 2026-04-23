# AutonomousSynthesizer Design Document

## 1. Purpose
`AutonomousSynthesizer` is the core engine for autonomous code generation and evolution. It unifies the responsibilities of code synthesis (`CodeSynthesizer`), verification (`CompilationVerifier`, `ExecutionVerifier`), and self-healing (`TestFailureAnalyzer`).

It also integrates the legacy `GoalDrivenTDDEngine` capabilities, enabling it to decompose high-level requirements into smaller TDD goals and execute the Red-Green-Refactor cycle autonomously.

## 2. Structured Specification

### Input
- **Constructor**:
    - `config_manager`: 設定マネージャ。
    - `morph_analyzer` (Optional): 形態素解析器。
    - `vector_engine` (Optional): ベクトルエンジン。
    - `task_manager` (Optional): タスクマネージャ。
- **Method `synthesize_safely`**:
    - `method_name`: メソッド名。
    - `design_steps`: 設計手順リスト。
    - `max_retries`: 最大リトライ回数 (default: 3)。
    - `execute`: 実行検証を行うか (default: False)。
    - `session_context`: 文脈情報（直前のメソッド情報など）。
    - `return_type` / `input_param_type`: 型ヒント。
    - `work_dir`: 作業ディレクトリ。
- **Method `decompose_and_synthesize`**:
    - `goal`: `TDDGoal` オブジェクト（記述と受入条件）。

### Output
- **status**: "success", "partial_success", or "error".
- **code**: Final generated code.
- **artifacts**: List of generated test files and implementation files.
- **metrics**: Quality metrics (Cyclomatic Complexity, Maintainability Index, etc.).
- **attempts**: Number of retry attempts.

### Core Logic

#### A. 高レベル・ゴール駆動フロー (`decompose_and_synthesize`)
1. **要件分解**: `TDDGoal` の受入条件（acceptance_criteria）を、`IntentDetector` や `SemanticAnalyzer` を用いて個別のサブタスク（Requirement）に分解します。
2. **重複排除と再利用**: 
   - 各サブタスクの実装前に `StructuralMemory` を検索し、プロジェクト内に類似機能が既に存在しないか確認します。
   - 重複が検出された場合、既存のコードを `MethodStore` に **Call Pattern（呼び出しテンプレート）** としてインジェクトし、新規生成の代わりに再利用を試みます。メソッド本体の埋め込みではなく、`ClassName.MethodName({param1}, {param2})` 形式の型安全な呼び出しを生成します。
3. **順次合成と文脈維持**:
   - 分解された要件を一つずつ `synthesize_safely` で合成します。
   - 直前のメソッドの戻り値型やシグネチャを「セッションコンテキスト」として次の合成ステップに引き継ぎ、メソッド間の整合性を保ちます。
4. **コード統合**: 合成された複数のメソッド、Using文、および抽出されたPOCO定義を統合し、クリーンな単一のC#ファイルとして出力します。

#### B. 低レベル・自己修復合成フロー (`synthesize_safely`)
1. **初期合成**: `CodeSynthesizer` によりコードを生成します。
2. **検証ループ**: ビルド（Compilation）および実行（Execution）による検証を最大 N 回繰り返します。
3. **依存関係の自律解決 (Autonomous NuGet Resolution)**:
   - ビルドエラー `CS0246` (型または名前空間が見つからない) を検知した場合、エラーメッセージからシンボル名を抽出します。
   - `NuGetClient` を使用して対応するパッケージを検索・特定します。
   - 特定されたパッケージを依存関係リストに追加し、即座に再合成・再ビルドを行います。
4. **失敗分析とフィードバック**:
   - 検証失敗時、`TestFailureAnalyzer` によりエラーの原因（型不一致、メソッド不在、実行時例外等）を特定します。
   - 負のフィードバックを `KnowledgeBase` に蓄積し、同じ過ちを繰り返さないよう学習します。
5. **設計ステップの動的補完**:
   - エラー内容に基づき、「ToStringを追加する」「ファイルの存在チェックを入れる」といった具体的な修正ステップを `design_steps` に自動的に注入して再合成を行います。
6. **完了判定と学習の確定**:
   - ビルドと実行時のアサーション（`LogicAuditor` による目標抽出）がすべてパスした時点で、成功としてコードを返却します。
   - 成功時、新たに解決された NuGet パッケージ情報を `NuGetClient` を通じて永続化ファイルに保存し、学習結果を確定させます。


## 3. Dependencies
- **Components**:
    - `CodeSynthesizer`: Core logic generation.
    - `CompilationVerifier` / `ExecutionVerifier`: Validation.
    - `TestFailureAnalyzer`: Error analysis.
    - `DynamicHarvester`: External method acquisition.
    - `DummyDataFactory`: Test data generation.
    - `NuGetClient`: Dependency resolution.
    - `StructuralMemory`: Project structure awareness.
- **Legacy Components (Integrated)**:
    - Conceptually replaces `GoalDrivenTDDEngine`.

## 4. Key Scenarios
- **Scenario 1: Simple Synthesis**: User asks for "A method to read a text file". -> Synthesizes `File.ReadAllText`.
- **Scenario 2: Self-Healing**: Synthesized code fails build due to type mismatch. -> Analyzer detects mismatch -> Synthesizer adds explicit cast -> Build passes.
- **Scenario 3: Goal Driven**: User asks for "A calculator service". -> Decomposes into "Add", "Subtract". -> Generates `Calculator` class and tests. -> Verifies all.
- **Scenario 4: Dependency Resolution**: Code uses `CsvHelper` but package is missing. -> Build fails. -> `NuGetClient` resolves `CsvHelper`. -> Adds package and rebuilds -> Success.

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.
- 2026-04-21: StructuralMemory の保存先は `config_manager.storage_dir`（`resources/vectors/vector_db`）を使用し、`cache` への分散保存を避ける構成に更新。

