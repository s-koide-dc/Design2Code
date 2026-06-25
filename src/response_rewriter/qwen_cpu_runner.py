import json
import os
import sys
import traceback


DEFAULT_MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
DEFAULT_MAX_NEW_TOKENS = 32
_MODEL = None
_TOKENIZER = None
_SENTENCE_FINAL_CHARS = ("。", "！", "？", ".", "!", "?", "」", "』", '"', "'")


def build_messages(payload: dict) -> list[dict]:
    instruction = payload.get("instruction", "")
    constraints = payload.get("constraints", {})
    response_text = payload.get("input", {}).get("response_text", "")
    original_text = payload.get("input", {}).get("original_text", "")
    intent = payload.get("input", {}).get("intent", "")
    dialogue_state = payload.get("input", {}).get("dialogue_state", "")
    task_name = payload.get("input", {}).get("task_name", "")
    action_status = payload.get("input", {}).get("action_status", "")

    system_lines = [
        "あなたは日本語の応答文を自然に整えるリライターです。",
        "あなたの仕事は rewrite だけです。新しい情報を足してはいけません。",
        "会話を開始してはいけません。質問を追加してはいけません。挨拶を追加してはいけません。",
        "response_text の意味・事実・意図を変えてはいけません。",
        "主語・話者・視点を変えてはいけません。たとえば「私は」を「私たちは」に変えてはいけません。",
        "断定文を依頼文や質問文に変えてはいけません。文の役割はそのまま保ってください。",
        "できるだけ元の文を保ち、必要最小限の語尾修正だけを行ってください。",
        "original_text はユーザーの元発話であり、書き換え対象ではありません。original_text をそのまま返してはいけません。",
        instruction or "与えられた response_text の事実を変えずに、日本語の自然さだけを整えてください。",
        f"rewrite_style: {constraints.get('rewrite_style', 'natural_japanese')}",
        f"preserve_facts: {constraints.get('preserve_facts', True)}",
        f"forbid_code_generation: {constraints.get('forbid_code_generation', True)}",
        f"forbid_new_commands: {constraints.get('forbid_new_commands', True)}",
        f"forbid_markdown_blocks: {constraints.get('forbid_markdown_blocks', True)}",
        "出力は書き換え後の本文のみを返してください。",
        "もし自然に直す必要がほとんどないなら、response_text をほぼそのまま返してください。",
    ]

    user_lines = [
        f"intent: {intent}",
        f"dialogue_state: {dialogue_state}",
        f"task_name: {task_name}",
        f"action_status: {action_status}",
        f"reference_user_text: {original_text}",
        "次の response_text だけを書き換えてください。新しい文は足さないでください。",
        "response_text:",
        response_text,
    ]

    return [
        {"role": "system", "content": "\n".join(system_lines)},
        {"role": "user", "content": "\n".join(user_lines)},
    ]


def _load_model_and_tokenizer():
    global _MODEL, _TOKENIZER
    if _MODEL is not None and _TOKENIZER is not None:
        return _MODEL, _TOKENIZER

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as exc:
        raise RuntimeError(
            "transformers の import に失敗しました。仮想環境の Python で実行しているか確認してください。"
        ) from exc

    model_id = os.environ.get("QWEN_REWRITER_MODEL", DEFAULT_MODEL_ID)
    try:
        _TOKENIZER = AutoTokenizer.from_pretrained(model_id)
        _MODEL = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype="auto",
            low_cpu_mem_usage=True,
        )
    except Exception as exc:
        raise RuntimeError(
            f"モデル '{model_id}' の読み込みに失敗しました。Hugging Face への接続、ローカルキャッシュ、メモリ容量を確認してください。"
        ) from exc
    return _MODEL, _TOKENIZER


def run_rewrite(payload: dict) -> str:
    model, tokenizer = _load_model_and_tokenizer()
    messages = build_messages(payload)
    model_inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_tensors="pt",
        return_dict=True,
    )
    outputs = model.generate(
        **model_inputs,
        max_new_tokens=int(os.environ.get("QWEN_REWRITER_MAX_NEW_TOKENS", str(DEFAULT_MAX_NEW_TOKENS))),
        do_sample=False,
    )
    prompt_length = model_inputs["input_ids"].shape[-1]
    generated = outputs[0][prompt_length:]
    rewritten = tokenizer.decode(generated, skip_special_tokens=True).strip()
    return _postprocess_rewrite_output(payload, rewritten)


def _postprocess_rewrite_output(payload: dict, rewritten: str) -> str:
    original = payload.get("input", {}).get("response_text", "") or ""
    original_text = payload.get("input", {}).get("original_text", "") or ""
    if not rewritten:
        return original

    if original_text and rewritten == original_text and rewritten != original:
        return original

    banned_prefixes = ("こんにちは", "こんばんは", "はじめまして")
    if rewritten.startswith(banned_prefixes) and not original.startswith(banned_prefixes):
        return original

    if "？" in rewritten or "?" in rewritten:
        if "？" not in original and "?" not in original:
            return original

    if len(rewritten) > max(len(original) * 2, len(original) + 20):
        return original

    if original.endswith(_SENTENCE_FINAL_CHARS) and not rewritten.endswith(_SENTENCE_FINAL_CHARS):
        return original

    return rewritten


def main():
    payload = json.loads(sys.stdin.read() or "{}")
    try:
        rewritten = run_rewrite(payload)
    except Exception as exc:
        print(f"response_rewriter_qwen_cpu failed: {exc}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise SystemExit(1)

    sys.stdout.write(json.dumps({"text": rewritten}, ensure_ascii=False))


def serve_forever():
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            rewritten = run_rewrite(payload)
            sys.stdout.write(json.dumps({"text": rewritten}, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception as exc:
            print(f"response_rewriter_qwen_cpu failed: {exc}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            break


if __name__ == "__main__":
    main()
