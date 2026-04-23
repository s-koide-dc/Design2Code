# response_generator Design Document

## 1. Purpose

`response_generator` は意図、トピック、アクション結果を基に最終応答文を生成する。  
固定応答、概念マッチ、定義応答、アクション結果の要約を統合して `response.text` を構築する。

## 2. Structured Specification

### Input
- **Description**: `analysis.intent` / `analysis.topics` / `action_result` を含むコンテキスト。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: `response.text` を追加したコンテキスト。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. Safety Policy のエラーがある場合は即時にエラーメッセージを返す。
2. `intent_responses` に一致する意図があれば固定応答を返す（`CAPABILITY` は明示的に除外し、専用文を使う）。
3. `TIME` / `CAPABILITY` は内部ロジックで生成する。
4. トピックが無い `DEFINITION` はエラーを返す。その他の意図はデフォルト応答へフォールバック可能。
5. `topics` がある場合、`concept_responses` の類似度評価で概念応答を試す。
6. `DEFINITION` は名詞句を抽出し、辞書の意味を応答文に反映する。抽出できない場合はフォールバックする。
7. それ以外はテンプレートまたはデフォルト応答を使用する。
8. `action_result` がある場合は応答文に結果を付加し、特定意図（`CS_ANALYZE` / `CS_IMPACT_SCOPE` / `GENERATE_TESTS` など）を整形する。
9. `task_interruption` がある場合は、割り込み後の復帰メッセージを付加する。

### Test Cases
- **Happy Path**:
  - **Scenario**: `TIME` の応答。
  - **Expected Output**: 現在時刻の応答文。
- **Edge Cases**:
  - **Scenario**: `topics` がない `DEFINITION`。
  - **Expected Output / Behavior**: デフォルト応答またはエラー。
  - **Scenario**: `action_result.status == "error"`。
  - **Expected Output / Behavior**: エラーメッセージを含む応答。
  - **Scenario**: `CS_IMPACT_SCOPE` の成功結果。
  - **Expected Output / Behavior**: Mermaid 形式の影響グラフが付加される。

## 3. Dependencies
- **Internal**: `vector_engine`, `task_manager`, `log_manager`
- **External**: `json`, `os`, `random`, `datetime`
