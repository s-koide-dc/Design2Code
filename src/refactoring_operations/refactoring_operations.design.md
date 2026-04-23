# RefactoringOperations Design Document

## 1. Purpose
`RefactoringOperations` は、独立したモジュールとして、コードベースのリファクタリング分析、提案の生成、および適用（現在は手動適用の案内）を担当します。`RefactoringAnalyzer` と連携し、コードの保守性と品質の向上を支援します。

## 2. Structured Specification

### 2.1. 初期化 (`__init__`)
- **Parameters**: `action_executor` - 親となる ActionExecutor インスタンス (移行期間中)
- **Logic**: ActionExecutor への参照を保持し、`_get_entity_value` や `_safe_join` などのヘルパーメソッドにアクセスできるようにします。

### 2.2. リファクタリング分析 (`analyze_refactoring`)
- **Input**:
    - `project_path`: プロジェクトのルートパス
    - `language`: プログラミング言語
    - `options`: 分析オプション
- **Core Logic**:
    1. `RefactoringAnalyzer` を呼び出してプロジェクト全体をスキャンします。
    2. 検出されたコードスメル（God Class, Long Method 等）を優先度別に集計。
    3. 品質メトリクス（保守性指数、技術的負債）を算出。
    4. **サマリー構築**: 検出件数（高・中・低優先度）、自動修正可能数、および主要メトリクスをユーザー向けの分かりやすいメッセージに整形。
    5. **レポート連携**: 生成された分析レポート（JSON/HTML）のパスを応答に含める。
- **Output**: 検出数、メトリクス、レポートパスを含むサマリーメッセージ。

### 2.3. リファクタリング提案 (`suggest_refactoring`)
- **Input**: `analyze_refactoring` と同様。
- **Core Logic**:
    1. 分析を実行し、具体的な改善提案のリストを生成します。
    2. 各提案に対して、対象箇所、内容、見積り工数、自動修正の可否を付与します。
- **Output**: 主要な提案内容と推奨事項のサマリー。

### 2.4. リファクタリング適用 (`apply_refactoring`)
- **Input**:
    - `project_path`: プロジェクトパス
    - `suggestion_id`: 適用対象の提案ID
- **Core Logic**:
    1. 現在は自動適用を未実装とし、手動適用のための手順と注意点を提供します。
- **Output**: 手動適用ガイドメッセージ。

## 3. Dependencies
- **Internal**: `ActionExecutor` (移行用依存), `RefactoringAnalyzer`
- **External**: `os`, `typing`

## 4. Error Handling
- パス不備やファイル不在時のエラー
- 分析実行中の例外キャッチと報告
