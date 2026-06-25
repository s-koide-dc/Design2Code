# response_generator Design Document

## 1. Purpose

`response_generator` は意図、トピック、タスク状態、アクション結果を基に最終応答文を生成する。  
固定応答、概念マッチ、定義応答、動的テンプレート、アクション結果の要約を統合して `response.text` を構築する。

## 2. Structured Specification

### Input
- **Description**: `analysis.intent` / `analysis.topics` / `task` / `action_result` を含むコンテキスト。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: `response.text` を追加したコンテキスト。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. Safety Policy のエラーがある場合は即時にエラーメッセージを返す。
2. `analysis.topics` は文字列入力も辞書形式へ正規化してから後続処理へ渡す。
3. `intent_responses` に一致する意図があれば固定応答を返す（`INTENT_CAPABILITY` は明示的に除外し、専用文を使う）。
4. `INTENT_TIME` / `INTENT_CAPABILITY` は内部ロジックで生成する。
5. トピックが無い `INTENT_DEFINITION` はエラーを返す。その他の意図はデフォルト応答へフォールバック可能。
6. `topics` がある場合、`concept_responses` の類似度評価で概念応答を試す。
7. `INTENT_DEFINITION` は名詞句を抽出し、辞書の意味を応答文に反映する。抽出できない場合はフォールバックする。
8. それ以外はテンプレートまたはデフォルト応答を使用する。
9. `_finalize_response` では `task` と `action_result` から `task_name` / 対象 / 生成物 / 例外種別を抽出し、`dialogue_templates` を用いて進捗・成功・失敗の自然文へ動的に束ねる。進捗系の標準文は deterministic に十分自然であることを優先し、LLM rewrite を前提にした冗長文へ寄せない。
10. `action_result.status == "error"` の場合は構造化 `type` と既知例外名を優先して人間向け説明へ変換する。
11. `action_result.dialogue_metadata.phase` が `goal_driven_tdd` / `failure_analysis` / `code_fix` の場合は、フェーズ固有の成功・失敗メッセージへ昇格し、`reason` / `recommended_action` / `target_summary` を優先して文面化する。
12. `recommended_action` は `resources/custom_knowledge.json` の `recommended_action_labels` と `recommended_action_descriptions` で利用者向け表示名と説明文へ変換し、内部コード名を直接出力しない。
13. 特定意図（`CS_ANALYZE` / `CS_IMPACT_SCOPE` / `GENERATE_TESTS` など）は専用整形を維持したまま、動的テンプレートを前置または補足として付加する。
14. `task_interruption` がある場合は、割り込み応答の末尾に復帰用メッセージを付加する。
15. `generate_confirmation_message` は `plan.recommended_action` を優先し、必要に応じて `action_method` から `recommended_action` を決定論的に補完して、承認待ち文面も同じ表示名・説明文へ揃える。
16. 承認文面を生成した場合は `dialogue_state=pending_confirmation` を明示し、通常の補足質問 (`task_clarification`) と扱いを分離する。
17. `pending_confirmation` などの対話状態名は `src.utils.dialogue_state` の共通定数を利用し、承認系の状態判定を文字列直書きに依存させない。
18. 現時点で `action_method` からの補完は `_apply_code_fix -> apply_code_fix` を持ち、TDD 系の修正適用承認が `recommended_action` 未設定でも自然文へ収束する。
19. `TIME` / `CAPABILITY` / `DEFINITION` / `GENERAL` などの対話制御 intent は `src.utils.control_intents` の共通定数を使い、固定応答やフォールバック条件の文字列直書きを避ける。
20. `CS_IMPACT_SCOPE` / `CS_ANALYZE` / `GENERATE_TESTS` など action 後整形を持つ intent は `src.utils.action_intents` の共通定数を使い、後処理分岐の文字列直書きを避ける。
21. `_finalize_response` の最後段では `response_rewriter` を呼び出し、Phase 3 のローカル LLM リライト層を安全に差し込めるようにする。
22. `response_rewriter` は既定で無効であり、構造化出力（コードブロック、Mermaid、画像）や長文、エラー応答は設定に応じて deterministic にバイパスする。

### Test Cases
- **Happy Path**:
  - **Scenario**: `INTENT_TIME` の応答。
  - **Expected Output**: 現在時刻の応答文。
  - **Scenario**: `action_result.status == "success"` かつ `generated_files` を含む。
  - **Expected Output**: タスク名・対象・生成物パスを含む自然文。
  - **Scenario**: `dialogue_metadata.phase == "goal_driven_tdd"`。
  - **Expected Output**: 目標名、反復回数、生成成果物数を含む自然文。
- **Edge Cases**:
  - **Scenario**: `topics` がない `DEFINITION`。
  - **Expected Output / Behavior**: デフォルト応答またはエラー。
  - **Scenario**: `action_result.status == "error"`。
  - **Expected Output / Behavior**: 構造化エラー説明を含む応答。
  - **Scenario**: `CS_IMPACT_SCOPE` の成功結果。
  - **Expected Output / Behavior**: Mermaid 形式の影響グラフが付加される。
  - **Scenario**: `task_interruption == True`。
  - **Expected Output / Behavior**: 通常応答の後ろにタスク再開案内が付加される。
  - **Scenario**: `response_rewriter` が有効で plugin が文面を返す。
  - **Expected Output / Behavior**: 安全条件を満たす場合だけ最終応答が差し替わる。
  - **Scenario**: Mermaid を含む structured output。
  - **Expected Output / Behavior**: リライトせず元文面を返す。

## 3. Dependencies
- **Internal**: `vector_engine`, `task_manager`, `log_manager`, `response_rewriter`
- **External**: `json`, `os`, `random`, `datetime`

## 4. Operational Notes
- タスク定義や knowledge base の読込失敗は stdout ではなく logger に記録する。
- `dialogue_templates`, `recommended_action_labels`, `recommended_action_descriptions` は `resources/custom_knowledge.json` からロードし、乱択ではなく固定キー解決で利用する。
- `SMALLTALK` の既定応答は短く会話継続しやすい文面を優先し、LLM rewrite を前提にした説明調の膨らみを避ける。
- 対象抽出は `filename` だけでなく `command` も含めて行い、承認待ちや進捗文で「対象」が空ラベルへ崩れないようにする。
- 標準の進捗・承認待ち・入力待ち・成功文は、余分な空白や説明語を避けた短い deterministic 文面として維持し、既定品質では rewrite せず preserve する。
- 正式な利用者向け出力は常に `context["response"]["text"]` に集約し、モジュール自身は標準出力責務を持たない。
