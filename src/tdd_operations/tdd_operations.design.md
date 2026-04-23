# TDDOperations Design Document

## 1. Purpose (Updated 2026-02-10)
`TDDOperations` は、独立したモジュールとして、テスト失敗の分析、修正提案の生成、およびコード修正の自動適用を担当します。`AdvancedTDDSupport` と連携し、テスト駆動開発のプロセスを自動化・支援します。

## 2. Structured Specification

### 2.1. 初期化 (`__init__`)
- **Parameters**: `action_executor` - 親となる ActionExecutor インスタンス (移行期間中)
- **Logic**: ActionExecutor への参照を保持し、`_get_entity_value` や `_safe_join` などのヘルパーメソッドにアクセスできるようにします。

### 2.2. テスト失敗分析 (`analyze_test_failure`)
- **Input**: `context` (直前のテスト実行結果を含む)
- **Core Logic**:
    1. **エラー情報の取得**: 直近の `action_result` または履歴から、テスト失敗（実行エラー）またはビルドエラーの詳細を自動的に取得します。
    2. **ビルドエラーのパース**: 実行エラーがない場合、ビルドログから正規表現（`file(line,col): error CSxxxx: message`）を用いて、ファイル名、行番号、エラーコードを抽出します。
    3. **ターゲットコードの動的特定**: 失敗したテストメソッド名からヒューリスティックに製品コードのクラス・メソッドを特定し、C#解析結果（manifest.json）を引いて対象の実装（メソッド本体）を自動的に読み込みます。
    4. **修正提案の生成**: `AdvancedTDDSupport` を呼び出し、抽出された失敗コンテキストに基づく具体的な修正案（Fix Suggestion）を生成します。
- **Output**: 分析結果と `safety_score` 等を含む修正提案のリスト。

### 2.3. ゴール駆動型TDD実行 (`execute_goal_driven_tdd`)
- **Input**: 
    - `goal_description`: 実装目標の説明
    - `acceptance_criteria`: 受入基準のリスト
    - `constraints`: 言語やカバレッジ目標などの制約
- **Core Logic**:
    1. `AdvancedTDDSupport` のゴール駆動エンジンを起動します。
    2. テスト生成、実装、実行のサイクルを反復し、目標達成を目指します。
- **Output**: 実行結果の統計（イテレーション数、成功率）と生成された成果物のリスト。

### 2.4. コード修正適用 (`apply_code_fix`)
- **Input**: `fix_id`（"all" で一括適用）、`backup_enabled`
- **Core Logic**:
    1. **一括適用プロセス**: ファイルごとに修正をグループ化し、行番号の変動を避けるために**降順（ファイル末尾から順に）**で修正を適用します。
    2. **修正タイプ別の処理**: 
       - `add_package`: `dotnet add package` を実行。
       - `null_validation`: メソッドの開始 `{` の直後にガード節を挿入。
       - `test_self_healing / parameter_fix`: 該当行を提案コードで置換。
       - `add_using`: ファイル先頭に `using` を挿入。
    3. **検証とロールバック**: 修正適用後に `validate_code_syntax`（ビルド等）を実行。検証に失敗した場合は、作成しておいたバックアップ（`.bak`）から自動的に元の状態へ復元します。
- **Output**: 適用成功数、失敗数、修正されたファイルの一覧。

## 3. Dependencies
- **Internal**: `ActionExecutor` (移行用依存), `AdvancedTDDSupport`, `CSharpOperations` (解析結果ロード用)
- **External**: `os`, `shutil`, `subprocess`, `re`, `datetime`, `collections`

## 4. Error Handling
- 履歴に修正提案が見つからない場合のエラー
- 修正適用後の検証失敗時の自動ロールバック
- ファイル操作やコマンド実行時の例外キャッチ
