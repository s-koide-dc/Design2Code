# coverage_analyzer Design Document

## 1. Purpose

`coverage_analyzer`モジュールは、テストカバレッジの測定、分析、レポート生成を統合的に提供し、品質保証の自動化を支援します。既存のTestGeneratorとActionExecutorと連携し、テスト実行からカバレッジ測定、ギャップ分析、改善提案まで一貫したワークフローを実現します。

**主要機能**:
- **多言語カバレッジ測定**: C#（Coverlet）、Python（coverage.py）、JavaScript（Jest）の完全サポート
- **高精度ギャップ分析**: 未カバーファイル・メソッド特定、優先度評価、不足シナリオ分析
- **高度な複雑度計算**: Roslyn解析結果（C#）およびAST解析（Python）を用いた正確なサイクロマティック複雑度の算出
- **包括的レポート生成**: JSON、HTML、テキスト形式での詳細レポート
- **品質メトリクス**: ライン・ブランチ・メソッドカバレッジ、技術的負債評価、保守性指数
- **改善提案エンジン**: 具体的なテスト追加提案、コード品質向上案、工数見積もり
- **言語別テストテンプレート生成**: C#、Python、JavaScriptの各言語に最適化されたテストコードテンプレート自動生成

## 2. Architecture Overview

### 2.1 Core Components

#### CoverageAnalyzer (Main Class)
- **役割**: カバレッジ分析の中心的なコントローラー
- **責任**: 
  - 言語別カバレッジ測定の統合（C#、Python、JavaScript）
  - 分析結果の集約とワークフロー管理
  - レポート生成の統括
  - Roslynデータ等の外部解析情報の統合
  - 設定ファイル（`resources/coverage_config.json`）の読み込みとデフォルト値のマージ
  - ログマネージャーとの連携によるイベント記録

#### Language-Specific Collectors
- **CSharpCoverageCollector**: 
  - Coverlet JSON形式の完全パース
  - `dotnet test`コマンドの実行とカバレッジデータ収集
  - ライン・ブランチ・メソッドカバレッジの詳細計算
  - エラーハンドリング（コマンド失敗時の適切なエラーメッセージ返却）
- **PythonCoverageCollector**: 
  - coverage.py totals形式の解析
  - `py -m coverage run`および`py -m coverage json`の実行
  - missing_lines特定とカバレッジ率計算
  - unittest discover統合
- **JavaScriptCoverageCollector**: 
  - Jest statements/functions形式の処理
  - `jest --coverage`コマンドの実行
  - coverage-final.json解析と未カバー行特定

#### Analysis Engine
- **GapAnalyzer**:
  - **役割**: 言語別未カバー領域特定、複雑度スコア計算、優先度評価
  - **高度な機能**:
    - **C#**: 
      - 外部の `MyRoslynAnalyzer` から提供される `TotalComplexity` メトリクスを利用
      - ファイルパスとRoslynマニフェストのマッチング
      - メソッド単位での未カバー行・メソッド特定
      - 正確な複雑度に基づいたリスク評価
    - **Python**: 
      - 標準 `ast` モジュールを使用したソースコード解析
      - 分岐構造（If, For, While, Try, BoolOp等）から正確な複雑度を計算
      - SyntaxError時のフォールバック処理
    - **JavaScript/その他**: 
      - 正規表現によるキーワードカウント（ヒューリスティック）
      - コメント除去処理による精度向上
  - **優先度評価ロジック**:
    - high: 未カバー行数 > 20 または 複雑度 > 20
    - medium: 未カバー行数 > 5 または 複雑度 > 10
    - low: その他
  - **不足シナリオ特定**:
    - 完全未カバーメソッドの検出（基本動作確認テスト提案）
    - 部分的未カバーメソッドの検出（エッジケーステスト提案）

- **QualityAnalyzer**: 
  - カバレッジトレンド分析（現在は"unknown"、将来的に履歴データ統合予定）
  - 品質スコア計算（ラインカバレッジベース + ギャップペナルティ）
  - 技術的負債評価（high/medium/low分類）
  - 保守性指数（Maintainability Index）計算

- **RecommendationEngine**: 
  - 言語別テストテンプレート生成（C#: xUnit、Python: unittest、JavaScript: Jest）
  - 工数見積もり（low/medium/high）
  - 改善提案優先度付け（未カバーメソッド、不足シナリオ、リファクタリング）
  - 具体的なテスト名とコードスニペット生成

#### Report Generator
- **JSONReporter**: 
  - 機械可読形式でのレポート出力
  - カバレッジ結果、ギャップ分析、品質メトリクス、推奨事項の統合
  - タイムスタンプ付きファイル名生成
- **HTMLReporter**: 
  - 視覚的なカバレッジレポート生成
  - 品質スコア表示
  - 将来的にチャート・グラフ統合予定
- **TextReporter**: 
  - 人間可読なサマリーレポート
  - カバレッジ率とギャップ数の簡潔な表示

### 2.2 Coverage Measurement Process

#### 1. 事前準備フェーズ
- プロジェクト構造の分析
- テストファイルの検出
- 言語固有の設定確認（`_load_coverage_config`）
- デフォルト設定とカスタム設定のマージ
- （オプション）C# Roslyn解析データの受け取り（`options["roslyn_data"]`）
- ログマネージャーへのイベント記録（`coverage_analysis_start`）

#### 2. カバレッジ測定フェーズ（`_measure_coverage`）
- 言語別カバレッジツールの実行
  - C#: `dotnet test /p:CollectCoverage=true /p:CoverletOutputFormat=json`
  - Python: `py -m coverage run -m unittest discover && py -m coverage json`
  - JavaScript: `jest --coverage --coverageReporters=json`
- 測定結果の収集と正規化
- エラーハンドリング（コマンド失敗、ファイル未生成の検出）

#### 3. 分析フェーズ（`_analyze_gaps`）
- カバレッジデータの解析
- **複雑度計算**（`_calculate_complexity`）: 
  - 言語に応じた最適（Roslyn/AST/ヒューリスティック）な方法でファイルごとの複雑度を算出
  - C#: Roslynデータからの`TotalComplexity`抽出
  - Python: AST解析による分岐ノードカウント
  - JavaScript: 正規表現によるキーワードカウント
- 未カバー領域の優先度付け（未カバー行数 × 複雑度スコア）
- 不足テストシナリオの特定（`_identify_missing_scenarios`）
  - 完全未カバーメソッド → 基本動作確認テスト提案
  - 部分的未カバーメソッド → エッジケーステスト提案

#### 4. 品質評価・改善提案（`_analyze_quality`, `_generate_recommendations`）
- 品質メトリクスの計算
  - 品質スコア: `(line_coverage / 10.0) - (uncovered_files * 0.1) - (high_priority_gaps * 0.5)`
  - 技術的負債: high_priority_gaps > 5 → "high"、total_uncovered_files > 5 → "medium"、その他 → "low"
  - 保守性指数: `80 - (total_lines * 0.005) + (line_coverage * 0.2)`
- 改善提案の生成
  - 未カバーメソッドのテスト追加提案（テンプレートコード付き）
  - 不足シナリオのテスト追加提案（テスト名付き）
  - リファクタリング提案（技術的負債が高い場合）
- レポート出力（`_generate_reports`）
  - JSON、HTML、テキスト形式での出力
  - `coverage_reports/`ディレクトリへの保存

## 3. Structured Specification

### 3.1 CoverageAnalyzer.analyze_project

#### Input
- **Description**: カバレッジ測定対象のプロジェクトパスと言語、測定オプション（Roslynデータ含む）
- **Type/Format**: 
  - `project_path` (str): プロジェクトのルートパス
  - `language` (str): "csharp", "python", "javascript"のいずれか
  - `options` (dict, optional): 追加オプション
    - `roslyn_data` (dict, optional): MyRoslynAnalyzerの出力データ
    - `test_path` (str, optional): テストディレクトリパス（Pythonで使用）
    - `output_formats` (list, optional): ["json", "html", "text"]から選択
- **Example**:
  ```json
  {
    "project_path": "src/calculator/",
    "language": "csharp",
    "options": {
      "roslyn_data": {
        "manifest": [{"id": "file1", "filePath": "Calculator.cs"}],
        "objects": [{"id": "file1", "metrics": {"TotalComplexity": 15}}]
      },
      "output_formats": ["json", "html"]
    }
  }
  ```

#### Output
- **Description**: カバレッジ測定結果、分析結果、レポートパスを含む統合結果
- **Type/Format**: dict
- **Success Case**:
  ```json
  {
    "status": "success",
    "project_path": "src/calculator/",
    "language": "csharp",
    "coverage_summary": {
      "line_coverage": 85.5,
      "branch_coverage": 78.2,
      "method_coverage": 90.0,
      "total_lines": 1000,
      "covered_lines": 855
    },
    "gap_analysis": {
      "uncovered_files": [
        {
          "file": "Calculator.cs",
          "uncovered_lines": [15, 23, 45],
          "uncovered_methods": ["Divide", "Modulo"],
          "complexity_score": 15,
          "priority": "high"
        }
      ],
      "missing_test_scenarios": [
        {
          "target_method": "Divide",
          "scenario": "Divide の基本動作確認",
          "suggested_test": "Divide_ShouldReturnResult_WhenValidInput",
          "priority": "high"
        }
      ],
      "analysis_summary": {
        "total_uncovered_files": 1,
        "high_priority_gaps": 1,
        "missing_scenarios_count": 1
      }
    },
    "quality_metrics": {
      "coverage_trend": "unknown",
      "quality_score": 7.5,
      "technical_debt": "medium",
      "maintainability_index": 75
    },
    "recommendations": [
      {
        "type": "add_test",
        "priority": "high",
        "description": "Calculator.csのDivideメソッドのテストを追加してください",
        "suggested_test_code": "[Fact]\npublic void Divide_ShouldReturnExpectedResult_WhenValidInput() { ... }",
        "estimated_effort": "medium"
      }
    ],
    "reports": {
      "json_report": "coverage_reports/coverage_20260206_143022.json",
      "html_report": "coverage_reports/coverage_20260206_143022.html"
    },
    "timestamp": "2026-02-06T14:30:22.123456"
  }
  ```
- **Error Case**:
  ```json
  {
    "status": "error",
    "message": "サポートされていない言語です: ruby"
  }
  ```

#### Core Logic
1. **初期化とログ記録**:
   - `options`のデフォルト値設定（空辞書）
   - `roslyn_data`の抽出
   - ログマネージャーへのイベント記録（`coverage_analysis_start`）

2. **カバレッジ測定**（`_measure_coverage`）:
   - 言語が`self.collectors`に存在するか確認
   - 存在しない場合: エラーメッセージ返却
   - 存在する場合: 対応するコレクターの`collect_coverage`を呼び出し
   - 測定結果の`status`が"success"でない場合: 結果をそのまま返却

3. **ギャップ分析**（`_analyze_gaps`）:
   - `GapAnalyzer`インスタンス生成（言語指定）
   - `analyze`メソッド呼び出し（coverage_data, project_path, roslyn_data渡し）
   - 未カバーファイル・メソッド特定、複雑度計算、優先度評価

4. **品質分析**（`_analyze_quality`）:
   - `QualityAnalyzer`インスタンス生成
   - `analyze`メソッド呼び出し（coverage_data, gap_analysis渡し）
   - 品質スコア、技術的負債、保守性指数の計算

5. **推奨事項生成**（`_generate_recommendations`）:
   - `RecommendationEngine`インスタンス生成（言語指定）
   - `generate`メソッド呼び出し（gap_analysis, quality_metrics渡し）
   - テスト追加提案、リファクタリング提案の生成

6. **レポート生成**（`_generate_reports`）:
   - `output_formats`の取得（デフォルト: ["json", "text"]）
   - タイムスタンプ生成
   - `coverage_reports/`ディレクトリ作成
   - 各フォーマットに応じたレポーター呼び出し
   - レポートファイルパスの収集

7. **結果統合と返却**:
   - すべての分析結果を統合した辞書を作成
   - タイムスタンプ追加
   - 結果返却

8. **例外処理**:
   - すべての処理を`try-except`で囲む
   - 例外発生時: エラーメッセージを含む辞書を返却

### 3.2 GapAnalyzer._calculate_complexity

#### Input
- **Description**: ファイルの絶対パスとオプションのRoslynデータ
- **Type/Format**:
  - `file_path_abs` (str): 解析対象ファイルの絶対パス
  - `roslyn_data` (dict, optional): Roslyn解析結果
- **Example**:
  ```python
  file_path_abs = "/path/to/Calculator.cs"
  roslyn_data = {
    "manifest": [{"id": "file1", "filePath": "/path/to/Calculator.cs"}],
    "objects": [{"id": "file1", "metrics": {"TotalComplexity": 15}}]
  }
  ```

#### Output
- **Description**: ファイルの複雑度スコア（整数）
- **Type/Format**: int
- **Example**: `15` (C# with Roslyn), `8` (Python AST), `5` (JavaScript heuristic)

#### Core Logic
1. **C#かつRoslynデータあり**:
   - `_get_complexity_from_roslyn`を呼び出し
   - Roslynデータから複雑度を抽出して返却

2. **ファイル存在確認**:
   - ファイルが存在しない場合: `1`を返却

3. **ファイル読み込み**:
   - UTF-8エンコーディングでファイルを開く
   - エラー無視モード（`errors='ignore'`）

4. **Python言語の場合**:
   - `ast.parse(content)`で構文木を構築
   - 初期複雑度を`1`に設定
   - `ast.walk(tree)`でノードを巡回:
     - `If`, `While`, `For`, `AsyncFor`, `With`, `AsyncWith`, `Try`, `ExceptHandler`: 複雑度+1
     - `BoolOp`: 複雑度 + (values数 - 1)
   - 計算した複雑度を返却
   - `SyntaxError`の場合: `_heuristic_complexity`にフォールバック

5. **その他の言語**:
   - `_heuristic_complexity(content)`を呼び出し

6. **例外処理**:
   - すべての例外をキャッチして`1`を返却

### 3.3 GapAnalyzer._get_complexity_from_roslyn

#### Input
- **Description**: ファイルパスとRoslynデータ
- **Type/Format**:
  - `file_path_abs` (str): ファイルの絶対パス
  - `roslyn_data` (dict): Roslyn解析結果
- **Example**: 上記と同じ

#### Output
- **Description**: Roslynから取得した複雑度スコア
- **Type/Format**: int
- **Example**: `15`

#### Core Logic
1. **初期化**:
   - `total_complexity = 0`
   - `file_found = False`
   - `target_ids = []`

2. **マニフェスト検索**:
   - `roslyn_data["manifest"]`を走査
   - 各エントリの`filePath`を正規化（`os.path.normpath`）
   - `file_path_abs`と一致する場合:
     - エントリの`id`を`target_ids`に追加
     - `file_found = True`

3. **ファイル未発見の場合**:
   - `1`を返却

4. **オブジェクト検索**:
   - `roslyn_data["objects"]`を走査
   - オブジェクトの`id`が`target_ids`に含まれる場合:
     - `metrics["TotalComplexity"]`を取得（デフォルト: 0）
     - `total_complexity`に加算

5. **結果返却**:
   - `max(1, total_complexity)`を返却（最小値1保証）

### 3.4 GapAnalyzer._heuristic_complexity

#### Input
- **Description**: ファイルの内容（文字列）
- **Type/Format**: str
- **Example**: `"if (x > 0) { return x; } else { return -x; }"`

#### Output
- **Description**: ヒューリスティックな複雑度スコア
- **Type/Format**: int
- **Example**: `3` (if, else, return等のキーワードカウント)

#### Core Logic
1. **初期化**:
   - `complexity = 1`
   - キーワードパターンリスト定義:
     - `\bif\b`, `\bwhile\b`, `\bfor\b`, `\bforeach\b`
     - `\bcase\b`, `\bdefault\b`, `\bcatch\b`
     - `&&`, `||`, `??`

2. **コメント除去**:
   - 各行を`//`で分割し、前半部分のみ取得
   - 改行で結合して`clean_content`を作成

3. **キーワードカウント**:
   - 各パターンに対して`re.findall`を実行
   - マッチ数を`complexity`に加算

4. **結果返却**:
   - 計算した複雑度を返却

### 3.5 RecommendationEngine.generate

#### Input
- **Description**: ギャップ分析結果と品質メトリクス
- **Type/Format**:
  - `gap_analysis` (dict): 未カバーファイル、不足シナリオ等
  - `quality_metrics` (dict): 品質スコア、技術的負債等
- **Example**: 上記の`analyze_project`の出力参照

#### Output
- **Description**: 改善提案のリスト
- **Type/Format**: list of dict
- **Example**:
  ```json
  [
    {
      "type": "add_test",
      "priority": "high",
      "description": "Calculator.csのDivideメソッドのテストを追加してください",
      "suggested_test_code": "[Fact]\npublic void Divide_ShouldReturnExpectedResult_WhenValidInput() { ... }",
      "estimated_effort": "medium"
    },
    {
      "type": "add_scenario_test",
      "priority": "medium",
      "description": "Divideのエッジケースシナリオのテストを追加してください",
      "suggested_test_name": "Divide_ShouldHandleEdgeCase",
      "estimated_effort": "low"
    },
    {
      "type": "refactor",
      "priority": "high",
      "description": "技術的負債が高いため、コードのリファクタリングを検討してください",
      "estimated_effort": "high"
    }
  ]
  ```

#### Core Logic
1. **初期化**:
   - `recommendations = []`

2. **未カバーメソッドのテスト追加提案**:
   - `gap_analysis["uncovered_files"]`を走査
   - 各ファイルの`uncovered_methods`を走査
   - 各メソッドに対して:
     - `_generate_test_template`でテストコード生成
     - 提案辞書を作成（type="add_test", priority=ファイルの優先度, description, suggested_test_code, estimated_effort="medium"）
     - `recommendations`に追加

3. **不足シナリオのテスト追加提案**:
   - `gap_analysis["missing_test_scenarios"]`を走査
   - 各シナリオに対して:
     - 提案辞書を作成（type="add_scenario_test", priority=シナリオの優先度, description, suggested_test_name, estimated_effort="low"）
     - `recommendations`に追加

4. **品質改善提案**:
   - `quality_metrics["technical_debt"]`が"high"の場合:
     - リファクタリング提案辞書を作成（type="refactor", priority="high", description, estimated_effort="high"）
     - `recommendations`に追加

5. **結果返却**:
   - `recommendations`リストを返却

### 3.6 RecommendationEngine._generate_test_template

#### Input
- **Description**: メソッド名とファイル名
- **Type/Format**:
  - `method_name` (str): テスト対象メソッド名
  - `file_name` (str): ファイル名（パス含む）
- **Example**: `method_name="Divide"`, `file_name="src/Calculator.cs"`

#### Output
- **Description**: 言語別テストテンプレートコード
- **Type/Format**: str
- **Example** (C#):
  ```csharp
  [Fact]
  public void Divide_ShouldReturnExpectedResult_WhenValidInput()
  {
      // Arrange
      var target = new Calculator();
      
      // Act
      var result = target.Divide();
      
      // Assert
      Assert.NotNull(result);
  }
  ```

#### Core Logic
1. **C#の場合**:
   - xUnit形式のテストテンプレート生成
   - `[Fact]`属性
   - AAA（Arrange-Act-Assert）パターン
   - ファイル名から`Path(file_name).stem`でクラス名抽出
   - `Assert.NotNull(result)`でアサーション

2. **Pythonの場合**:
   - unittest形式のテストテンプレート生成
   - メソッド名を小文字化（`test_{method_name.lower()}_...`）
   - AAA（Arrange-Act-Assert）パターン
   - `self.assertIsNotNone(result)`でアサーション

3. **その他（JavaScript）の場合**:
   - Jest形式のテストテンプレート生成
   - `test('...')`構文
   - AAA（Arrange-Act-Assert）パターン
   - `expect(result).toBeDefined()`でアサーション

4. **結果返却**:
   - 生成したテンプレート文字列を返却

### Test Cases

#### TC1: C# Roslyn統合テスト
- **Scenario**: Roslynデータを使用したC#プロジェクトのカバレッジ分析
- **Input**:
  - `project_path`: "tests/fixtures/csharp_project"
  - `language`: "csharp"
  - `options`: {"roslyn_data": {"manifest": [...], "objects": [...]}}
- **Expected Output**:
  - `status`: "success"
  - `gap_analysis["uncovered_files"][0]["complexity_score"]`: Roslynの`TotalComplexity`値と一致
  - `recommendations`: 未カバーメソッドのテスト追加提案を含む

#### TC2: Python AST複雑度計算テスト
- **Scenario**: ネストされたループと条件分岐を持つPythonファイルの解析
- **Input**:
  - Pythonファイル内容: 
    ```python
    def complex_function(x):
        if x > 0:
            for i in range(x):
                if i % 2 == 0:
                    return i
        return -1
    ```
- **Expected Output**:
  - 複雑度: `4` (if x2, for x1, 基本複雑度 x1)

#### TC3: JavaScript ヒューリスティック複雑度テスト
- **Scenario**: JavaScriptファイルのキーワードベース複雑度計算
- **Input**:
  - JavaScriptファイル内容:
    ```javascript
    function test(x) {
        if (x > 0 && x < 10) {
            for (let i = 0; i < x; i++) {
                console.log(i);
            }
        }
    }
    ```
- **Expected Output**:
  - 複雑度: `4` (if x1, && x1, for x1, 基本複雑度 x1)

#### TC4: エラーハンドリングテスト
- **Scenario**: サポートされていない言語の指定
- **Input**:
  - `project_path`: "tests/fixtures/ruby_project"
  - `language`: "ruby"
- **Expected Output**:
  - `status`: "error"
  - `message`: "サポートされていない言語です: ruby"

#### TC5: カバレッジ測定失敗テスト
- **Scenario**: dotnet testコマンドの失敗
- **Input**:
  - `project_path`: "tests/fixtures/invalid_csharp_project"
  - `language`: "csharp"
- **Expected Output**:
  - `status`: "error"
  - `message`: "dotnet test failed: ..." (stderr内容を含む)

#### TC6: 推奨事項生成テスト
- **Scenario**: 高い技術的負債を持つプロジェクトの分析
- **Input**:
  - `gap_analysis`: {"uncovered_files": [...], "analysis_summary": {"high_priority_gaps": 10}}
  - `quality_metrics`: {"technical_debt": "high"}
- **Expected Output**:
  - `recommendations`: リファクタリング提案を含む（type="refactor", priority="high"）

#### TC7: レポート生成テスト
- **Scenario**: JSON、HTML、テキスト形式でのレポート生成
- **Input**:
  - `options`: {"output_formats": ["json", "html", "text"]}
- **Expected Output**:
  - `reports["json_report"]`: "coverage_reports/coverage_YYYYMMDD_HHMMSS.json"が存在
  - `reports["html_report"]`: "coverage_reports/coverage_YYYYMMDD_HHMMSS.html"が存在
  - ファイルが実際に作成されていること

## 4. Consumers
- **action_executor**: カバレッジ分析操作を呼び出し、テスト実行後のカバレッジ測定を統合
- **test_generator**: テスト生成後のカバレッジ検証、ギャップ分析に基づく追加テスト生成の判断
- **autonomous_learning**: カバレッジデータを学習データとして活用、テスト品質の改善パターン学習

## 5. Dependencies

- **Internal**: 
  - `action_executor`: カバレッジ測定コマンドの実行
  - `test_generator`: テスト生成との連携
  - `log_manager`: イベントログ記録（coverage_analysis_start, coverage_config_error等）
- **External**: 
  - `subprocess`: 外部カバレッジツールの実行
  - `json`: カバレッジデータの読み書き
  - `os`: ファイルシステム操作、パス正規化
  - `re`: 正規表現によるキーワードマッチング
  - `datetime`: タイムスタンプ生成
  - `pathlib`: ファイルパス操作
  - `ast`: Python構文木解析（複雑度計算）
- **Language Tools**: 
  - C#: `dotnet` CLI（Coverlet package必須）
  - Python: `coverage` package（`pip install coverage`）
  - JavaScript: `jest` with coverage support（`npm install --save-dev jest`）

## 6. Configuration

### 6.1 Configuration File Location
- **Path**: `resources/coverage_config.json`
- **Format**: JSON

### 6.2 Configuration Structure
```json
{
  "csharp": {
    "tool": "coverlet",
    "command_template": "dotnet test /p:CollectCoverage=true /p:CoverletOutputFormat=json /p:CoverletOutput={output_path}",
    "exclude_patterns": ["**/bin/**", "**/obj/**", "**/*.Tests/**"],
    "thresholds": {
      "line": 80,
      "branch": 70,
      "method": 90
    }
  },
  "python": {
    "tool": "coverage",
    "command_template": "coverage run -m pytest {test_path} && coverage json -o {output_path}",
    "exclude_patterns": ["**/venv/**", "**/__pycache__/**", "**/test_*.py"],
    "thresholds": {
      "line": 85,
      "branch": 75
    }
  },
  "javascript": {
    "tool": "jest",
    "command_template": "jest --coverage --coverageReporters=json --coverageDirectory={output_path}",
    "exclude_patterns": ["**/node_modules/**", "**/dist/**", "**/*.test.js"],
    "thresholds": {
      "line": 80,
      "branch": 70,
      "function": 85
    }
  }
}
```

### 6.3 Configuration Loading Logic
1. デフォルト設定を定義（上記構造）
2. `resources/coverage_config.json`の存在確認
3. ファイルが存在する場合:
   - JSONファイルを読み込み
   - 言語ごとにデフォルト設定とマージ（`update`メソッド使用）
4. ファイルが存在しない、または読み込みエラーの場合:
   - ログマネージャーに警告記録（`coverage_config_error`）
   - デフォルト設定を使用
5. マージされた設定を返却

## 7. Integration Workflow

### 7.1 Test Generation → Coverage Analysis Flow
1. **TestGenerator**: 新規テスト生成
2. **ActionExecutor**: テスト実行
3. **CoverageAnalyzer**: カバレッジ測定
4. **GapAnalyzer**: 未カバー領域特定
5. **RecommendationEngine**: 追加テスト提案
6. **TestGenerator**: 提案に基づく追加テスト生成（ループ）

### 7.2 CI/CD Integration Flow
1. **CI/CD Trigger**: コミット、プルリクエスト
2. **Build**: プロジェクトビルド
3. **Test Execution**: 全テスト実行
4. **CoverageAnalyzer**: カバレッジ測定・分析
5. **Report Generation**: JSON/HTMLレポート生成
6. **Threshold Check**: 設定された閾値との比較
7. **Pass/Fail Decision**: 閾値未達の場合はビルド失敗

### 7.3 Roslyn Integration Flow (C# Only)
1. **MyRoslynAnalyzer**: C#プロジェクトの静的解析実行
2. **Roslyn Output**: `TotalComplexity`等のメトリクス生成
3. **CoverageAnalyzer**: Roslynデータを`options["roslyn_data"]`として受け取り
4. **GapAnalyzer**: Roslynの複雑度データを使用した高精度ギャップ分析
5. **RecommendationEngine**: 複雑度に基づく優先度付き改善提案

### 7.4 Autonomous Learning Integration
1. **CoverageAnalyzer**: カバレッジデータ生成
2. **AutonomousLearning**: カバレッジデータを学習データとして収集
3. **Pattern Recognition**: 高カバレッジテストのパターン学習
4. **TestGenerator**: 学習パターンに基づくテスト生成改善

## 8. Error Handling

### 8.1 Command Execution Errors
- **Scenario**: `dotnet test`, `coverage run`, `jest`コマンドの失敗
- **Detection**: `subprocess.run`の`returncode`チェック
- **Response**: 
  - エラーメッセージ（stderr）を含む辞書返却
  - `{"status": "error", "message": "dotnet test failed: ..."}`
  - ログマネージャーへのエラー記録

### 8.2 File Not Found Errors
- **Scenario**: カバレッジ出力ファイルが生成されない
- **Detection**: `os.path.exists`チェック
- **Response**: 
  - `{"status": "error", "message": "Coverage file not generated"}`
  - ログマネージャーへのエラー記録

### 8.3 JSON Parse Errors
- **Scenario**: カバレッジJSONファイルの解析失敗
- **Detection**: `json.load`の例外キャッチ
- **Response**: 
  - `{"status": "error", "message": "Failed to parse coverage data: ..."}`
  - ログマネージャーへのエラー記録

### 8.4 AST Parse Errors (Python)
- **Scenario**: Python構文エラーによるAST解析失敗
- **Detection**: `ast.parse`の`SyntaxError`キャッチ
- **Response**: 
  - ヒューリスティック複雑度計算にフォールバック
  - 警告ログ記録（オプション）

### 8.5 Unsupported Language Errors
- **Scenario**: サポートされていない言語の指定
- **Detection**: `language not in self.collectors`チェック
- **Response**: 
  - `{"status": "error", "message": "サポートされていない言語です: {language}"}`
  - 即座に返却（処理継続なし）

## 9. Performance Considerations

### 9.1 Large Project Optimization
- **Issue**: 大規模プロジェクトでのカバレッジ測定時間
- **Solution**: 
  - 並列テスト実行（`dotnet test --parallel`等）
  - 増分カバレッジ測定（変更ファイルのみ）
  - キャッシュ機構（前回測定結果の再利用）

### 9.2 Complexity Calculation Optimization
- **Issue**: 多数のファイルに対する複雑度計算のオーバーヘッド
- **Solution**: 
  - Roslynデータの優先使用（C#）
  - AST解析結果のキャッシュ（Python）
  - 並列処理（複数ファイルの同時解析）

### 9.3 Report Generation Optimization
- **Issue**: 大量のレポートデータの生成・保存
- **Solution**: 
  - ストリーミング書き込み（大規模JSON）
  - 圧縮レポート（gzip）
  - 古いレポートの自動削除（保持期間設定）

## 10. Future Enhancements

### 10.1 Coverage Trend Analysis
- **Current**: `coverage_trend`は常に"unknown"
- **Enhancement**: 
  - 履歴データベース構築
  - 時系列カバレッジ推移の可視化
  - トレンド予測（機械学習）

### 10.2 Advanced Visualization
- **Current**: 基本的なHTMLレポート
- **Enhancement**: 
  - インタラクティブなカバレッジマップ
  - ヒートマップ表示
  - ドリルダウン機能

### 10.3 Multi-Language Project Support
- **Current**: 単一言語プロジェクトのみ
- **Enhancement**: 
  - 複数言語混在プロジェクトの統合カバレッジ
  - 言語間依存関係の考慮
  - 統合レポート生成

### 10.4 AI-Powered Test Generation
- **Current**: テンプレートベースのテスト提案
- **Enhancement**: 
  - LLMを使用した高度なテスト生成
  - コンテキスト理解に基づくテストケース提案
  - 自動テスト実装・検証