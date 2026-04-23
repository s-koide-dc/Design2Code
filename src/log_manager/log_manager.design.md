# log_manager Design Document

## 1. Purpose (Updated 2026-02-10 15:30)

`log_manager`モジュールは、AIパイプラインの各処理ステップにおける詳細な情報を記録し、アクションの再現性と透明性を確保することを目的とします。ユーザーの入力からAIの最終的な行動、その結果に至るまで、すべての重要なイベントを時系列でログに記録します。さらに、セキュリティ上重要な操作に対しては厳格な監査データ検証を行い、不備がある場合に処理を未然に防ぐ安全装置としての機能も提供します。

**主要機能**:
- **デュアルフォーマットログ**: 人間可読なテキストログと機械可読なJSONログの同時出力
- **セキュリティ監査**: 重要な操作に対する必須フィールド検証と監査コンプライアンス
- **機密情報保護**: 自動的な機密フィールドのサニタイズとマスキング
- **動的ログレベル**: 設定ファイルによる実行時のログレベル制御
- **エラー集約**: アクション実行エラーの専用サマリーファイル管理
- **ターンごとのイベント取得**: パイプラインの1ターン（開始から終了まで）のイベントをファイルから抽出し、永続化する機能
- **厳格モード**: 監査不備時の処理ブロック機能（`AuditComplianceError`）

## 2. Architecture Overview

### 2.1 Core Components

#### LogManager (Main Class)
- **役割**: ログ記録の中心的なコントローラー
- **責任**:
  - ログファイルの管理（テキスト、JSON、エラーサマリー）
  - ログレベルのフィルタリング
  - セキュリティ監査の実施
  - 機密情報のサニタイズ
  - イベントのファイル読み出し (`get_events_after`)

#### Security Audit System
- **SECURITY_SENSITIVE_EVENTS**: セキュリティ上重要なイベントのリスト
- **AuditComplianceError**: 監査不備時の例外クラス
- **Audit Validation**: 必須フィールドの検証ロジック
- **Strict Mode**: 監査不備時の処理ブロック機能

#### Log Output Management
- **Text Log**: 人間可読なタイムスタンプ付きログ
- **JSON Log**: 機械可読な構造化ログ (JSON Objects Sequence)
- **Error Summary**: アクション実行エラーの集約ファイル

### 2.2 Logging Process

#### 1. 初期化フェーズ
- 設定マネージャーからの設定読み込み（オプション）
- ログディレクトリの作成
- ログファイルパスの生成（タイムスタンプ付き）
- ログレベルの解析と設定

#### 2. イベント記録フェーズ
- ログレベルのフィルタリング
- セキュリティ監査の実施（重要イベントのみ）
- 機密情報のサニタイズ（固定キー + キーワード一致）
- ログエントリの作成
- ファイルへの書き込み（テキスト + JSON）
- エラーサマリーの更新（エラーイベントのみ）

#### 3. イベント取得フェーズ (Analytics)
- `get_events_after(start_time)`: 指定時刻以降のイベントを JSON ログファイルから抽出。
- これにより、メモリ内リストに依存せず、プロセス終了やクラッシュに強いログ収集を実現。

## 3. Structured Specification

### 3.1 LogManager.get_events_after

#### Input
- **Description**: 指定時刻以降のイベントを取得
- **Type/Format**:
  - `start_timestamp` (datetime): 検索開始時刻
- **Output**: List[dict] (イベントのリスト)

#### Core Logic
1. **バッファ調整**: `start_timestamp` から数秒（例: 5秒）引いた時刻を基準とし、クロックのズレや書き込み遅延を吸収。
2. **ファイル読み込み**: 現在の JSON ログファイルを読み込む。
3. **パース処理**:
   - JSON オブジェクトが連続する形式 (`{...},\n{...}`) を正規表現で抽出。
   - `json.loads` でパースし、`timestamp` フィールドと比較。
4. **フィルタリング**: 基準時刻以降のイベントのみをリストに追加して返却。

### 3.4 LogManager.log_event (Updated)

- **変更点**: メモリ内リストへの追加を廃止し、すべてファイルベースで管理。

### 3.5 LogManager._write_log

- **変更点**: ファイル書き込み後、OSレベルでのバッファフラッシュを確実に行う（`with open` コンテキストマネージャにより自動化されるが、即時性を重視）。

## 6. Configuration

### 6.1 Configuration Structure
- **Path**: `config/config.json`の`logging`セクション
- **Format**: JSON
- **Structure**:
  ```json
  {
    "logging": {
      "log_dir": "logs",
      "log_file_prefix": "pipeline",
      "log_level": "INFO",
      "strict_audit": true,
      "sensitive_fields": ["filename", "command", "content", "error_details"],
      "sensitive_field_keywords": ["token", "secret", "password", "api_key", "apikey"]
    }
  }
  ```

## 10. Future Enhancements

### 10.1 Log Rotation & Archival (Implemented)
- **Status**: Implemented via `scripts/rotate_logs.py`
- **Logic**:
  - 起動時に `Pipeline` から呼び出される。
  - 指定日数（例: 7日）より古い `pipeline_*.json/log` を `logs/archive/` に zip 圧縮して移動。
