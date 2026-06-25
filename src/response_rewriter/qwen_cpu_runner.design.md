# qwen_cpu_runner Design Document

## 1. Purpose

`qwen_cpu_runner` は `Qwen2.5-3B-Instruct` を `Transformers` 直実行でロードし、`response_rewriter` の versioned contract を受けて日本語の自然文リライトを返す CPU 前提の runner である。  
コード生成ではなく、自然な日本語への整形だけを担当する。

## 2. Structured Specification

### Input
- **Description**: `response_rewriter` から渡される JSON payload。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: `{"text": "..."}` 形式の JSON。
- **Type/Format**: `str`

### Core Logic
1. `build_messages` は `instruction`, `constraints`, `input` を system/user messages に展開する。`original_text` は補助参照としてだけ渡し、書き換え対象としては強調しない。
2. system message には、事実保持・コード生成禁止・新規コマンド提案禁止・Markdown block 禁止に加え、主語・話者・視点・文の役割を変えないことを明示する。
3. model id は既定で `Qwen/Qwen2.5-3B-Instruct` を使い、`QWEN_REWRITER_MODEL` 環境変数で上書きできる。
4. model/tokenizer は lazy load し、同一プロセス内で再利用する。
5. `generate` は CPU 前提の greedy decoding (`do_sample=False`) を使い、既定 32 token の `QWEN_REWRITER_MAX_NEW_TOKENS` で上限を調整できる。
6. decode 後は、不要な挨拶追加・質問追加・過剰な長文化に加え、`original_text` への逆戻り、文末が未完になる出力のような会話取り違えも簡易ガードで検出し、逸脱時は原文へフォールバックする。
7. `main` は one-shot stdin/stdout 契約、`serve_forever` は JSONL の常駐サーバー契約を担当する。
8. 失敗時は stderr へ理由を書き、one-shot は非ゼロ終了、server mode は異常を出して停止する。

### Test Cases
- **Happy Path**:
  - **Scenario**: versioned contract から messages を組み立てる。
  - **Expected Output**: system/user messages に instruction, constraints, response_text が含まれる。
- **Edge Cases**:
  - **Scenario**: model load または generation が失敗する。
  - **Expected Output / Behavior**: stderr に理由を書き、非ゼロ終了する。

## 3. Dependencies
- **Internal**: `response_rewriter`
- **External**: `transformers`, `json`, `os`, `sys`

## 4. Operational Notes
- 業務用 PC の CPU 実行を前提にし、既定値は `Qwen2.5-3B-Instruct` とする。
- この runner は文面リライト専用であり、コード生成やタスク実行は行わない。
- 常駐 server mode では同一プロセスの `_MODEL` / `_TOKENIZER` キャッシュをそのまま再利用し、毎回の model reload を避ける。
- 主語維持などの prompt 制約だけでは HTTP backend を含む全経路の品質を保証できないため、共通層でも同系統の安全ガードを併用する前提で設計する。
