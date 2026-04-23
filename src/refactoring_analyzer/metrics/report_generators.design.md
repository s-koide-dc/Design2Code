# RefactoringReportGenerators Design Document

## 1. Purpose
リファクタリング分析の結果を、人間が読みやすい JSON および HTML 形式のレポートとして出力します。

## 2. Structured Specification

### Reporters

#### `RefactoringJSONReporter`
- **Output**: 分析の全データを構造化した JSON ファイル。
- **Logic**: スメル、提案、メトリクス、推奨事項を辞書にまとめ、タイムスタンプを付与して保存。

#### `RefactoringHTMLReporter`
- **Output**: Bootstrap を使用した視覚的な HTML レポート。
- **Logic**: 
    - メトリクスをサマリーとしてカード形式で表示。
    - コードスメルを重要度（赤/黄/緑）に応じたスタイルで一覧表示。
    - 改善提案と推奨アクションをセクションごとにレンダリング。

### Test Cases
- **Happy Path**: 分析結果を渡し、有効な JSON/HTML ファイルが生成されること。
