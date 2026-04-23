# RefactoringSuggestionEngine Design Document

## 1. Purpose
`RefactoringSuggestionEngine` は、検出されたコードスメル（長いメソッド等）に対し、具体的な解決策（メソッド抽出、クラス分割等）を立案します。

## 2. Structured Specification

### Input
- **code_smells**: 検出されたスメルのリスト。
- **options**: 最大提案数等のオプション。

### Output
- **suggestions**: 具体的な修正アクションを含む提案リスト。

### Core Logic
1.  **スメル別の戦略立案**:
    - **LongMethod**: メソッド抽出 (`extract_method`) を提案。新メソッド名の候補と見積工数を提示。
    - **DuplicateCode**: 共通メソッド抽出 (`extract_common_method`) を提案。
    - **ComplexCondition**: 変数分割による簡素化 (`simplify_condition`) を提案。
    - **GodClass**: 責任ごとのクラス分割 (`split_class`) を提案。
2.  **言語特有の考慮**:
    - Python では `ast` モジュール、JavaScript では基底分析器、C# では Roslyn データをそれぞれ参照し、最適な修正範囲を特定。
3.  **ランキング**: 重要度と優先度に基づいてソートし、上位件数（デフォルト 10件）に絞り込み。
4.  **影響分析の付与**: 各提案に対し、テストへの影響範囲や安全レベルを付記。

## 3. Dependencies
- **External**: `typing`
