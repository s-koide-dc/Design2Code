# QualityMetricsCalculator Design Document (Class: QualityMetricsCalculator)

## 1. Purpose
`QualityMetricsCalculator` は、検出されたスメルやコード統計に基づき、プロジェクトの健全性を数値化（品質スコア、保守性指数、技術的負債）します。

## 2. Structured Specification

### Input
- **code_smells**: 検出されたスメルのリスト。
- **roslyn_data** (Optional): C# のメトリクス情報。

### Output
- **metrics**: 
    - `overall_score`: 10点満点の品質スコア。
    - `maintainability_index`: 保守性指数（20-100）。
    - `technical_debt_hours`: 修正にかかる推定時間。
    - `code_duplication_percentage`: コード重複率（％）。
    - `improvement_potential`: 改善ポテンシャルスコア。

### Core Logic
1.  **品質スコア計算**: 10.0 から、スメルの件数と重要度（High/Medium）に応じた減点方式で算出。
2.  **保守性指数の推定**: スメル数と平均複雑度に基づくヒューリスティックな式を用いて算出。
3.  **技術的負債の見積もり**: スメルのタイプ（GodClassなら4時間等）ごとに定義された基本時間に、重要度倍率を乗じて合計。
4.  **平均複雑度の算出**: 
    - C# の場合は Roslyn の `cyclomaticComplexity` を集計。
    - 他言語はメソッドの行数等を指標として代用。
5.  **レーティング判定**: 総合スコアに基づき、A（9.0以上）から E（4.0未満）までの 5段階でプロジェクト品質を格付け。

## 3. Dependencies
- **External**: `typing`

### Test Cases
- **Scenario**: Happy Path - No Smells
    - **Input**:
      ```json
      {
        "target_method": "calculate",
        "init_args": {"language": "python"},
        "args": {
            "project_path": "/dummy/path",
            "code_smells": []
        }
      }
      ```
    - **Expected**:
      ```json
      {
        "overall_score": 10.0,
        "technical_debt_hours": 0.0
      }
      ```
- **Scenario**: High Severity God Class
    - **Input**:
      ```json
      {
        "target_method": "calculate",
        "init_args": {"language": "python"},
        "args": {
            "project_path": "/dummy/path",
            "code_smells": [
                {"type": "god_class", "severity": "high", "detail": "TestClass"}
            ]
        }
      }
      ```
    - **Expected**:
      ```json
      {
        "overall_score": 8.9,
        "technical_debt_hours": 6.0
      }
      ```

