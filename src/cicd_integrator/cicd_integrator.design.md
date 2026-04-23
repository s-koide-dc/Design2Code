# cicd_integrator Design Document

## 1. Purpose (Updated 2026-04-14)

`cicd_integrator`モジュールは、既存のテスト生成、カバレッジ分析、リファクタリング支援機能をCI/CDパイプラインに統合し、自動化された品質管理を提供します。GitHub Actions、Azure DevOps、Jenkinsなどの主要なCI/CDプラットフォームに対応し、品質ゲートによる自動品質評価とレポート統合を実現します。

**主要機能**:
- **GitHub Actions統合**: 多言語対応のワークフロー自動生成（C#/Python/JavaScript）
- **品質ゲート管理**: 5種類のゲート（テスト実行、カバレッジ、品質スコア、スメル検出）
- **パイプライン設定生成**: YAML形式の設定ファイル自動生成
- **品質レポート統合**: テスト、カバレッジ、リファクタリングレポートの統合
- **品質チェッカー**: CI/CDパイプラインでの自動品質評価
- **多プラットフォーム対応**: GitHub Actions、Azure DevOps、Jenkins対応

## 2. Architecture Overview

### 2.1 Core Components

#### CICDIntegrator (Main Class)
- **役割**: CI/CD統合の中心的なコントローラー
- **責任**: プラットフォーム別パイプライン生成、品質ゲート管理、レポート統合、設定およびプロファイル管理（`CICDTemplateManager`/`ProfileManager`の機能を包含）
- **初期化**:
  - `workspace_root`: ワークスペースのルートディレクトリ（`Path` オブジェクト）
  - `log_manager`: ロギングマネージャー（オプション）
  - `config`: CI/CD設定（`_load_cicd_config()` で読み込み）
  - `generators`: プラットフォーム別ジェネレーターの辞書
  - `quality_gate_manager`: 品質ゲートマネージャー
  - `report_integrator`: 品質レポート統合器

#### Platform-Specific Generators
- **GitHubActionsGenerator**: GitHub Actionsワークフロー生成（完全実装）
  - `generate_pipeline(project_info, options)`: ワークフロー設定を生成
- **AzureDevOpsGenerator**: Azure DevOpsパイプライン生成（基本構造）
  - `generate_pipeline(project_info, options)`: パイプライン設定を生成
- **JenkinsGenerator**: Jenkinsパイプライン生成（基本構造）
  - `generate_pipeline(project_info, options)`: Jenkinsfile を生成

#### Quality Management
- **QualityGateManager**: 品質ゲートの設定と評価（ロジック担当）
  - `setup_gates(quality_gates, language)`: 品質ゲートを設定
- **QualityReportIntegrator**: 複数品質レポートの統合
  - レポートの統合とダッシュボード生成
- **QualityGateChecker**: CI/CDパイプライン環境で実行される独立したスクリプト（`python -m src.cicd_integrator.quality_gate_checker`として呼び出し）

### 2.2 Pipeline Generation Process

#### 1. プロジェクト情報収集フェーズ
- プロジェクト構造の分析
- 言語とフレームワークの特定
- 既存CI/CD設定の確認

#### 2. パイプライン設計フェーズ
- プラットフォーム固有の設定生成
- 言語別最適化の適用
- 品質チェックステップの統合

#### 3. 品質ゲート設定フェーズ
- 品質基準の定義
- ゲート条件の設定
- 評価ロジックの構築

#### 4. 設定ファイル生成フェーズ
- YAML/JSON形式での出力
- テンプレートの適用
- カスタマイズの反映

### 2.3 Integration Points

#### ActionExecutor統合
- `_setup_cicd_pipeline()`: CI/CDパイプライン設定
- `_configure_quality_gates()`: 品質ゲート設定
- `_generate_cicd_config()`: CI/CD設定ファイル生成

#### 既存分析機能統合
- TestGenerator: 自動テスト実行の統合
- CoverageAnalyzer: カバレッジ測定の統合
- RefactoringAnalyzer: コード品質分析の統合

#### LogManager統合
- パイプライン生成イベントの記録
- 品質ゲート評価結果の履歴管理
- エラーと警告の追跡

## 3. Structured Specification

### Input

- **Description**: CI/CDパイプライン生成対象のプロジェクト情報と設定オプション
- **Type/Format**: `dict`
- **Example**:
  ```json
  {
    "project_info": {
      "name": "MyDotNetApp",
      "language": "csharp",
      "ci_platform": "github_actions",
      "framework": "net6.0",
      "test_framework": "xunit"
    },
    "quality_gates": {
      "test_coverage_threshold": 80,
      "quality_score_threshold": 7.0,
      "max_high_priority_smells": 0,
      "max_medium_priority_smells": 5
    },
    "options": {
      "output_formats": ["yaml", "json"],
      "enable_security_scanning": true,
      "profile": "enterprise"
    }
  }
  ```

### Output

- **Description**: 生成されたパイプライン設定、品質ゲート、統合レポートを含む結果
- **Type/Format**: `dict`
- **Example**:
  ```json
  {
    "status": "success",
    "platform": "github_actions",
    "project_info": {
      "name": "MyDotNetApp",
      "language": "csharp",
      "ci_platform": "github_actions"
    },
    "pipeline_config": {
      "workflow": {
        "name": "CI/CD Pipeline - MyDotNetApp",
        "on": {
          "push": {"branches": ["main", "develop"]},
          "pull_request": {"branches": ["main"]}
        },
        "jobs": {
          "quality-check": {
            "runs-on": "ubuntu-latest",
            "steps": [
              {"name": "Checkout code", "uses": "actions/checkout@v3"},
              {"name": "Setup .NET", "uses": "actions/setup-dotnet@v3"},
              {"name": "Run tests", "run": "dotnet test"},
              {"name": "Quality gate check", "run": "python -m src.cicd_integrator.quality_gate_checker"}
            ]
          }
        }
      },
      "language": "csharp",
      "steps_count": 8
    },
    "quality_gates": [
      {
        "name": "test_execution",
        "type": "blocking",
        "condition": "all_tests_pass",
        "description": "全テストが成功すること",
        "timeout": 300
      },
      {
        "name": "coverage_check",
        "type": "blocking",
        "condition": "coverage >= 80",
        "description": "テストカバレッジが80%以上であること",
        "metric": "line_coverage"
      }
    ],
    "config_files": [
      {
        "path": ".github/workflows/ci-cd.yml",
        "content": "name: CI/CD Pipeline - MyDotNetApp\n...",
        "type": "yaml",
        "description": "GitHub Actions CI/CDワークフロー"
      }
    ],
    "generated_at": "2026-01-20T16:57:36"
  }
  ```

### Core Logic

#### 1. 初期化と設定 (`__init__`, `_load_cicd_config`)
- **ワークスペースルートの設定**: `Path` オブジェクトとして保存
- **ロガーの設定**: `log_manager` への参照を保存
- **設定の読み込み**:
  1. デフォルト設定を定義（プラットフォーム、品質ゲート、通知、言語設定、品質ツールコマンド）
  2. `resources/cicd_config.json` が存在する場合、読み込み
  3. `_deep_merge_config()` でデフォルト設定とマージ
  4. エラーが発生した場合、警告をログに記録してデフォルト設定を使用
- **ジェネレーターの初期化**: プラットフォーム別ジェネレーターを辞書に格納
- **品質管理コンポーネントの初期化**: `QualityGateManager` と `QualityReportIntegrator` を初期化

#### 2. 設定の深いマージ (`_deep_merge_config`)
- **再帰的マージ**:
  1. `override_config` の各キーと値を走査
  2. キーが `base_config` に存在し、両方が辞書の場合、再帰的にマージ
  3. それ以外の場合、`override_config` の値で上書き
- **目的**: デフォルト設定を保持しつつ、ユーザー設定で上書き

#### 3. パイプライン生成 (`generate_pipeline`)
- **ログ記録**: パイプライン生成開始イベントを記録
- **プロジェクト情報の検証**:
  1. `_validate_project_info()` を呼び出し
  2. 検証に失敗した場合、エラーメッセージを返す
- **プラットフォームの選択**:
  1. `project_info` から `ci_platform` を取得（デフォルト: "github_actions"）
  2. サポートされていないプラットフォームの場合、エラーを返す
- **パイプライン設定の生成**:
  1. プラットフォーム固有のジェネレーターを取得
  2. `generator.generate_pipeline(project_info, options)` を呼び出し
- **品質ゲートの設定**:
  1. `quality_gate_manager.setup_gates()` を呼び出し
  2. プロジェクト情報の品質ゲート設定と言語を渡す
- **設定ファイルの生成**:
  1. `_generate_config_files()` を呼び出し
  2. プラットフォーム、パイプライン設定、プロジェクト情報を渡す
- **結果の返却**: 生成されたパイプライン設定、品質ゲート、設定ファイルを含む辞書を返す

#### 4. プロジェクト情報の検証 (`_validate_project_info`)
- **必須フィールドのチェック**:
  - `name`: プロジェクト名
  - `language`: プログラミング言語
- **言語のサポート確認**: 設定に言語固有の設定が存在するか確認
- **検証結果の返却**: `{"valid": True/False, "errors": [...]}`

#### 5. 品質ゲート設定
- 品質基準の定義
- ゲート条件の構築
- 評価ロジックの設定

#### 6. レポート統合
- 複数品質レポートの統合
- 統合ダッシュボードの生成
- トレンド分析の実行

#### 7. 設定ファイル生成 (`_generate_config_files`)
- **プラットフォーム別処理**:
  - GitHub Actions: `.github/workflows/` ディレクトリにYAMLファイルを生成
  - Azure DevOps: `azure-pipelines.yml` を生成
  - Jenkins: `Jenkinsfile` を生成
- **ディレクトリ構造の作成**: 必要に応じてディレクトリを作成
- **ファイル保存**: 生成された設定をファイルに書き込み
- **検証**: 生成されたファイルの妥当性を確認

#### 8. 品質評価実行
- メトリクス収集
- ゲート条件の評価
- 結果レポートの生成

### Test Cases

#### パイプライン生成テスト
- **Scenario**: C#プロジェクトのGitHub Actionsワークフロー生成
- **Input**: `{"name": "TestProject", "language": "csharp", "ci_platform": "github_actions"}`
- **Expected Output**: 8ステップのワークフロー、品質ゲート5個、YAML設定ファイル

#### 品質ゲート評価テスト
- **Scenario**: 品質メトリクスによるゲート評価
- **Input**: `{"coverage": 85, "quality_score": 8.0, "high_priority_smells": 0}`
- **Expected Output**: 全ゲート通過、overall_status: "passed"

#### 多言語対応テスト
- **Scenario**: Python、JavaScript、C#の統合パイプライン
- **Input**: 各言語のプロジェクト情報
- **Expected Output**: 言語固有の最適化されたワークフロー

#### レポート統合テスト
- **Scenario**: テスト、カバレッジ、リファクタリングレポートの統合
- **Input**: 3種類のレポートデータ
- **Expected Output**: 統合品質スコア、推奨アクション、HTML/JSONレポート

#### エラーハンドリングテスト
- **Scenario**: 無効なプロジェクト情報での処理
- **Input**: 必須フィールド不足のプロジェクト情報
- **Expected Output**: 適切なエラーメッセージと検証結果

## 4. Consumers
- **action_executor**: Invokes CI/CD pipeline setup and configuration.

## 4. Dependencies

- **Internal**: `test_generator`, `coverage_analyzer`, `refactoring_analyzer`, `action_executor`, `log_manager`
- **External**: `os`, `json`, `datetime`, `pathlib`, `collections`, `subprocess`
- **CI/CD Tools**:
  - GitHub Actions: YAML生成、Actions API
  - Azure DevOps: Pipeline YAML、REST API
  - Jenkins: Jenkinsfile、Pipeline DSL

## 5. Configuration

### CI/CD設定ファイル (`resources/cicd_config.json`)

#### デフォルト設定の構造
```json
{
  "platforms": {
    "github_actions": {
      "enabled": true,
      "workflow_path": ".github/workflows",
      "default_runner": "ubuntu-latest"
    },
    "azure_devops": {
      "enabled": false,
      "pipeline_path": "azure-pipelines.yml"
    },
    "jenkins": {
      "enabled": false,
      "pipeline_path": "Jenkinsfile"
    }
  },
  "quality_gates": {
    "test_coverage_threshold": 80,
    "quality_score_threshold": 7.0,
    "max_high_priority_smells": 0,
    "max_medium_priority_smells": 5,
    "timeout_seconds": 300
  },
  "notifications": {
    "pr_comments": true,
    "slack_enabled": false,
    "email_enabled": false
  },
  "language_configs": {
    "csharp": {
      "build_command": "dotnet build",
      "test_command": "dotnet test",
      "coverage_tool": "coverlet",
      "package_restore": "dotnet restore"
    },
    "python": {
      "build_command": "py -m pip install -r requirements.txt",
      "test_command": "py -m unittest discover tests/unit",
      "coverage_tool": "coverage",
      "package_restore": "py -m pip install -r requirements.txt"
    },
    "javascript": {
      "build_command": "npm run build",
      "test_command": "npm test",
      "coverage_tool": "jest",
      "package_restore": "npm install"
    }
  },
  "quality_tool_commands": {
    "refactoring_analyzer": "python -m src.refactoring_analyzer.refactoring_analyzer",
    "quality_gate_checker": "python -m src.cicd_integrator.quality_gate_checker"
  }
}
```

#### 設定のマージ動作
- ユーザー設定ファイル（`resources/cicd_config.json`）が存在する場合、デフォルト設定と深いマージを実行
- ユーザー設定で指定されたキーのみが上書きされ、その他はデフォルト値を保持
- エラーが発生した場合、警告をログに記録してデフォルト設定を使用

#### プロジェクトプロファイル（拡張設定）
```json
{
  "project_profiles": {
    "startup": {
      "description": "スタートアップ向けの迅速な開発設定",
      "quality_gates": {
        "test_coverage_threshold": 60,
        "quality_score_threshold": 6.0,
        "max_high_priority_smells": 2
      }
    },
    "enterprise": {
      "description": "エンタープライズ向けの厳格な品質設定",
      "quality_gates": {
        "test_coverage_threshold": 90,
        "quality_score_threshold": 8.0,
        "max_high_priority_smells": 0
      }
    },
    "open_source": {
      "description": "オープンソースプロジェクト向け設定",
      "quality_gates": {
        "test_coverage_threshold": 85,
        "quality_score_threshold": 7.5,
        "max_high_priority_smells": 0
      }
    }
  }
}
```

## 6. Integration Workflow

### パイプライン統合フロー
```
ユーザー入力 ("CI/CDを設定して")
→ IntentDetector (SETUP_CICD)
→ Planner (cicd_setup_plan)
→ ActionExecutor._setup_cicd_pipeline()
→ CICDIntegrator.generate_pipeline()
→ LogManager (結果記録)
→ ResponseGenerator (設定ファイル提示)
```

### 品質ゲート評価フロー
```
CI/CDパイプライン実行 → テスト実行 → カバレッジ測定 →
リファクタリング分析 → 品質ゲート評価 → 結果レポート生成
```

### 複合タスクフロー
```
プロジェクト分析 → パイプライン生成 → 品質ゲート設定 →
設定ファイル生成 → 統合レポート作成
```

この設計により、既存の品質分析機能と統合された包括的なCI/CD自動化システムが実現され、継続的な品質向上と開発効率の改善を支援します。

## 7. Review Notes
- 2026-04-14: 生成フローと品質ゲート統合の記述を現行実装に合わせて再確認。
