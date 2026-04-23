# RetryUtils Design Document

## 1. Purpose

RetryUtilsは、指数バックオフ機能付きのリトライデコレータを提供するユーティリティモジュールです。ネットワーク接続エラーやI/Oエラーなど、一時的な障害に対して自動的に再試行を行い、システムの堅牢性を向上させます。

## 2. Structured Specification

### Input
- **Description**: デコレータのパラメータとして、リトライ設定を受け取る
- **Type/Format**: 
  - `max_retries`: `int` (デフォルト: 3)
  - `base_delay`: `float` (デフォルト: 1.0秒)
  - `max_delay`: `float` (デフォルト: 10.0秒)
  - `exceptions`: `tuple` (デフォルト: (IOError, OSError, ConnectionError))
- **Example**:
  ```python
  @retry_with_backoff(max_retries=5, base_delay=0.5, max_delay=30)
  def unstable_function():
      # 不安定な処理
      pass
  ```

### Output
- **Description**: デコレートされた関数の実行結果、または最終的な例外
- **Type/Format**: 元の関数の戻り値の型、または例外
- **Example**:
  ```python
  # 成功時: 元の関数の戻り値
  result = decorated_function()
  
  # 失敗時: 最後に発生した例外が再発生
  # ConnectionError, IOError, OSError等
  ```

### Core Logic
1. **デコレータ適用**:
   - 指定されたパラメータでリトライ設定を初期化
   - 元の関数をラップする内部関数を作成
2. **関数実行とリトライ**:
   - 指定された最大回数まで関数実行を試行
   - 指定された例外が発生した場合のみリトライ
   - 各試行間に指数バックオフによる待機時間を設ける
3. **バックオフ計算**:
   - 待機時間 = min(base_delay * (2^試行回数) + ランダム値, max_delay)
   - ランダム値(0-1秒)を追加してサンダリングハード問題を回避
4. **ログ記録**:
   - 関数の第一引数がlog_managerを持つ場合、リトライ情報をログに記録
   - ae.log_managerパターンにも対応
5. **最終処理**:
   - 全試行が失敗した場合、最後の例外を再発生

### Test Cases
- **Happy Path**:
  - **Scenario**: 1回目で成功する関数
  - **Input**: 正常に動作する関数にデコレータを適用
  - **Expected Output**: 元の関数の戻り値がそのまま返される
- **Edge Cases**:
  - **Scenario**: 指定回数内で成功する場合
  - **Input**: 2回目で成功する関数（max_retries=3）
  - **Expected Output**: 2回目の実行結果が返され、1回のリトライログが記録される
  - **Scenario**: 全試行が失敗する場合
  - **Input**: 常に例外を発生させる関数
  - **Expected Output**: 最後に発生した例外が再発生される
  - **Scenario**: 対象外の例外が発生する場合
  - **Input**: ValueError等、指定されていない例外を発生させる関数
  - **Expected Output**: リトライせずに即座に例外が再発生される
  - **Scenario**: ログマネージャーが存在しない場合
  - **Input**: log_managerを持たないオブジェクトの関数
  - **Expected Output**: ログ記録なしでリトライが実行される

## 3. Security & Boundary Rules

- **最大遅延制限**: max_delayにより無制限な待機時間を防止
- **例外フィルタリング**: 指定された例外のみリトライし、予期しない例外は即座に伝播
- **リソース保護**: 指数バックオフにより、システムへの過度な負荷を防止

## 4. Consumers

- **action_executor**: ファイル操作やコマンド実行の安定性向上
- **vector_engine**: ベクトルモデル読み込みの堅牢性確保
- **semantic_analyzer**: 知識ベースアクセスの信頼性向上
- **test_generator**: テスト生成処理の安定化
- **その他**: 外部リソースアクセスを行う全モジュール

## 5. Dependencies

- **Internal**: 
  - `log_manager`: リトライ情報のログ記録（オプション）
- **External**: 
  - `time`: 待機時間の実装
  - `random`: ジッター追加
  - `functools`: デコレータの実装