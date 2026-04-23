# CodeFixSuggestionEngine Design Document

## 1. Purpose
`CodeFixSuggestionEngine` (通称 `FixEngine`) は、テスト失敗分析結果や整合性監査結果に基づき、実装コードまたはテストコードに対する具体的な修正案を生成する責任を負います。

## 2. Structured Specification

### Input
- **analysis**: `TestFailureAnalyzer` による失敗分析、または `LogicAuditor` による監査結果（Dict）。
- **target_code**: 修正対象のソースコード情報（ファイルパス、現在の実装内容など）。

### Output
- **suggestions**: `CodeFixSuggestion` オブジェクトのリスト（コード修正提案、または設計書へのバックポート提案を含む）。

### Core Logic
1.  **監査結果の優先処理**: 入力に `findings` が含まれる場合、`logic_gap`（実装漏れ）に対する修正を優先生成。
2.  **ロジックスタブ生成 (`_generate_missing_logic_fix`)**: 
    - 言語（C#, Python）を自動判定。
    - **C#**: `return` 文の前、またはメソッド/クラスの閉じ括弧 `}` の前に `// TODO` を挿入。
3.  **C# 構文エラー修復 (`fix_syntax_error`)**: 
    - **動的な型修復**: CS1503（型変換エラー）において、メッセージから現在の型と期待される型を抽出し、型引数の修正やキャストの挿入を行う。
    - **シンボル解決**: CS0246（型不足）において、未定義の型名（`T` 等）を `object` に置換する、または `using` 句を自動追加する。
    - **非同期補完**: CS4033（awaitエラー）において、メソッドに `async Task` を自動付与する。
4.  **テスト期待値修正 (`self_healing_test`)**: 実際値（Actual）に基づきアサーションを自動更新。
5.  **テストArrange修正 (`test_arrange_fix`)**: 
    - 「戻り値が一致しない」等のエラーに対し、Mockのセットアップ（`Returns(...)`）を自動修正。
6.  **設計への逆同期 (Back-porting)**: 
    - 不整合に対し、コード側が正しいと仮定した「設計書更新案」を生成。
7.  **安全性評価**: `SafetyValidator` を用いて、`syntax_fix` や `test_self_healing` 以外のリスクを厳密に評価。

### Test Cases
- **Happy Path**: 監査で見つかった未実装ステップ名が、コメントとしてコードに正しく挿入されること。
- **Happy Path**: C# のセミコロン不足が検知され、自動付与されること。

## 3. Dependencies
- **Internal**: `ast_analyzer`, `safety_validator`, `dummy_factory`
- **External**: `re`, `datetime`