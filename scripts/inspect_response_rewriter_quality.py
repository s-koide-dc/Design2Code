# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.response_rewriter.response_rewriter import ResponseRewriter
from src.utils.cli_output import emit_error, emit_json_stdout
from src.utils.dialogue_state import PENDING_CONFIRMATION, TASK_CLARIFICATION


DEFAULT_CASES = [
    {
        "id": "deterministic_result_pending_should_stay",
        "family": "deterministic_progress",
        "description": "結果待ちの標準進捗文は既定でそのまま維持する",
        "context": {
            "analysis": {"intent": "GENERAL"},
            "dialogue_state": "",
            "original_text": "進捗を教えて",
            "action_result": {"status": "in_progress"},
        },
        "response_text": "確認を進めています。結果がまとまりしだいお伝えします。",
        "expected_rewrite": False,
    },
    {
        "id": "deterministic_task_in_progress_should_stay",
        "family": "deterministic_progress",
        "description": "標準の進捗テンプレートは既定でそのまま維持する",
        "context": {
            "analysis": {"intent": "GENERAL"},
            "dialogue_state": "",
            "original_text": "sample.py はどう？",
            "action_result": {"status": "in_progress"},
        },
        "response_text": "GENERATE_TESTSを進めています。対象はsrc/sample.pyです。完了したらお知らせします。",
        "expected_rewrite": False,
    },
    {
        "id": "deterministic_awaiting_input_should_stay",
        "family": "deterministic_progress",
        "description": "標準の入力待ちテンプレートは既定でそのまま維持する",
        "context": {
            "analysis": {"intent": "GENERAL"},
            "dialogue_state": TASK_CLARIFICATION,
            "clarification_needed": True,
            "original_text": "ファイルを作って",
            "action_result": {"status": "success"},
        },
        "response_text": "FILE_CREATEを進めるために、ファイル名を教えてください。",
        "expected_rewrite": False,
    },
    {
        "id": "deterministic_awaiting_approval_should_stay",
        "family": "deterministic_progress",
        "description": "標準の承認待ちテンプレートは既定でそのまま維持する",
        "context": {
            "analysis": {"intent": "GENERAL"},
            "dialogue_state": PENDING_CONFIRMATION,
            "original_text": "dir を実行して",
            "action_result": {"status": "success"},
        },
        "response_text": "CMD_RUNを進める前に、対象のdirについて承認をお願いします。",
        "expected_rewrite": False,
    },
    {
        "id": "deterministic_action_success_should_stay",
        "family": "deterministic_success",
        "description": "標準の成功応答テンプレートは既定でそのまま維持する",
        "context": {
            "analysis": {"intent": "GENERATE_TESTS"},
            "dialogue_state": "",
            "original_text": "sample.py はどう？",
            "action_result": {"status": "success"},
        },
        "response_text": "GENERATE_TESTSが完了しました。対象は src/sample.py です。",
        "expected_rewrite": False,
    },
    {
        "id": "smalltalk_with_status",
        "family": "excluded_conversational",
        "description": "雑談系応答も既定では rewrite せず維持する",
        "context": {
            "analysis": {"intent": "SMALLTALK"},
            "dialogue_state": "",
            "original_text": "雑談しよう",
            "action_result": {"status": "success"},
        },
        "response_text": "もちろんです。少しお話ししましょうか。",
        "expected_rewrite": False,
    },
    {
        "id": "greeting_short_reply",
        "family": "excluded_conversational",
        "description": "挨拶応答は既定では rewrite せず維持する",
        "context": {
            "analysis": {"intent": "GREETING"},
            "dialogue_state": "",
            "original_text": "こんにちは",
            "action_result": {"status": "success"},
        },
        "response_text": "こんにちは！",
        "expected_rewrite": False,
    },
    {
        "id": "bye_short_reply",
        "family": "excluded_conversational",
        "description": "別れの挨拶は既定では rewrite せず維持する",
        "context": {
            "analysis": {"intent": "BYE"},
            "dialogue_state": "",
            "original_text": "またね",
            "action_result": {"status": "success"},
        },
        "response_text": "またお話ししましょう。",
        "expected_rewrite": False,
    },
    {
        "id": "personal_q_profile_reply",
        "family": "excluded_conversational",
        "description": "自己紹介系応答は既定では rewrite せず維持する",
        "context": {
            "analysis": {"intent": "PERSONAL_Q"},
            "dialogue_state": "",
            "original_text": "あなたは誰？",
            "action_result": {"status": "success"},
        },
        "response_text": "私はあなたのパーソナルAIアシスタントです。いろいろな言葉について教えたり、お話ししたりするのが好きですよ。",
        "expected_rewrite": False,
    },
    {
        "id": "definition_agent_reply",
        "family": "excluded_conversational",
        "description": "定義説明応答は既定では rewrite せず維持する",
        "context": {
            "analysis": {"intent": "DEFINITION"},
            "dialogue_state": "",
            "original_text": "エージェントって何？",
            "action_result": {"status": "success"},
        },
        "response_text": "エージェントは、ユーザーの代わりに特定のタスクやアクションを実行するソフトウェアです。",
        "expected_rewrite": False,
    },
    {
        "id": "emotive_support_reply",
        "family": "excluded_conversational",
        "description": "感情応答は既定では rewrite せず維持する",
        "context": {
            "analysis": {"intent": "EMOTIVE"},
            "dialogue_state": "",
            "original_text": "少し疲れた",
            "action_result": {"status": "success"},
        },
        "response_text": "お気持ち、お察しします。何か力になれることがあれば言ってくださいね。",
        "expected_rewrite": False,
    },
    {
        "id": "feedback_thanks_reply",
        "family": "excluded_conversational",
        "description": "感謝への応答は既定では rewrite せず維持する",
        "context": {
            "analysis": {"intent": "FEEDBACK"},
            "dialogue_state": "",
            "original_text": "ありがとう",
            "action_result": {"status": "success"},
        },
        "response_text": "ありがとうございます。そう言っていただけると助かります。",
        "expected_rewrite": False,
    },
    {
        "id": "action_completion_must_stay_deterministic",
        "family": "must_preserve",
        "description": "作業系成功応答は既定では rewrite しない",
        "context": {
            "analysis": {"intent": "FILE_CREATE"},
            "dialogue_state": "",
            "original_text": "sample.txt を作って",
            "action_result": {"status": "success"},
        },
        "response_text": "ファイル 'sample.txt' を作成しました。",
        "expected_rewrite": False,
    },
    {
        "id": "error_message_must_not_rewrite",
        "family": "must_preserve",
        "description": "エラー応答は既定では rewrite しない",
        "context": {
            "analysis": {"intent": "GENERAL"},
            "dialogue_state": "",
            "original_text": "何が起きた？",
            "action_result": {"status": "error"},
        },
        "response_text": "処理中に問題が発生しました。内容を確認してください。",
        "expected_rewrite": False,
    },
    {
        "id": "confirmation_must_not_rewrite",
        "family": "must_preserve",
        "description": "承認待ち文面は既定では rewrite しない",
        "context": {
            "analysis": {"intent": "FILE_DELETE"},
            "dialogue_state": PENDING_CONFIRMATION,
            "original_text": "このファイルを消して",
            "action_result": {"status": "success"},
        },
        "response_text": "ファイルを削除します。よろしいですか？",
        "expected_rewrite": False,
    },
    {
        "id": "clarification_must_not_rewrite",
        "family": "must_preserve",
        "description": "補足質問は既定では rewrite しない",
        "context": {
            "analysis": {"intent": "FILE_CREATE"},
            "dialogue_state": TASK_CLARIFICATION,
            "clarification_needed": True,
            "original_text": "ファイルを作って",
            "action_result": {"status": "success"},
        },
        "response_text": "ファイル名を教えていただけますか？",
        "expected_rewrite": False,
    },
]


class _Config:
    def __init__(self, workspace_root: Path, config: dict):
        self.workspace_root = workspace_root
        self.response_rewriter_config = config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect response rewriter quality across fixed cases."
    )
    parser.add_argument(
        "--cases-file",
        help="Optional JSON file containing quality inspection cases.",
    )
    parser.add_argument(
        "--family",
        action="append",
        dest="families",
        help="Optional case family filter. Repeatable.",
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
        default=30,
        help="Backend timeout in seconds.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=32,
        help="Generation cap for compatible backends.",
    )
    return parser.parse_args()


def _load_cases(args: argparse.Namespace) -> list[dict]:
    if not args.cases_file:
        cases = DEFAULT_CASES
    else:
        cases_path = Path(args.cases_file)
        if not cases_path.is_file():
            raise FileNotFoundError(f"cases file not found: {cases_path}")
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
        if not isinstance(cases, list):
            raise ValueError("cases file must contain a JSON array")

    requested_families = set(args.families or [])
    if requested_families:
        cases = [
            case for case in cases
            if case.get("family", "uncategorized") in requested_families
        ]
    return cases


def _build_config(args: argparse.Namespace) -> dict:
    config = {
        "enabled": True,
        "provider": args.provider,
        "timeout_seconds": args.timeout_seconds,
        "prompt_contract": {
            "rewrite_style": "natural_japanese",
            "instruction": "与えられた response_text の事実を変えず、日本語の自然さだけを最小限に整えてください。新しい情報、質問、挨拶、提案は追加しないでください。主語・話者・視点・文の役割は変えないでください。"
        },
        "rewrite_allowed_intents": [],
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


def _inspect_case(rewriter: ResponseRewriter, case: dict) -> dict:
    context = case.get("context", {})
    response_text = case.get("response_text", "")
    original_text = context.get("original_text", "")
    intent = context.get("analysis", {}).get("intent", "")
    family = case.get("family", "uncategorized")
    expected_rewrite = bool(case.get("expected_rewrite", True))
    eligible = rewriter.should_rewrite(context, response_text)
    rewritten = rewriter.rewrite(context, response_text)
    changed = rewritten != response_text

    if expected_rewrite and original_text and rewritten == original_text and rewritten != response_text:
        assessment = "semantic_regression"
    elif expected_rewrite and changed:
        assessment = "rewritten"
    elif expected_rewrite and not changed:
        assessment = "no_effect"
    elif not expected_rewrite and not changed:
        assessment = "preserved_as_expected"
    else:
        assessment = "unexpected_rewrite"

    return {
        "id": case.get("id", ""),
        "family": family,
        "intent": intent,
        "description": case.get("description", ""),
        "expected_rewrite": expected_rewrite,
        "eligible_by_gate": eligible,
        "changed": changed,
        "assessment": assessment,
        "original_response_text": response_text,
        "rewritten_response_text": rewritten,
    }


def _build_family_summary(results: list[dict]) -> dict:
    family_summary: dict[str, dict] = {}
    for item in results:
        family = item.get("family", "uncategorized")
        family_bucket = family_summary.setdefault(
            family,
            {
                "total_cases": 0,
                "rewritten": 0,
                "no_effect": 0,
                "semantic_regression": 0,
                "preserved_as_expected": 0,
                "unexpected_rewrite": 0,
            },
        )
        family_bucket["total_cases"] += 1
        assessment = item.get("assessment")
        if assessment in family_bucket:
            family_bucket[assessment] += 1
    return family_summary


def _build_case_ids_by_assessment(results: list[dict]) -> dict:
    grouped: dict[str, list[str]] = {}
    for item in results:
        assessment = item.get("assessment", "unknown")
        grouped.setdefault(assessment, []).append(item.get("id", ""))
    return grouped


def main() -> int:
    args = _parse_args()
    try:
        cases = _load_cases(args)
        config = _build_config(args)
    except (FileNotFoundError, ValueError) as exc:
        emit_error(str(exc))
        return 1

    rewriter = ResponseRewriter(config_manager=_Config(WORKSPACE_ROOT, config))
    results = []
    for case in cases:
        results.append(_inspect_case(rewriter, case))

    summary = {
        "total_cases": len(results),
        "rewritten": sum(1 for item in results if item["assessment"] == "rewritten"),
        "no_effect": sum(1 for item in results if item["assessment"] == "no_effect"),
        "semantic_regression": sum(1 for item in results if item["assessment"] == "semantic_regression"),
        "preserved_as_expected": sum(1 for item in results if item["assessment"] == "preserved_as_expected"),
        "unexpected_rewrite": sum(1 for item in results if item["assessment"] == "unexpected_rewrite"),
    }
    emit_json_stdout(
        {
            "provider": args.provider,
            "model_id": args.model_id,
            "endpoint_url": args.endpoint_url,
            "requested_families": args.families or [],
            "summary": summary,
            "family_summary": _build_family_summary(results),
            "case_ids_by_assessment": _build_case_ids_by_assessment(results),
            "results": results,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
