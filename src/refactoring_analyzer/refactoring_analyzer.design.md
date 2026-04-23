# RefactoringAnalyzer Design Document

## 1. Purpose (Updated 2026-04-14)

`refactoring_analyzer`モジュールは、コードの品質向上を支援するため、コードスメルの検出、リファクタリング提案、品質メトリクスの計算を統合的に提供します。MyRoslynAnalyzerとの完全統合により、C#プロジェクトの深いAST解析を実現し、既存のCoverageAnalyzerと連携した包括的なコード改善支援を提供します。

**主要機能**:
- **高精度コードスメル検出**: MyRoslynAnalyzer統合による4種類のスメル検出（長いメソッド、重複コード、複雑条件、神クラス）
- **依存グラフ解析**: 影響範囲分析、リスク評価、テスト影響度計算
- **リファクタリング提案エンジン**: メソッド抽出、共通化、条件簡素化、クラス分割の具体的提案
- **品質メトリクス**: 総合品質スコア、保守性指数、技術的負債時間、改善ポテンシャル評価
- **プロファイル機能**: プロジェクト別設定、除外ルール、安全性チェック
- **包括的レポート**: JSON・HTML形式での詳細分析レポート

## 2. Architecture Overview

本モジュールは責任範囲を明確にするため、以下の3つのサブパッケージで構成されます：

1.  **Analyzers (`analyzers/`)**: 言語別のコード解析を担当。
    - `BaseRefactoringAnalyzer`: 共通の走査・除外ロジック。
    - `CSharpRefactoringAnalyzer`: Roslyn 連携による C# 解析。
    - `PythonRefactoringAnalyzer`: Python AST 解析。
    - `JavaScriptRefactoringAnalyzer`: ESLint 連携解析。
2.  **Detectors (`detectors/`)**: 具体的なコードスメルの検出アルゴリズム（Long Method, Duplicate Code 等）。
3.  **Metrics & Suggestions (`metrics/`)**:
    - `QualityMetricsCalculator`: 総合品質スコアの算出。
    - `RefactoringSuggestionEngine`: 改善策の提示。
    - `ImpactScopeAnalyzer`: 変更による影響範囲の特定。
    - `RefactoringJSONReporter/HTMLReporter`: レポート出力。

### 2.1 Core Components (Refactored)

#### RefactoringAnalyzer (Coordinator)
- **役割**: リファクタリング分析の中核コーディネーター。
- **責任**: 言語別分析器（Analyzers）の切り替え、および分析結果に対するメトリクス算出・提案生成（Metrics）のオーケストレーション。

#### Language-Specific Analyzers
- **CSharpRefactoringAnalyzer**: C#特化。`ActionExecutor` を通じて `MyRoslynAnalyzer` を呼び出し、知識グラフベースの詳細な分析を実行。
- **PythonRefactoringAnalyzer**: Python特化。標準ライブラリの `ast` や `pylint` 等の外部ツールを統合。
- **JavaScriptRefactoringAnalyzer**: JavaScript/TypeScript特化。`ESLint` 等の外部リンターを統合。

#### Specialized Engines & Calculators
- **RefactoringSuggestionEngine**: 検出されたコードスメルに基づき、言語固有のリファクタリング手法（メソッド抽出、変数リネーム等）を提案。
- **QualityMetricsCalculator**: 保守性指数（Maintainability Index）、複雑度、技術的負債時間、総合品質スコア等の計量的評価。
- **ImpactScopeAnalyzer**: 知識グラフや解析結果を用いて、変更時の直接的・間接的な影響範囲を特定。
- **RecommendationEngine**: 分析結果を総合し、修正の優先順位付けと具体的なアクションプラン（実行推奨事項）を生成。

#### Code Smell Detectors
- **LongMethodDetector**: メソッド長（行数）と複雑度に基づく検出。
    - **カウントロジック**: 空行を除くすべての行（コメント行を含む）をカウント対象とする。これは、過度なコメントもコードの保守性や可読性に影響を与えるためである。
    - **Roslyn統合**: `MyRoslynAnalyzer` から提供される `lineCount` メトリクスを直接使用する。
- **DuplicateCodeDetector**: `bodyHash` 等を用いたコード重複の特定。
- **ComplexConditionDetector**: 条件分岐の深さや論理演算子の多用を検出。
- **GodClassDetector**: 責務過多な巨大クラスを検出。

### 2.2 Code Smell Detection Process

#### 1. 静的解析フェーズ
- ソースコードのAST解析
- メトリクス収集（行数、複雑度、依存関係）
- パターンマッチングによるスメル検出

#### 2. 品質評価フェーズ
- 各スメルの重要度評価
- 修正コストと効果の見積もり
- 優先度付けアルゴリズムの適用

#### 3. 提案生成フェーズ
- リファクタリング手法の選択
- 具体的なコード例の生成
- 影響範囲の分析

#### 4. 検証フェーズ
- 提案の安全性確認
- テストカバレッジとの整合性チェック
- 自動適用可能性の判定

### 2.3 Integration Points

#### CoverageAnalyzer統合
- カバレッジデータとスメル検出の組み合わせ
- テストされていないコードの優先的なリファクタリング
- リファクタリング後のカバレッジ影響予測

#### MyRoslynAnalyzer統合
- C#の詳細なAST情報の活用
- 依存関係グラフとの連携
- 影響範囲の正確な特定

#### ActionExecutor統合
- リファクタリング提案の実行
- 段階的な適用とロールバック
- ユーザー承認ワークフロー

## 3. Structured Specification

### Input

- **Description**: リファクタリング分析対象のプロジェクトパスと言語、分析オプション
- **Type/Format**: `dict`
- **Example**:
  ```json
  {
    "project_path": "src/calculator/",
    "language": "csharp",
    "analysis_options": {
      "smell_types": ["long_method", "duplicate_code", "complex_condition"],
      "severity_threshold": "medium",
      "include_auto_fix": true,
      "max_suggestions": 10
    },
    "coverage_data": {
      "line_coverage": 85.5,
      "uncovered_files": ["Calculator.cs"]
    }
  }
  ```

### Output

- **Description**: 検出されたコードスメル、リファクタリング提案、品質メトリクスを含む分析結果
- **Type/Format**: `dict`
- **Example**:
  ```json
  {
    "status": "success",
    "project_path": "src/calculator/",
    "language": "csharp",
    "analysis_summary": {
      "total_smells": 12,
      "high_priority": 3,
      "medium_priority": 6,
      "low_priority": 3,
      "auto_fixable": 4
    },
    "code_smells": [
      {
        "type": "long_method",
        "severity": "high",
        "file": "Calculator.cs",
        "method": "ComplexCalculation",
        "line_start": 45,
        "line_end": 120,
        "metrics": {
          "line_count": 75,
          "cyclomatic_complexity": 12,
          "parameter_count": 8
        },
        "description": "メソッドが長すぎます（75行）。推奨は20行以下です。",
        "impact": "可読性とテスト容易性が低下しています。"
      }
    ],
    "refactoring_suggestions": [
      {
        "id": "extract_method_001",
        "type": "extract_method",
        "priority": "high",
        "target": {
          "file": "Calculator.cs",
          "method": "ComplexCalculation",
          "lines": "45-65"
        },
        "suggestion": {
          "new_method_name": "ValidateInputParameters",
          "description": "入力パラメータの検証ロジックを別メソッドに抽出",
          "estimated_effort": "15分",
          "safety_level": "safe"
        },
        "code_example": {
          "before": "public decimal ComplexCalculation(decimal a, decimal b, ...) {\n    if (a < 0) throw new ArgumentException(...);\n    if (b < 0) throw new ArgumentException(...);\n    // ... 20行の検証コード\n}",
          "after": "public decimal ComplexCalculation(decimal a, decimal b, ...) {\n    ValidateInputParameters(a, b, ...);\n    // ... 計算ロジック\n}\n\nprivate void ValidateInputParameters(decimal a, decimal b, ...) {\n    if (a < 0) throw new ArgumentException(...);\n    if (b < 0) throw new ArgumentException(...);\n    // ... 検証ロジック\n}"
        },
        "auto_fixable": true,
        "impact_analysis": {
          "affected_files": ["Calculator.cs"],
          "test_impact": "既存テストは影響なし",
          "coverage_change": "+5% (新メソッドのテスト追加推奨)"
        }
      }
    ],
    "quality_metrics": {
      "overall_score": 7.2,
      "maintainability_index": 68,
      "average_complexity": 4.8,
      "technical_debt_hours": 12.5,
      "code_duplication_percentage": 8.3,
      "improvement_potential": "medium"
    },
    "recommendations": [
      {
        "category": "immediate_action",
        "priority": "high",
        "description": "3つの長いメソッドを優先的にリファクタリングしてください",
        "estimated_impact": "保守性指数 +15ポイント向上"
      },
      {
        "category": "preventive_measure",
        "priority": "medium",
        "description": "コードレビューガイドラインにメソッド長制限を追加",
        "estimated_impact": "将来の技術的負債蓄積を50%削減"
      }
    ],
    "reports": {
      "detailed_report": "refactoring_reports/analysis_20260120_164700.html",
      "summary_report": "refactoring_reports/summary_20260120_164700.json"
    }
  }
  ```

### Core Logic

#### 1. 初期化と設定
- プロジェクト構造の分析
- 言語固有の設定読み込み
- 分析ツールの可用性確認

#### 2. コードスメル検出
- 各検出器の並列実行
- メトリクス収集と閾値比較
- スメルの重要度評価

#### 3. リファクタリング提案生成
- 検出されたスメルに対する提案生成
- コード例の自動生成
- 安全性と効果の評価

#### 4. 品質メトリクス計算
- 複雑度指標の計算
- 技術的負債の定量化
- 改善ポテンシャルの評価

#### 5. 影響範囲分析
- 依存関係グラフの構築
- 変更影響の予測
- テストカバレッジとの整合性確認

#### 6. レポート生成
- 詳細分析レポートの作成
- 実行可能なアクションプランの提示
- 進捗追跡用メトリクスの出力

### Test Cases

#### MyRoslynAnalyzer統合テスト
- **Scenario**: C#プロジェクトの完全AST解析
- **Input**: `{"project_path": "tests/fixtures/sample_csharp/", "language": "csharp"}`
- **Expected Output**: manifest.json解析、details_by_id処理、4種類のスメル検出

#### 長いメソッド検出テスト（Roslyn）
- **Scenario**: startLine/endLineからの正確な行数計算
- **Input**: MyRoslynAnalyzerのMethod詳細
- **Expected Output**: 閾値超過メソッドの検出、severity評価

#### 重複コード検出テスト（bodyHash）
- **Scenario**: bodyHashベースの重複メソッド特定
- **Input**: 同一bodyHashを持つ複数メソッド
- **Expected Output**: 決定論的な重複報告（ID順ソート）

#### 神クラス検出テスト
- **Scenario**: クラス行数・メソッド数による評価
- **Input**: 大規模クラスのRoslyn解析結果
- **Expected Output**: 閾値超過クラスの検出、メトリクス詳細

#### 影響範囲分析テスト
- **Scenario**: 依存グラフトラバーサル
- **Input**: calls/calledBy/accesses関係
- **Expected Output**: 影響ファイル・クラス・メソッド特定、リスクレベル評価

#### 品質メトリクス計算テスト
- **Scenario**: 総合品質スコア・技術的負債時間計算
- **Input**: 検出されたスメル一覧
- **Expected Output**: 10点満点スコア、修正時間見積もり

#### リファクタリング提案テスト
- **Scenario**: 言語別テンプレート生成
- **Input**: 各種スメル情報
- **Expected Output**: C#/Python/JavaScript形式の具体的提案

#### プロファイル適用テスト
- **Scenario**: プロジェクト別設定の適用
- **Input**: プロファイル名と設定
- **Expected Output**: 設定マージ、除外ルール適用

#### エラーハンドリングテスト
- **Scenario**: ActionExecutor未設定、Roslyn解析失敗
- **Input**: 無効な設定・環境
- **Expected Output**: 適切なエラーメッセージ、LogManager記録

## 4. Consumers
- **action_executor**: Invokes refactoring analysis operations.

## 4. Dependencies

- **Internal**: `coverage_analyzer`, `action_executor`, `log_manager`
- **External**: `ast`, `re`, `json`, `os`, `subprocess`, `pathlib`
- **Language Tools**:
  - C#: MyRoslynAnalyzer、dotnet CLI
  - Python: ast module、pylint、flake8
  - JavaScript: ESLint、Babel parser

## 5. Configuration

### リファクタリング設定ファイル (`resources/refactoring_config.json`)
```json
{
  "csharp": {
    "smell_thresholds": {
      "long_method_lines": 20,
      "cyclomatic_complexity": 10,
      "parameter_count": 5,
      "class_line_count": 300
    },
    "auto_fix_enabled": ["rename_variable", "extract_constant"],
    "safety_checks": ["test_coverage", "dependency_analysis"]
  },
  "python": {
    "smell_thresholds": {
      "long_method_lines": 25,
      "cyclomatic_complexity": 8,
      "parameter_count": 4
    },
    "tools": ["pylint", "flake8", "bandit"]
  },
  "javascript": {
    "smell_thresholds": {
      "long_function_lines": 15,
      "cyclomatic_complexity": 6,
      "parameter_count": 3
    },
    "tools": ["eslint", "jshint"]
  }
}
```

## 6. Integration Workflow

### パイプライン統合フロー
```
ユーザー入力 ("コードをリファクタリングして")
→ IntentDetector (ANALYZE_REFACTORING)
→ Planner (refactoring_analysis_plan)
→ ActionExecutor._analyze_refactoring()
→ RefactoringAnalyzer.analyze_project()
→ LogManager (結果記録)
→ ResponseGenerator (提案提示)
```

### CoverageAnalyzer連携フロー
```
カバレッジ分析 → リファクタリング分析 →
統合評価 → 優先度付け → 改善計画生成
```

この設計により、既存システムと統合された包括的なリファクタリング支援システムが実現され、開発者の生産性と コード品質の継続的な向上を支援します。

## 7. Review Notes
- 2026-04-14: 分析フローと統合ポイントの記述を現行実装に合わせて再確認。
