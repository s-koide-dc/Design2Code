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
1.  **監査結果の優先処理**: 入力に `findings` が含まれる場合、`logic_gap` / `missing_step` を処理する。
2.  **構造化ロジック修正 (`_generate_missing_logic_fix`)**:
    - `symbol_id`、`start_line`、`end_line`、`replacement_code`、引数配列形式の `validation_command` を必須契約とする。
    - 契約が完全な場合だけ置換候補を `auto_applicable=True` で返す。
    - 情報が不足する場合はコードやTODOを生成せず、欠落項目を持つ `auto_applicable=False` の手動調査候補を返す。
    - テストの期待値は実装仕様ではないため、期待値をreturnへ直書きするフォールバックは行わない。
3.  **値不一致・パラメータ修正**:
    - `logic_value_mismatch` と `missing_parameter` も、構造化編集契約がある場合だけ適用可能候補を返す。
    - finding の説明文から数値・変数名・引数名を抽出してコードを書き換えない。
4.  **C# 構文エラー修復 (`fix_syntax_error`)**:
    - `replacement_code`、`start_line`、`end_line`、引数配列形式の `validation_command` を持つ構造化編集契約がある場合だけ適用可能候補を返す。
    - コンパイラメッセージから型名・名前空間・async の有無を推定してコードを書き換えない。
    - 契約が不足する場合は `manual_fix` を返し、`auto_applicable=False` とする。
5.  **テスト期待値修正 (`self_healing_test`)**: 実際値（Actual）に基づきアサーションを自動更新。
6.  **テストArrange修正 (`test_arrange_fix`)**:
    - `arrange_statement`、`insert_line`、引数配列形式の `validation_command` を持つ構造化Arrange編集契約がある場合だけ適用可能候補を返す。
    - SUT/Test のソーステキストから依存名、Mock名、戻り値型、挿入位置を推定して `Returns(...)` を生成しない。
7.  **設計への逆同期 (Back-porting)**:
    - `design_path`、`backport_content`、`step_idx` を持つ構造化設計同期契約がある場合だけ、設計書更新案を生成する。
    - finding の説明文から値、比較演算子、ステップ番号を抽出して設計更新案を作らない。
8.  **提案コンテキスト補完**: 生成した各 `CodeFixSuggestion` に `impact_analysis.target_file` / `target_method` / `root_cause` / `fix_direction` / `reason` / `recommended_action` / `target_summary` / `conversation_hint` を補完する。非適用候補の `recommended_action` は `inspect_manual_fix` とする。
9.  **安全性評価**: `SafetyValidator` を用いて、適用可能候補を検証する。`safety_score` は既存モデル互換のために保持するが、`FixEngine` はスコアを計算・上書きしない。適用可否は構造化契約、`auto_applicable`、`SafetyValidator` の構造化 evidence で判断する。

### Test Cases
- **Happy Path**: 完全な構造編集契約がある場合だけ、symbol ID・行範囲・置換コード・検証コマンドを持つ適用可能候補になること。
- **Edge Case**: 構造編集契約が不足する場合、TODOを生成せず手動調査候補になること。
- **Edge Case**: 値不一致・パラメータ不足でも構造化編集契約が不足する場合は手動調査候補になること。
- **Happy Path**: C# のセミコロン不足が検知され、自動付与されること。
- **Edge Case**: C# 構文エラーでも構造化編集契約が不足する場合は手動調査候補になること。
- **Edge Case**: Arrange修正でも構造化Arrange編集契約が不足する場合は手動調査候補になること。
- **Edge Case**: Backportでも構造化設計同期契約が不足する場合は提案を生成しないこと。
- **Happy Path**: 生成された提案に `target_file`、`reason`、`recommended_action`、`target_summary` が補完されること。

## 3. Dependencies
- **Internal**: `ast_analyzer`, `safety_validator`
- **External**: `hashlib`, `datetime`
