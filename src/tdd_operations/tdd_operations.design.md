# TDDOperations Design Document
<!-- metadata-sync: 2026-07-09T00:00:00+09:00 -->

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
    2. **ビルドエラーのパース**: 実行エラーがない場合、ビルドログを固定区切りで分解し、`file(line,col): error CSxxxx: message` 形式からファイル名、行番号、エラーコードを抽出します。正規表現による推定は行いません。
    3. **ターゲットコードの動的特定**: Roslyn解析結果とスタックトレースのファイル・行番号を照合し、メソッドの行範囲から対象の実装を特定します。テストメソッドの命名規約には依存しません。
    4. **修正提案の生成**: `AdvancedTDDSupport` を呼び出し、抽出された失敗コンテキストに基づく具体的な修正案（Fix Suggestion）を生成します。
       - C#解析済みの場合は `manifest` / `details_by_id` を `roslyn_data` として渡し、`AdvancedTDDSupport` がスタック位置から対象メソッドの構造化symbol情報を解決します。
       - 解析結果が履歴に無い場合は、直近のテスト実行 `project_path` を使ってRoslyn解析を実行し、失敗分析へ渡します。解析不能時は従来の安全なロールバック経路を維持します。
    5. **対話メタデータの固定化**: `failure_count` / `suggestion_count` / `failed_test_names` / `primary_target_file` / `primary_reason` / `primary_recommended_action` / `primary_target_summary` / `next_action` を `action_result.dialogue_metadata` と `failure_summary` に格納します。
- **Output**: 分析結果と、適用可否・理由・推奨アクションを含む修正提案のリスト。`safety_score` は互換フィールドとして保持される場合がありますが、表示や適用可否の判断には使いません。

### 2.3. ゴール駆動型TDD実行 (`execute_goal_driven_tdd`)
- **Input**: 
    - `goal_description`: 実装目標の説明
    - `acceptance_criteria`: 受入基準のリスト
    - `constraints`: 言語やカバレッジ目標などの制約
- **Core Logic**:
    1. `AdvancedTDDSupport` のゴール駆動エンジンを起動します。
    2. テスト生成、実装、実行のサイクルを反復し、目標達成を目指します。
    3. `goal_description` / `iteration_count` / 生成コード数 / 生成テスト数 / `next_action` を `dialogue_metadata` と `tdd_summary` に格納します。
- **Output**: 実行結果の統計（イテレーション数、成功率）と生成された成果物のリスト。

### 2.4. コード修正適用 (`apply_code_fix`)
- **Input**: `fix_id`（"all" で一括適用）、`backup_enabled`
- **Core Logic**:
    0. `fix_` / `heal_` / `manual_` / `calc_` / `nullcheck_` の提案 ID は個別適用対象として保持し、未知の自然言語指定だけを一括適用へ正規化します。
    1. **一括適用プロセス**: ファイルごとに修正をグループ化し、行番号の変動を避けるために**降順（ファイル末尾から順に）**で修正を適用します。
    2. **修正タイプ別の処理**: 
       - `add_package`: `dotnet add package` を実行。
       - `null_validation`: メソッドの開始 `{` の直後にガード節を挿入。
       - `test_self_healing / parameter_fix`: 該当行を提案コードで置換。
       - `add_using`: ファイル先頭に `using` を挿入。
    3. **検証とロールバック**: 修正適用後に `validate_code_syntax`（ビルド等）を実行。検証に失敗した場合は、作成しておいたバックアップ（`.bak`）から自動的に元の状態へ復元します。
       - `test_arrange_fix` / `test_self_healing` は、対象ファイルから一意に解決した `.csproj` に対して `dotnet test --no-restore` も実行し、テスト失敗・タイムアウト・プロジェクト特定不能時はロールバックします。
    4. **対話メタデータの固定化**: 適用件数、スキップ件数、変更ファイル一覧、理由、推奨アクション、対象要約を `dialogue_metadata` と `generated_files` に格納します。
- **Output**: 適用成功数、失敗数、修正されたファイルの一覧。

## 3. Dependencies
- **Internal**: `ActionExecutor` (移行用依存), `AdvancedTDDSupport`, `CSharpOperations` (解析結果ロード用)
- **External**: `os`, `shutil`, `subprocess`, `datetime`, `collections`

## 4. Error Handling
- 履歴に修正提案が見つからない場合のエラー
- 修正適用後の検証失敗時の自動ロールバック
- ファイル操作やコマンド実行時の例外キャッチ

## 5. Operational Notes
- 個別失敗分析中の例外は `action_executor.log_manager` とモジュール logger に記録し、stdout へ直接出力しない。
- 利用者向けの結果は `context["action_result"]` に集約する。
- `dialogue_metadata` は `response_generator` 向けの決定論的入力であり、文面そのものはここで生成しない。
