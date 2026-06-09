# utils Design Document

## 1. Purpose (Updated 2026-04-14)

`utils` は設計書解析や監査、テキスト解析、リトライ、ビルダー連携など、プロジェクト横断の補助機能を提供する。

## 2. Structured Specification

### Input
- **Description**: コンテキスト辞書や文字列パス。
- **Type/Format**: `Dict[str, Any]` / `str`

### Output
- **Description**: 要約辞書、正規化済みパス、抽出パス。
- **Type/Format**: `Dict[str, Any]` / `str`

### Core Logic
1. `design_doc_parser` は Markdown から Purpose / Spec / Test Cases を抽出する。
2. `design_doc_refiner` は設計書と実装の差分・不整合を監査する。
3. `logic_auditor` は数値条件などの論理ゴールと実装コードの整合を検査する。
4. `text_parser` は URL/SQL パラメータやパス候補の抽出を行う。
5. `retry_utils` はリトライ制御を提供する。
6. `dialogue_state` は `pending_confirmation` / `task_clarification` / `feedback_collection` の共通定数を提供し、対話状態名の直書きを避ける。
7. `confirmation_response` は `AGREE` / `DISAGREE` / `CLARIFICATION_RESPONSE` とその遷移状態の共通定数を提供し、承認応答分岐の文字列直書きを避ける。
8. `control_intents` は `TIME` / `GENERAL` / `CANCEL_TASK` / `FEEDBACK_RECEIVED` など対話制御 intent と会話 intent 集合の共通定数を提供し、会話分岐の文字列直書きを避ける。
9. `action_intents` は `FILE_CREATE` / `CMD_RUN` / `EXECUTE_GOAL_DRIVEN_TDD` に加え `SETUP_CICD` / `GENERATE_PIPELINE_CONFIG` / `RECOVERY_FROM_TEST_FAILURE` / `SET_METHOD_NAME` / `FILE_WRITE` など資産境界まで含めた主要 action intent と補助集合を提供し、実行系分岐の文字列直書きを避ける。
10. `semantic_intents` は `GENERAL` / `FETCH` / `TRANSFORM` / `DISPLAY` など IR / code synthesis 内部 semantic intent、node kind、runtime role を提供し、内部語彙の文字列直書きを避ける。

### Test Cases
- **Happy Path**:
  - **Scenario**: `normalize_path` で `C:\\work\\a.txt` を正規化。
  - **Expected Output**: `C:/work/a.txt`。
- **Edge Cases**:
  - **Scenario**: `context` が `None`。
  - **Expected Output / Behavior**: 既定のエラー要約を返す。

## 3. Dependencies
- **Internal**: `design_doc_parser`, `design_doc_refiner`, `logic_auditor`, `text_parser`, `retry_utils`
- **External**: `os`, `re`, `json`

## 4. Review Notes
- 2026-04-14: normalize_path を含む補助機能の役割と依存関係を現行実装に合わせて再確認。
- 2026-06-04: `logic_auditor` と `spec_auditor` の internal semantic intent 比較を `src.utils.semantic_intents` の共通語彙へ寄せた。
- 2026-06-04: `action_intents` を task 資産境界まで拡張し、`validate_project_consistency.py` の resource 語彙検証で `intent_corpus.json` / `task_definitions.json` を監視できるようにした。
