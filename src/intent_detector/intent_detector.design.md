# intent_detector Design Document

## 1. Purpose

`intent_detector` はユーザー入力の意図を推定し、`context.analysis.intent` と `intent_confidence` を更新する。  
コーパスに含まれる例文をベクトル化し、入力文との類似度で意図を決定する。承認待ち（確認要求）状態では `AGREE`/`DISAGREE` を優先判定する。

## 2. Structured Specification

### Input
- **Description**: パイプラインコンテキスト。
- **Type/Format**: `Dict[str, Any]`
- **Example**:
  ```json
  {
    "original_text": "はい",
    "analysis": { "tokens": [] },
    "task": { "name": "FILE_DELETE", "clarification_needed": true }
  }
  ```

### Output
- **Description**: 意図と信頼度が更新されたコンテキスト。
- **Type/Format**: `Dict[str, Any]`
- **Example**:
  ```json
  {
    "analysis": {
      "intent": "AGREE",
      "intent_confidence": 1.0
    }
  }
  ```

### Core Logic
1. 初期化で `corpus_path` を決定する（`config_manager.intent_corpus_path` → 明示引数 → `resources/intent_corpus.json`）。
2. コーパス JSON から `intents` を読み込む。読み込み失敗時は空配列として続行する。
3. `prepare_corpus_vectors` で例文を形態素解析し、文ベクトルを作成して `cache/intent_vectors.pkl` に保存する。キャッシュは `intent_corpus.json` の更新時刻で無効化する。
4. `_extract_content_words` は助詞/助動詞/記号/接続詞を除外し、拡張子トークン（`txt`, `md`, `json` など）をノイズとして除外する。拡張子が含まれる場合は ASCII トークンの大半を除外してファイル名誤検出を抑制する。
5. `detect` は `original_text` が空の場合、`GENERAL` と `intent_confidence=0.5` を返す。
6. 承認待ちの判定は `clarification_needed` と `clarification_type == "APPROVAL"` に基づく。`active_tasks` に同条件があれば `awaiting_conf` を真とする。
7. 意図候補の文ベクトルが存在する場合のみ、入力文のベクトルと全意図ベクトルの類似度を比較する。
8. ベースラインの `threshold=0.60` を超える最良意図を採用する。
9. 状態に応じたブーストを適用する（例: `FILE_CREATE` の `AWAITING_CONTENT` → `PROVIDE_CONTENT` に加点）。
10. 承認待ち状態では `AGREE` / `DISAGREE` に追加ブーストを適用する。
11. アクション系意図（例: `FILE_CREATE`, `CMD_RUN`, `GENERATE_TESTS`）は一定スコア以上で小さなブーストを加えて、`GREETING` の誤判定を抑制する。
12. `GREETING` は高スコア時のみ追加ブーストを許可する。
13. `context.analysis.intent` / `intent_confidence` を更新し、`pipeline_history` に `intent_detector` を追加する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 既存の例文に近い入力で意図が一致する。
  - **Input**: `"テストを実行して"`（例文が存在する場合）
  - **Expected Output**: `intent_confidence > 0.60` で一致意図。
- **Edge Cases**:
  - **Scenario**: 入力が空。
  - **Expected Output / Behavior**: `intent="GENERAL"`, `intent_confidence=0.5`。
  - **Scenario**: 承認待ち状態で「はい」入力。
  - **Expected Output / Behavior**: `intent="AGREE"`, `intent_confidence=1.0`。
  - **Scenario**: 承認待ちではない確認要求（`clarification_type != "APPROVAL"`）。
  - **Expected Output / Behavior**: `AGREE/DISAGREE` に過度な優先はかからず、通常の類似度判定を行う。

## 3. Dependencies
- **Internal**: `vector_engine`, `morph_analyzer`, `task_manager`, `config_manager`
- **External**: `json`, `os`, `pickle`
