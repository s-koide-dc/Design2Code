# pipeline_core 設計ドキュメント

## 1. Purpose (Updated 2026-04-21)

`pipeline_core` は対話パイプラインの実行フローを統括する。`Setup → LanguageAnalysis → IntentDetection → SemanticAnalysis → TaskManagement → Clarification → Execution → Response` の順で Stage を実行し、`context` を更新・伝搬させる。実行中の例外は集中処理し、エラーログと学習イベントの記録を行う。VectorEngine をバックグラウンドでロードし、必要時に同期的に利用可能にする。

## 2. Structured Specification

### Input
- **Description**: ユーザー入力テキスト。
- **Type/Format**: `str`
- **Example**: `"注文履歴を取得して"`

### Output
- **Description**: ステージ処理結果を含むパイプラインコンテキスト。
- **Type/Format**: `Dict[str, Any]`
- **Example**:
  ```json
  {
    "original_text": "注文履歴を取得して",
    "analysis": { "intent": "FETCH" },
    "response": { "text": "..." }
  }
  ```

### Core Logic
1. `Pipeline.__init__` で `ConfigManager` を構成し、`MorphAnalyzer`、`SyntacticAnalyzer`、`SemanticAnalyzer`、`TaskManager`、`ClarificationManager`、`Planner`、`ActionExecutor`、`LogManager` を初期化する。
2. テスト実行時はキャッシュ（`<model>.v0.vocab.npy` / `<model>.v0.matrix.npy`）が無い場合のみ `SKIP_VECTOR_MODEL=1` を設定し、VectorEngine のロードをスキップできるようにする。
3. 起動時に `scripts.rotate_logs.rotate_logs` を呼び出し、ログのメンテナンスを実施する（失敗時は無視）。
4. `VectorEngine` は `_start_vector_engine_loading` でバックグラウンドロードを開始し、`vector_engine` プロパティ初回アクセス時に完了待ち（タイムアウト 30 秒）または同期ロードへフォールバックする。
5. `IntentDetector` と `ResponseGenerator` はプロパティで遅延生成され、必要時に `vector_engine` を注入する。
6. `AutonomousLearning` は遅延生成され、`LogManager`、`MorphAnalyzer`、`VectorEngine` を利用して学習イベントを受け取る。
7. `ClarificationManager` のしきい値は `config.json` の `clarification` セクションから読み込み、`Planner` の意図しきい値は `planner` セクションから読み込む。
8. `run(text)` で初期 `context` を生成し、Stage を順に `execute(context, pipeline)` で実行する。
9. Stage が `_early_exit` をセットした場合は以後のステージをスキップして終了する。
10. 例外が発生した場合は `pipeline_stage_error` をログへ記録し、`_log_and_return_error` でエラー用 `context` を構築して返却する。
11. `_log_and_return_error` は `pipeline_error` と `pipeline_end` を記録し、`AutonomousLearning` に `SESSION_COMPLETED` を通知する。
12. `run` の終了時に `_persist_session_log` を呼び、`logs/pipeline_<timestamp>.json` へイベントを JSON Lines で保存する。  
   - `[ACTION|PERSIST|dict|void|FILE] [semantic_roles:{"path":"logs/pipeline_<timestamp>.json"}]` イベントログを追記する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 全ステージが正常に完走する。
  - **Input**: 任意の短文。
  - **Expected Output**: `context.response.text` が生成され、ログファイルが作成される。
- **Edge Cases**:
  - **Scenario**: 途中のステージが `_early_exit` を設定する。
  - **Input**: 明示的に早期終了するケース。
  - **Expected Output / Behavior**: 以降のステージを実行せず `context` を返す。
  - **Scenario**: ステージ実行中に例外が発生する。
  - **Input**: 例外を発生させる入力。
  - **Expected Output / Behavior**: `errors` に内容が記録され、`pipeline_error` と `pipeline_end` がログに残る。
  - **Scenario**: VectorEngine のバックグラウンドロードが失敗する。
  - **Expected Output / Behavior**: エラーイベントを記録し、同期ロードへフォールバックする。

## 3. Dependencies
- **Internal**: `morph_analyzer`, `syntactic_analyzer`, `intent_detector`, `semantic_analyzer`, `task_manager`, `clarification_manager`, `planner`, `action_executor`, `response_generator`, `vector_engine`, `log_manager`, `config_manager`, `autonomous_learning`, `context_manager`

## 4. Error Handling
- `run` で例外を捕捉し、`_log_and_return_error` で安全なエラーコンテキストを生成する。

## 5. Performance & Security
- `VectorEngine` はバックグラウンドでロードし、必要時に同期的に取得する。
