# semantic_analyzer Design Document
<!-- metadata-sync: 2026-07-15T00:00:00+09:00 -->

## 1. Purpose

`semantic_analyzer` は形態素解析済みチャンクからトピックを抽出し、意図に応じた実体（ファイル名・パス・コマンド等）を抽出して `context.analysis.entities` を更新する。  
カスタム知識ベースと SQLite 辞書から意味を引き、必要に応じて履歴参照・状態依存の信頼度ブーストを行う。

## 2. Structured Specification

### Input
- **Description**: パイプラインコンテキスト（`analysis.chunks` を含む）。
- **Type/Format**: `Dict[str, Any]`
- **Example**:
  ```json
  {
    "original_text": "test.txt を作成",
    "analysis": { "chunks": [[{"surface":"test.txt","pos":"名詞","base":"test.txt"}]], "intent": "FILE_CREATE" }
  }
  ```

### Output
- **Description**: `analysis.topics` と `analysis.entities` が更新されたコンテキスト。
- **Type/Format**: `Dict[str, Any]`
- **Example**:
  ```json
  {
    "analysis": {
      "topics": [{"text":"test.txt","pos":"名詞","meaning":null}],
      "entities": {"filename":{"value":"test.txt","confidence":0.9}}
    }
  }
  ```

### Core Logic
1. `analysis.chunks` が無い場合はエラーを追加して終了する。
2. 名詞トークンから `topics` を生成し、重複を排除して `analysis.topics` に格納する。
3. `original_text` と履歴・意図・タスク状態に基づき `_extract_entities` を実行する。
4. `analysis.entities` が存在する場合は抽出結果をマージし、`pipeline_history` に `semantic_analyzer` を追加する。
5. `_extract_entities` は以下を実行する。
   - URL を最優先で抽出し、テキストから除外する。
   - 明示的なファイル拡張子は `.csproj` / `.slnx` / `.props` / `.targets` を含めて抽出し、短い拡張子が長い拡張子を途中で切り取らないよう境界を検証する。
   - `src.utils.action_intents` の共通定数を使い、`FILE_MOVE/FILE_COPY/BACKUP_AND_DELETE` ではソース/デスティネーションを分離抽出する。
   - `FILE_CREATE/FILE_APPEND` では引用符内テキストを内容候補として抽出する。
   - `awaiting_entity` がある場合は積極的に抽出して信頼度を 1.0 にする。
   - 待機中の実体が `project_path` / source / destination の場合、汎用ファイル抽出結果を待機中の実体へ構造的に割り当て直す。
   - 指示語（それ/そのファイル）を履歴から解決する。
   - 意図別の特殊抽出（`CS_QUERY_ANALYSIS`、`MANAGE_KNOWLEDGE`、`DOC_REFINE`、`EXECUTE_GOAL_DRIVEN_TDD` / `PROVIDE_CRITERIA` など）を実行する。
6. `task_state` が `AWAITING_<ENTITY>` の場合、該当実体の信頼度を 1.0 にする。
7. カスタム知識と辞書DBの障害は `data_source_diagnostics` に `source / operation / error_type` を記録し、`analyze()` の `errors` へ伝播する。検索語、データ内容、例外本文は含めない。
8. SQLite接続は処理成功・失敗にかかわらず必ずcloseする。該当データなしは診断を追加せず、SQLite障害と区別する。

### Test Cases
- **Happy Path**:
  - **Scenario**: `FILE_CREATE` でファイル名が抽出される。
  - **Input**: `"test.txt を作成"`
  - **Expected Output**: `entities.filename.value == "test.txt"`。
  - **Edge Cases**:
  - **Scenario**: `.csproj` を含む .NET プロジェクトパスを抽出する。
  - **Expected Output / Behavior**: `entities.filename.value` が `.csproj` まで保持される。
  - **Scenario**: `analysis.chunks` が存在しない。
  - **Expected Output / Behavior**: `errors` にメッセージを追加して終了。
  - **Scenario**: 指示語入力（「それを削除」）で履歴参照。
  - **Expected Output / Behavior**: 直近の `filename` を補完。
  - **Scenario**: 辞書DBが破損している。
  - **Expected Output / Behavior**: `meaning` は `null` のまま解析を継続し、`errors` に `source=dictionary_db` とSQLite例外型を追加する。
  - **Scenario**: カスタム知識JSONが破損している。
  - **Expected Output / Behavior**: 空知識で解析を継続し、`errors` に `JSONDecodeError` を追加する。

## 3. Dependencies
- **Internal**: `text_parser`, `context_utils`
- **External**: `json`, `os`, `re`, `sqlite3`

## 4. Review Notes
- 2026-06-29: 辞書DB・知識JSONの診断契約とSQLite接続解放を反映。
- 2026-06-30: clarification 応答で抽出済みパスを待機中の実体名へ割り当てる契約を反映。
