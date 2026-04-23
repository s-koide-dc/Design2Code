# semantic_analyzer Design Document

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
   - `FILE_MOVE/FILE_COPY/BACKUP_AND_DELETE` ではソース/デスティネーションを分離抽出する。
   - `FILE_CREATE/FILE_APPEND` では引用符内テキストを内容候補として抽出する。
   - `awaiting_entity` がある場合は積極的に抽出して信頼度を 1.0 にする。
   - 指示語（それ/そのファイル）を履歴から解決する。
   - 意図別の特殊抽出（`CS_QUERY_ANALYSIS` など）を実行する。
6. `task_state` が `AWAITING_<ENTITY>` の場合、該当実体の信頼度を 1.0 にする。

### Test Cases
- **Happy Path**:
  - **Scenario**: `FILE_CREATE` でファイル名が抽出される。
  - **Input**: `"test.txt を作成"`
  - **Expected Output**: `entities.filename.value == "test.txt"`。
- **Edge Cases**:
  - **Scenario**: `analysis.chunks` が存在しない。
  - **Expected Output / Behavior**: `errors` にメッセージを追加して終了。
  - **Scenario**: 指示語入力（「それを削除」）で履歴参照。
  - **Expected Output / Behavior**: 直近の `filename` を補完。

## 3. Dependencies
- **Internal**: `text_parser`, `context_utils`
- **External**: `json`, `os`, `re`, `sqlite3`
