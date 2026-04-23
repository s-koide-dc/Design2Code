# LogicAuditor Design Document

## 1. Purpose (Updated 2026-02-10)
`LogicAuditor`は、`DesignDocParser`によって構造化された設計データ（仕様）と、実際のソースコードの構造を比較し、論理的な不整合や実装漏れを自動的に検出することを目的とします。これにより、「設計書通りに正しく実装されているか」の監査を自動化します。

## 2. Structured Specification

### Input
- **design_data**: `DesignDocParser` が出力した構造化データ（Dict）。
- **source_structure**: `ASTAnalyzer` または Roslyn解析ツールが出力したコード構造データ（Dict）。

### Output
- **audit_results**: 検出された不整合のリスト。
- **Type/Format**: `Dict`
- **Example**:
  ```json
  {
    "status": "inconsistent",
    "findings": [
      { "type": "missing_parameter", "detail": "Inputで定義されている 'userId' がメソッド引数にありません。" },
      { "type": "logic_gap", "detail": "Core Logicのステップ2 'DB接続' に相当する処理がコード内に見当たりません。" }
    ],
    "consistency_score": 0.75
  }
  ```

### Core Logic
1.  **インターフェース検証**:
    - 設計書の `Input` / `Output` で指定された型や変数が、実装（メソッド引数、戻り値型）に含まれているかチェック。
2.  **ロジック網羅性検証 (Semantic Audit)**:
    - **キーワード抽出**: `Core Logic` の各ステップからキーワード（英語・日本語）を抽出。日本語の場合は `MorphAnalyzer` を使用して形態素解析を行う。
    - **キーワードマッチング**: ソースコード内のシンボルやリテラルと直接比較。
    - **セマンティック・フォールバック**:
        - **Terminology Bridging 2.0 (Dictionary-based)**: `domain_dictionary.json` を使用し、プロジェクト固有の用語（例：「閾値」→ `threshold`）を静的に紐付け。
        - **Vector Fallback**: 辞書にない場合、`VectorEngine` を用いて文章ベクトル間の類似度を計算（閾値 0.7）。
3.  **論理・数値監査 (Logic & Numeric Audit)**:
    - **数値不一致検知**: `Core Logic` 内の数値（例: 「閾値 0.90」）とコード内のリテラルを比較し、欠落があれば `high` レベルの指摘を生成。
    - **不等号監査 (Inequality Audit)**: 
        - 「以上」「以下」「未満」等の日本語表現を演算子（`>=`, `<=`, `<`, `>`）に変換。
        - コード内の数値周辺にある比較演算子をスキャンし、論理的な矛盾（例: 設計は「以上」だがコードは「<」等）を検知。
    - **ブラケットタグ除外**:
        - 設計ステップから `[semantic_roles:...]` 等のブラケットタグを除去してから論理抽出を行う。
    - **演算子フレーズ優先**:
        - 演算子候補文字列に対して、定義済みフレーズの包含を優先して演算子種別を決定する。
4.  **アサーション目標抽出 (`extract_assertion_goals`)**:
    - 設計ステップから数値制約や文字列包含条件を自動抽出し、`ExecutionVerifier` 用の検証プランを生成。
5.  **テスト網羅性検証**:
    - 設計書の `Test Cases` に記載された全シナリオが、既存のテストファイル内に存在するかチェック。
6.  **スコアリング**: 
    - 一致度に基づいて 0.0 〜 1.0 のスコアを算出。数値不一致やパラメータ欠落は大幅な減点対象とする。

### Test Cases
- **Happy Path**:
    - **Scenario**: 設計書と完全に一致する実装を渡した場合、`status: "consistent"` となること。
- **Semantic Match**:
    - **Scenario**: 設計に「閾値」とあり、コードに `threshold` とある。
    - **Expected**: `vector_engine` により関連性が認められ、`consistent` と判定されること。
- **Numeric Mismatch**:
    - **Scenario**: 設計に「0.90」とあり、コードに「0.60」とある。
    - **Expected**: `inconsistent` と判定され、`logic_value_mismatch` Findings が生成されること。

## 3. Dependencies
- **Internal**: `design_doc_parser`, `ast_analyzer`, `vector_engine`, `morph_analyzer`, `resources/domain_dictionary.json`
- **External**: `re`, `json`, `os`, `numpy`, `pathlib`
