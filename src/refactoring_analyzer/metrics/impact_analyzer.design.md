# ImpactScopeAnalyzer Design Document

## 1. Purpose
`ImpactScopeAnalyzer` は、提案されたリファクタリングがプロジェクトの他の部分（ファイル、クラス、メソッド）にどのような影響を与えるかを分析し、リスクレベルを判定します。

## 2. Structured Specification

### Input
- **suggestions**: リファクタリング提案のリスト。
- **roslyn_analysis_results** (Optional): C# の場合の構造化解析データ。

### Output
- **impact_report**: 影響を受けるファイル・クラス・メソッドのリスト、リスクレベル（low/medium/high）。

### Core Logic
1.  **直接的影響の特定**: 提案のターゲットとなっているファイル、クラス、メソッドを収集。
2.  **間接的影響のトラバース (C#)**: 
    - Roslyn 解析データ（`calledBy`, `calls`, `accesses`, `accessedBy`, `dependencies`）をフル活用。
    - **BFS（幅優先探索）**: ターゲットから出発し、呼び出し元や依存先を再帰的にキューに追加して訪問済みセット（visited）を構築。
    - クラス内の全メソッド・プロパティの相互依存も考慮した包括的なグラフ探索を実行。
3.  **リスク評価**: 
    - 影響を受けるファイル数（>5）や依存関係数（>10）に基づき、リスクレベル（low/medium/high）を判定。
    - `total_dependencies_identified` をカウントし、変更の「重さ」を数値化。
    - `estimated_test_impact`（テストへの影響度）を算出。

## 3. Dependencies
- **External**: `os`, `typing`
