# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.utils.cli_output import emit_error, emit_json_stdout


DEFAULT_TURNS = [
    "雑談しよう",
    "ファイルを作って",
    "雑談しよう",
    "sample.txt",
    "内容は「こんにちは」です",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a multi-turn conversation probe against the response rewriter backend."
    )
    parser.add_argument(
        "--turns-file",
        help="Optional JSON file containing an array of user utterances.",
    )
    parser.add_argument(
        "--provider",
        choices=["openai_compatible_http", "persistent_subprocess_jsonl", "subprocess_stdio"],
        default="openai_compatible_http",
        help="Response rewriter backend provider to use.",
    )
    parser.add_argument(
        "--endpoint-url",
        help="OpenAI compatible /v1/chat/completions endpoint for http provider.",
    )
    parser.add_argument(
        "--model-id",
        help="Model id for the selected backend.",
    )
    parser.add_argument(
        "--command",
        nargs="+",
        help="Backend command for subprocess providers.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=10,
        help="Backend timeout in seconds.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=32,
        help="Generation cap for compatible backends.",
    )
    return parser.parse_args()


def _load_turns(args: argparse.Namespace) -> list[str]:
    if not args.turns_file:
        return DEFAULT_TURNS

    turns_path = Path(args.turns_file)
    if not turns_path.is_file():
        raise FileNotFoundError(f"turns file not found: {turns_path}")
    turns = json.loads(turns_path.read_text(encoding="utf-8"))
    if not isinstance(turns, list) or not all(isinstance(item, str) for item in turns):
        raise ValueError("turns file must contain a JSON array of strings")
    return turns


def _build_rewriter_config(args: argparse.Namespace) -> dict:
    config = {
        "enabled": True,
        "provider": args.provider,
        "timeout_seconds": args.timeout_seconds,
        "prompt_contract": {
            "rewrite_style": "natural_japanese",
            "instruction": "与えられた response_text の事実を変えず、日本語の自然さだけを最小限に整えてください。新しい情報、質問、挨拶、提案は追加しないでください。主語・話者・視点・文の役割は変えないでください。"
        },
        "rewrite_allowed_intents": [
            "SMALLTALK",
        ],
        "rewrite_allowed_action_statuses": ["success"],
        "max_input_chars": 1200,
        "max_length_ratio": 1.6,
        "rewrite_confirmation_messages": False,
        "rewrite_clarification_messages": False,
        "rewrite_error_messages": False,
    }
    if args.provider == "openai_compatible_http":
        if not args.endpoint_url:
            raise ValueError("--endpoint-url is required for openai_compatible_http")
        if not args.model_id:
            raise ValueError("--model-id is required for openai_compatible_http")
        config.update(
            {
                "endpoint_url": args.endpoint_url,
                "model": args.model_id,
                "max_new_tokens": args.max_new_tokens,
            }
        )
    else:
        if not args.command:
            raise ValueError("--command is required for subprocess providers")
        config.update(
            {
                "command": args.command,
                "response_format": "json",
            }
        )
    return config


def _run_probe(turns: list[str], config: dict) -> dict:
    try:
        from src.pipeline_core.pipeline_core import Pipeline
    except ModuleNotFoundError as exc:
        if exc.name == "janome":
            raise RuntimeError(
                "run_response_rewriter_conversation_probe.py は Pipeline を使うため janome が必要です。"
                " `.venv-rewriter` ではなく、`pip install -r requirements.txt` 済みの通常環境の Python で実行してください。"
            ) from exc
        raise

    pipeline = Pipeline(is_test_mode=True)
    pipeline.config_manager.response_rewriter_config = config
    pipeline._response_generator = None
    generator = pipeline.response_generator
    rewriter = generator.response_rewriter
    original_rewrite = rewriter.rewrite

    rewrite_trace = {
        "pre_rewrite_text": None,
        "post_rewrite_text": None,
    }

    def traced_rewrite(context, response_text):
        rewrite_trace["pre_rewrite_text"] = response_text
        rewritten = original_rewrite(context, response_text)
        rewrite_trace["post_rewrite_text"] = rewritten
        return rewritten

    rewriter.rewrite = traced_rewrite

    turn_results = []
    for index, utterance in enumerate(turns, start=1):
        rewrite_trace["pre_rewrite_text"] = None
        rewrite_trace["post_rewrite_text"] = None
        result = pipeline.run(utterance)
        turn_results.append(
            {
                "turn": index,
                "user_text": utterance,
                "intent": result.get("analysis", {}).get("intent"),
                "clarification_needed": bool(result.get("clarification_needed", False)),
                "dialogue_state": result.get("dialogue_state"),
                "pre_rewrite_text": rewrite_trace["pre_rewrite_text"],
                "rewrite_applied": (
                    rewrite_trace["pre_rewrite_text"] is not None
                    and rewrite_trace["post_rewrite_text"] is not None
                    and rewrite_trace["pre_rewrite_text"] != rewrite_trace["post_rewrite_text"]
                ),
                "response_text": result.get("response", {}).get("text", ""),
            }
        )
    return {
        "turn_count": len(turn_results),
        "results": turn_results,
    }


def main() -> int:
    args = _parse_args()
    try:
        turns = _load_turns(args)
        config = _build_rewriter_config(args)
    except (FileNotFoundError, ValueError) as exc:
        emit_error(str(exc))
        return 1

    try:
        probe = _run_probe(turns, config)
    except Exception as exc:
        emit_error(str(exc))
        return 1

    emit_json_stdout(
        {
            "provider": args.provider,
            "model_id": args.model_id,
            "endpoint_url": args.endpoint_url,
            "turns": turns,
            "probe": probe,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
