# DesignSyncUtil Design Document

## 1. Purpose (Updated 2026-02-10)
`DesignSyncUtil` は、ソースコードの実装実態を設計書（Markdown）に自動的に書き戻す「逆同期（Back-porting）」機能を提供することを目的とします。

## 2. Structured Specification

### Input
- **design_path**: 更新対象の設計書パス（Markdown）。
- **code_structure**: `ASTAnalyzer` または Roslyn解析ツールが出力したコード構造データ（Dict）。
- **step_idx / new_content**: 特定のロジックステップを更新する場合のインデックスと内容。

### Output
- **status**: 同期が成功したかどうか（bool）。
- **Updated Markdown**: 実装実態が反映された設計書ファイル。

### Core Logic

#### A. インターフェース同期 (`sync_code_to_design`)
1.  設計書内の `Input:` セクションを検索。
2.  メソッド引数や型情報を抽出し、`Arguments: ... (Synced from code)` の形式で設計書を更新。
3.  C# と Python の両方の引数形式（`args` リストおよび `parameters` 文字列）に対応。

#### B. ロジックステップ同期 (`update_logic_step`)
1.  設計書内の `Core Logic:` セクション内の箇条書きリストをスキャン。
2.  指定されたインデックス (`step_idx`) の項目を、コードの解析結果に基づいた新しい内容に置換。
3.  更新された項目に `(Synced from code)` マーカーを付与し、自動更新されたことを明示。

#### C. フィードバック収集 (`collect_user_feedback`)
1.  監査における指摘へのユーザー回答を `user_feedback.jsonl` に保存。
2.  保存されたデータは `AutonomousLearning` によって解析され、知識ベースの更新に利用される。

### Test Cases
- **Happy Path**: C# のメソッド引数を追加した後、`sync_code_to_design` を呼び出すと設計書の `Input:` 部分が自動更新されること。
- **Happy Path**: ロジックステップのインデックスを指定して更新し、設計書の該当行のみが変更されること。

## 3. Dependencies
- **Internal**: `logic_auditor`, `fix_engine` (からの呼び出し)
- **External**: `re`, `json`, `pathlib`
