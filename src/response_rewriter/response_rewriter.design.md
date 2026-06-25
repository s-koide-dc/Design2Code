# response_rewriter Design Document

## 1. Purpose

`response_rewriter` は、`response_generator` が作った決定論的な最終応答文に対して、任意のローカル LLM プラグインで文面だけを後段リライトするための安全ゲートを提供する。  
既定では無効であり、未設定時は完全な no-op として振る舞う。

## 2. Structured Specification

### Input
- **Description**: `context` と、`response_generator` が確定した `response_text`。
- **Type/Format**: `Dict[str, Any]`, `str`

### Output
- **Description**: 安全条件を満たす場合のみリライト後の文字列。条件不一致や失敗時は元文字列。
- **Type/Format**: `str`

### Core Logic
1. `config_manager.response_rewriter_config` から設定を読む。既定は `enabled = false`。
2. `plugin` は `ResponseRewritePlugin` 契約に従い、`RewriteRequest` を受け取って文字列を返す。
3. `provider == "subprocess_stdio"` の場合は、外部プロセスへ versioned JSON contract を stdin で渡し、stdout の JSON `{ "text": "..." }` または text 応答を受け取る one-shot backend を使う。
4. `provider == "persistent_subprocess_jsonl"` の場合は、外部プロセスを常駐起動し、1 リクエスト 1 行の JSONL contract で stdin/stdout を往復させる backend を使う。
5. `provider == "openai_compatible_http"` の場合は、OpenAI 互換の `/v1/chat/completions` endpoint へ versioned contract を `messages` へ展開して POST する backend を使う。
6. persistent backend は同一プロセスを再利用し、都度の model reload を避ける。プロセス終了や I/O 失敗時は deterministic に元文面へフォールバックする。
7. `command` は `${PYTHON_EXECUTABLE}` と `${WORKSPACE_ROOT}` のプレースホルダを展開でき、マシン依存の絶対パスを config に直書きしなくてよい。
8. 設定が無効、空文字、長文超過、構造化出力（fenced code / mermaid / image）が含まれる場合はリライトを行わない。
9. `dialogue_state == pending_confirmation` は、`rewrite_confirmation_messages = true` でない限りリライトしない。
10. `dialogue_state == task_clarification` または `clarification_needed` は、`rewrite_clarification_messages = true` でない限りリライトしない。
11. `action_result.status == "error"` は、`rewrite_error_messages = true` でない限りリライトしない。
12. `rewrite_allowed_intents` が設定されている場合は、その allow-list に含まれる `analysis.intent` だけを rewrite 対象にする。空配列は「どの intent も rewrite しない」という明示設定として扱う。未設定時の既定も rewrite 対象なしである。
13. `rewrite_allowed_action_statuses` が設定されている場合は、その allow-list に含まれる `action_result.status` だけを rewrite 対象にする。これにより作業系完了文や途中状態を既定で deterministic に維持できる。
14. plugin 失敗、空応答、非文字列、`original_text` への逆戻り、長さ逸脱、構造化出力混入、文末が未完になる rewrite は元の文字列へフォールバックする。
15. 本モジュールはコード生成や意味推論を持たず、文面変換の安全境界だけを担当する。
16. backend に渡す `instruction` は「response_text の事実を変えず、日本語の自然さだけを整える」要約専用プロンプトとして扱う。

### Test Cases
- **Happy Path**:
  - **Scenario**: enabled な設定と正常 plugin。
  - **Expected Output**: plugin の返した文面へ置換される。
  - **Scenario**: `subprocess_stdio` backend が versioned JSON contract で応答する。
  - **Expected Output**: stdout の `text` を最終文面として採用する。
  - **Scenario**: `persistent_subprocess_jsonl` backend へ 2 回連続で送る。
  - **Expected Output**: 同一プロセスが再利用され、2 回目も応答できる。
  - **Scenario**: `openai_compatible_http` backend が OpenAI 互換 JSON を返す。
  - **Expected Output**: `choices[0].message.content` を最終文面として採用する。
  - **Scenario**: 承認待ち文面。
  - **Expected Output**: `rewrite_confirmation_messages` を有効にしない限り元文面を維持する。
- **Edge Cases**:
  - **Scenario**: fenced code block を含む応答。
  - **Expected Output / Behavior**: リライトせず元文面を返す。
  - **Scenario**: plugin が例外や空文字を返す。
  - **Expected Output / Behavior**: 元文面へフォールバックする。

## 3. Dependencies
- **Internal**: `config_manager`
- **External**: `atexit`, `dataclasses`, `json`, `logging`, `queue`, `subprocess`, `threading`

## 4. Operational Notes
- Phase 3 の初期段階では plugin 未接続の `NoOpResponseRewritePlugin` を既定値にする。
- ここで扱うのは自然文リライトのみであり、コードブロック・Mermaid・画像マークダウンは対象外にする。
- `subprocess_stdio` backend と `persistent_subprocess_jsonl` backend は `shell=True` を使わず、引数配列でのみ起動する。
- backend に渡す payload は `contract_version`, `mode`, `input`, `constraints`, `instruction` を含み、ローカル LLM ランナーが prompt を自前生成できるようにする。
- 承認文面と補足質問は安全上の意味を持つため、既定では deterministic のまま固定し、明示設定時のみ rewrite を許可する。
- 既定の rewrite 対象は空であり、`FILE_CREATE` などの action intent や conversational intent は、どれも明示許可がある場合だけ rewrite する。
- `rewrite_allowed_action_statuses` を使うことで、成功系 conversational 応答だけを候補にし、`in_progress` や action completion の揺れを避ける。
- backend 固有の postprocess に依存せず、最終採用前の共通層でも文末完全性を検証し、LM Studio などの HTTP backend でも未完文を遮断する。
- `instruction` は自然化専用であり、事実追加、コード生成、コマンド提案、Markdown block 追加を禁止する制約と対で扱う。
- subprocess 実運用では `persistent_subprocess_jsonl` を使い、backend の初期化コストを毎回払わない構成を前提とする。
- persistent backend の close は child process 終了に加え stdin/stdout/stderr を明示 close し、テストや長時間運用での descriptor leak を避ける。
- `openai_compatible_http` backend は `llama.cpp server` などのローカル OpenAI 互換 endpoint を想定し、`temperature=0`, `stream=false` の deterministic 寄り設定で使う。
- LM Studio などの実 backend を有効化する場合も、まず conversational intent 群だけで評価し、action intent への展開は quality / conversation probe の回帰を通してから行う。
