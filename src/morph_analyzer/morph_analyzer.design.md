# morph_analyzer 設計ドキュメント

## 1. 目的 (Purpose)

本モジュールは、パイプラインの最初の処理を担当する。
ユーザーから入力された生のテキスト文字列を形態素解析し、単語（トークン）のリストに分割する。解析結果は、`pipeline_core` で定義された共通データ構造（コンテキストオブジェクト）の `analysis.tokens` フィールドに格納される。

**主要機能**:
- **形態素解析**: Janomeライブラリを使用した日本語テキストのトークン化
- **トークン情報抽出**: 表層形、品詞、原形の詳細情報
- **エラーハンドリング**: 入力検証と例外処理
- **パイプライン統合**: コンテキストオブジェクトの標準化された更新

## 2. Architecture Overview

### 2.1 Core Components

#### MorphAnalyzer (Main Class)
- **役割**: 形態素解析の中心的なコントローラー
- **責任**:
  - Janomeトークナイザーの初期化と管理
  - ユーザー辞書の読み込み（オプション）
  - テキストのトークン化
  - トークン情報の抽出と構造化
  - コンテキストオブジェクトの更新

#### Tokenizer Integration
- **Janome Tokenizer**: 日本語形態素解析エンジン
- **Standard Dictionary**: デフォルトの標準辞書

#### Token Structure
- **surface**: 表層形（実際の文字列）
- **pos**: 品詞情報
- **base**: 原形（基本形）

### 2.2 Analysis Process

#### 1. 初期化フェーズ
- Janomeトークナイザーの初期化（標準辞書）

#### 2. 検証フェーズ
- コンテキストオブジェクトの基本構造確認
- `original_text`フィールドの存在確認および型検証

#### 3. 解析フェーズ
- テキストの空文字列チェック
- Janomeトークナイザーによるトークン化
- 各トークンの情報抽出（surface, pos, base）

#### 4. 結果更新フェーズ
- `context["analysis"]["tokens"]`への結果格納
- `context["pipeline_history"]`への履歴追加

## 3. 構造化仕様 (Structured Specification)

### 3.1 MorphAnalyzer.__init__

#### Input
- `config_manager` (ConfigManager, optional): 設定管理インスタンス

#### Output
- MorphAnalyzerインスタンス

#### Core Logic
1. **設定マネージャーの保存**: `self.config_manager = config_manager`
2. **トークナイザーの初期化**:
   - `Tokenizer()`（標準辞書）

### 3.2 MorphAnalyzer.analyze

#### Input
- `context` (dict): `original_text`フィールドを含むコンテキスト

#### Output
- トークン情報が追加されたコンテキスト (dict)

#### Core Logic
1. `[ACTION|TRANSFORM|dict|dict|NONE] [ops:init_context] コンテキストの基本構造を保証
2. `[ACTION|TRANSFORM|str|str|NONE] [ops:validate_input] 入力検証（original_textの存在と型）
3. `[ACTION|TRANSFORM|str|List<dict>|NONE] [ops:tokenize_text] 形態素解析の実行
4. `[ACTION|TRANSFORM|dict|dict|NONE] [ops:update_context] 結果格納と履歴更新

### Test Cases

#### TC1: ハッピーパス
- Input: `{"original_text": "猫が歩く"}`
- Expected: `analysis.tokens` に 3 トークン、`pipeline_history` に `"morph_analyzer"` を追加。

#### TC2: エッジケース（空文字列）
- Input: `{"original_text": ""}`
- Expected: `analysis.tokens` が `[]`、`pipeline_history` に `"morph_analyzer"` を追加。エラーなし。

#### TC3: エラーケース（original_text欠落）
- Input: `{}`
- Expected: `errors` にモジュール名とエラーメッセージを追加。

#### TC4: エラーケース（original_textが文字列でない）
- Input: `{"original_text": 123}`
- Expected: `errors` にモジュール名とエラーメッセージを追加。

## 4. Dependencies
- **janome**: 日本語形態素解析ライブラリ
- **pipeline_core**: コンテキスト定義

## 5. Error Handling
- 不正入力や解析例外時は `errors` フィールドに詳細を追加し、処理を中断してコンテキストを返却。

## 6. Performance
- トークナイザーのインスタンス化は初期化時に1回のみ。

## 7. Review Notes
- 2026-03-31: タイプ注釈の型 import を補完し、実装と一致させた。
