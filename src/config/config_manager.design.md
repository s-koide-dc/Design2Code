# ConfigManager Design Document

## 1. Purpose (Updated 2026-02-10 10:45)

`ConfigManager` は、AIパイプライン全体の設定管理を一元化するモジュールです。各種JSON設定ファイルの読み込み、パス解決、設定値の提供を担当し、システム全体で一貫した設定アクセスを可能にします。設定ファイルとデータアセットを明確に分離し、効率的な設定管理を実現します。

## 2. Structured Specification

### 2.1. 初期化 (`__init__`)
- **Parameters**: 
  - `workspace_root` (str, optional): ワークスペースのルートディレクトリ（デフォルト: 現在のディレクトリ）
- **Logic**:
  1. `workspace_root` を `Path` オブジェクトとして保存
  2. **コア設定ファイルの読み込み**（`config/` ディレクトリから）:
     - `config.json`: メイン設定
     - `safety_policy.json`: 安全性ポリシー
     - `retry_rules.json`: リトライルール
     - `project_rules.json`: プロジェクトルール
     - `scoring_rules.json`: スコアリングルール
  3. **設定ファイルパスの構築**（`config/` ディレクトリ）:
     - `error_patterns_path`: エラーパターン定義
     - `cicd_config_path`: CI/CD設定
     - `coverage_config_path`: カバレッジ設定
     - `refactoring_config_path`: リファクタリング設定
     - `method_store_path`: メソッドストアマスタ (resources/method_store.json)
     - `storage_dir`: セマンティック検索用ストレージのベースディレクトリ (resources/vectors/vector_db)
  4. **データアセットパスの構築**（`resources/` ディレクトリ）:
     - `intent_corpus_path`: 意図コーパス
     - `vector_model_path`: ベクトルモデル
     - `knowledge_base_path`: 知識ベース
     - `task_definitions_path`: タスク定義
     - `domain_dictionary_path`: ドメイン辞書

### Input
- **Description**: ワークスペースルートパス（オプション）
- **Type/Format**: `str` または `None`
- **Example**:
  ```python
  workspace_root = "/path/to/project"
  # または
  workspace_root = None  # 現在のディレクトリを使用
  ```

### Output
- **Description**: 設定値、設定セクション、またはファイルパス
- **Type/Format**: `Any`, `Dict[str, Any]`, `str`, `list`
- **Example**:
  ```python
  # 単一設定値
  value = config_manager.get("max_retries", 3)
  
  # 設定セクション
  clarification_config = config_manager.get_section("clarification")
  
  # 安全性ポリシー
  safety_policy = config_manager.get_safety_policy()
  
  # リトライルール
  retry_rules = config_manager.get_retry_rules()
  
  # プロジェクトルール
  project_rules = config_manager.get_project_rules()
  
  # ファイルパス
  path = config_manager.knowledge_base_path
  ```

### Core Logic

#### 2.2. JSON設定ファイルの読み込み (`_load_json`)
1. **ファイル存在確認**: 指定されたパスにファイルが存在するか確認
2. **ファイル読み込み**: UTF-8エンコーディングでファイルを開く
3. **JSON解析**: `json.load()` でJSONをパース
4. **エラーハンドリング**:
   - ファイルが存在しない場合: 空の辞書 `{}` を返す
   - JSON解析エラーの場合: 空の辞書 `{}` を返す
5. **返り値**: パースされた辞書または空の辞書

#### 2.3. 設定値の取得 (`get`)
1. **キーの検索**: `config_data` 辞書から指定されたキーを検索
2. **デフォルト値の適用**: キーが存在しない場合、デフォルト値を返す
3. **返り値**: 設定値またはデフォルト値

#### 2.4. 設定セクションの取得 (`get_section`)
1. **セクションの検索**: `config_data` 辞書から指定されたセクション名を検索
2. **デフォルト値の適用**: セクションが存在しない場合、空の辞書を返す
3. **返り値**: 設定セクション（辞書）または空の辞書

#### 2.5. 専用設定の取得
- **`get_safety_policy()`**: 安全性ポリシーの辞書を返す
- **`get_retry_rules()`**: リトライルールのリストを返す（`retry_rules.json` の "retry_rules" キー）
- **`get_project_rules()`**: プロジェクトルールの辞書を返す

### Test Cases

#### Happy Path
- **Scenario 1**: 標準的な設定ファイルが存在する環境での初期化と設定取得
  - **Input**: `ConfigManager()`
  - **Expected Output**: 各設定ファイルの内容が正常に読み込まれ、設定値が取得できる
  
- **Scenario 2**: 設定値の取得
  - **Input**: `config_manager.get("max_retries", 3)`
  - **Expected Output**: `config.json` に "max_retries" が存在する場合はその値、存在しない場合は 3
  
- **Scenario 3**: 設定セクションの取得
  - **Input**: `config_manager.get_section("clarification")`
  - **Expected Output**: `config.json` の "clarification" セクション全体（辞書）

#### Edge Cases
- **Scenario 1**: 設定ファイルが存在しない場合
  - **Input**: 存在しないファイルパスでの初期化
  - **Expected Output**: 空の辞書が返され、エラーは発生しない
  
- **Scenario 2**: 不正なJSON形式のファイル
  - **Input**: 構文エラーのあるJSONファイル
  - **Expected Output**: 空の辞書が返され、例外は発生しない
  
- **Scenario 3**: 存在しない設定キーの取得
  - **Input**: `get("nonexistent_key")`
  - **Expected Output**: `None` が返される
  
- **Scenario 4**: デフォルト値の使用
  - **Input**: `get("nonexistent_key", "default_value")`
  - **Expected Output**: `"default_value"` が返される
  
- **Scenario 5**: 存在しない設定セクションの取得
  - **Input**: `get_section("nonexistent_section")`
  - **Expected Output**: 空の辞書 `{}` が返される

## 3. Directory Structure

### 設定ファイル (`config/` ディレクトリ)
- `config.json`: メイン設定
- `safety_policy.json`: 安全性ポリシー
- `retry_rules.json`: リトライルール
- `project_rules.json`: プロジェクトルール
- `scoring_rules.json`: スコアリングルール
- `error_patterns.json`: エラーパターン定義
- `cicd_config.json`: CI/CD設定
- `coverage_config.json`: カバレッジ設定
- `refactoring_config.json`: リファクタリング設定

### データアセット (`resources/` ディレクトリ)
- `intent_corpus.json`: 意図コーパス
- `vectors/chive-1.3-mc90.txt`: ベクトルモデル
- `knowledge_base.json`: 知識ベース
- `task_definitions.json`: タスク定義
- `domain_dictionary.json`: ドメイン辞書

## 4. Security & Boundary Rules

- **パストラバーサル防止**: ワークスペースルート配下のファイルのみアクセス
- **ファイル読み込み制限**: JSON形式のファイルのみ処理
- **エラー情報の制限**: ファイル読み込みエラー時は詳細なエラー情報を外部に漏らさない
- **デフォルト値の提供**: 設定が存在しない場合でもシステムが動作するようデフォルト値を提供

## 5. Consumers

- **pipeline_core**: パイプライン全体の設定管理
- **intent_detector**: 意図コーパスパスの取得
- **vector_engine**: ベクトルモデルパスの取得
- **semantic_analyzer**: 知識ベースパスの取得
- **safety_policy_validator**: 安全性ポリシーの取得
- **planner**: リトライルールとプロジェクトルールの取得
- **task_manager**: タスク定義の取得
- **action_executor**: エラーパターンと安全性ポリシーの取得
- **cicd_integrator**: CI/CD設定の取得
- **coverage_analyzer**: カバレッジ設定の取得
- **refactoring_analyzer**: リファクタリング設定の取得

## 6. Dependencies

- **Internal**: なし（他のモジュールに依存しない基盤モジュール）
- **External**: 
  - `pathlib.Path`: パス操作
  - `json`: JSON解析
  - `os`: ファイルシステム操作
  - `typing`: 型ヒント

## 7. Design Principles

- **単一責任の原則**: 設定管理のみに特化
- **依存性の最小化**: 他のモジュールに依存しない
- **エラー耐性**: 設定ファイルが存在しない場合でも動作可能
- **明確な分離**: 設定ファイル（`config/`）とデータアセット（`resources/`）を明確に分離
- **一貫性**: 全てのモジュールが同じインターフェースで設定にアクセス
