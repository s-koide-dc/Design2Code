# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.utils.cli_output import emit_error, emit_json_stdout


DEFAULT_PAYLOAD = {
    "contract_version": "1.0",
    "mode": "rewrite_response_text",
    "input": {
        "response_text": "元の応答です。",
        "original_text": "元の応答です。",
        "intent": "GENERAL",
        "dialogue_state": "",
        "task_name": "",
        "action_status": "success",
    },
    "constraints": {
        "rewrite_style": "natural_japanese",
        "preserve_facts": True,
        "forbid_code_generation": True,
        "forbid_new_commands": True,
        "forbid_markdown_blocks": True,
        "max_length_ratio": 1.6,
    },
    "instruction": "与えられた response_text の事実を変えず、日本語の自然さだけを最小限に整えてください。新しい情報、質問、挨拶、提案は追加しないでください。",
}


def _default_persistent_command(workspace_root: Path) -> list[str]:
    return [
        sys.executable,
        str(workspace_root / "scripts" / "response_rewriter_qwen_cpu_server.py"),
    ]


def _default_oneshot_command(workspace_root: Path) -> list[str]:
    return [
        sys.executable,
        str(workspace_root / "scripts" / "response_rewriter_qwen_cpu.py"),
    ]


def _measure_oneshot(command: list[str], payload: dict, iterations: int) -> dict:
    timings_ms = []
    last_output = None
    payload_text = json.dumps(payload, ensure_ascii=False)
    for _ in range(iterations):
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            input=payload_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            shell=False,
            env=os.environ.copy(),
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or "one-shot backend failed").strip())
        timings_ms.append(elapsed_ms)
        last_output = (completed.stdout or "").strip()
    return _build_summary("oneshot", timings_ms, last_output)


def _measure_persistent(command: list[str], payload: dict, iterations: int) -> dict:
    timings_ms = []
    last_output = None
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        shell=False,
        bufsize=1,
        env=os.environ.copy(),
    )
    try:
        if process.stdin is None or process.stdout is None:
            raise RuntimeError("persistent backend stdio is unavailable")

        payload_line = json.dumps(payload, ensure_ascii=False) + "\n"
        for _ in range(iterations):
            started = time.perf_counter()
            process.stdin.write(payload_line)
            process.stdin.flush()
            stdout_line = process.stdout.readline()
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if not stdout_line:
                stderr_text = ""
                if process.stderr is not None:
                    stderr_text = process.stderr.read().strip()
                raise RuntimeError(stderr_text or "persistent backend returned no output")
            timings_ms.append(elapsed_ms)
            last_output = stdout_line.strip()
    finally:
        for stream_name in ("stdin", "stdout", "stderr"):
            stream = getattr(process, stream_name, None)
            if stream is None:
                continue
            try:
                stream.close()
            except Exception:
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
    return _build_summary("persistent", timings_ms, last_output)


def _measure_http(endpoint_url: str, model: str, payload: dict, iterations: int, max_new_tokens: int | None) -> dict:
    if not endpoint_url:
        raise RuntimeError("endpoint_url is required for http mode")
    if not model:
        raise RuntimeError("model id is required for http mode")

    from src.response_rewriter.qwen_cpu_runner import build_messages

    timings_ms = []
    last_output = None
    body = {
        "model": model,
        "messages": build_messages(payload),
        "temperature": 0,
        "stream": False,
    }
    if max_new_tokens is not None:
        body["max_tokens"] = max_new_tokens

    headers = {
        "Content-Type": "application/json",
    }
    encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
    for _ in range(iterations):
        request_obj = urllib_request.Request(
            endpoint_url,
            data=encoded,
            headers=headers,
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib_request.urlopen(request_obj, timeout=300) as response:
                response_body = response.read().decode("utf-8")
        except (urllib_error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(str(exc)) from exc
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        timings_ms.append(elapsed_ms)
        last_output = response_body.strip()

    return _build_summary("http", timings_ms, last_output)


def _build_summary(mode: str, timings_ms: list[float], last_output: str | None) -> dict:
    return {
        "mode": mode,
        "iterations": len(timings_ms),
        "first_ms": round(timings_ms[0], 3),
        "avg_ms": round(sum(timings_ms) / len(timings_ms), 3),
        "median_ms": round(statistics.median(timings_ms), 3),
        "min_ms": round(min(timings_ms), 3),
        "max_ms": round(max(timings_ms), 3),
        "timings_ms": [round(value, 3) for value in timings_ms],
        "last_output": last_output,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure one-shot vs persistent response rewriter latency."
    )
    parser.add_argument(
        "--mode",
        choices=["persistent", "oneshot", "both", "http"],
        default="both",
        help="Which execution mode to measure.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="How many requests to issue per mode.",
    )
    parser.add_argument(
        "--command",
        nargs="+",
        help="Override backend command. When set, the same command is used for the selected mode(s).",
    )
    parser.add_argument(
        "--payload-file",
        help="Optional JSON file containing the rewrite payload contract.",
    )
    parser.add_argument(
        "--model-id",
        help="Optional Qwen model id to inject via QWEN_REWRITER_MODEL.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        help="Optional generation cap to inject via QWEN_REWRITER_MAX_NEW_TOKENS.",
    )
    parser.add_argument(
        "--endpoint-url",
        help="OpenAI compatible /v1/chat/completions endpoint for http mode.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.iterations <= 0:
        emit_error("--iterations must be >= 1")
        return 1

    workspace_root = WORKSPACE_ROOT
    payload = DEFAULT_PAYLOAD
    if args.model_id:
        os.environ["QWEN_REWRITER_MODEL"] = args.model_id
    if args.max_new_tokens is not None:
        if args.max_new_tokens <= 0:
            emit_error("--max-new-tokens must be >= 1")
            return 1
        os.environ["QWEN_REWRITER_MAX_NEW_TOKENS"] = str(args.max_new_tokens)
    if args.payload_file:
        payload_path = Path(args.payload_file)
        if not payload_path.is_file():
            emit_error(f"payload file not found: {payload_path}")
            return 1
        payload = json.loads(payload_path.read_text(encoding="utf-8"))

    results = []
    try:
        if args.mode in ("oneshot", "both"):
            oneshot_command = args.command or _default_oneshot_command(workspace_root)
            results.append(_measure_oneshot(oneshot_command, payload, args.iterations))
        if args.mode in ("persistent", "both"):
            persistent_command = args.command or _default_persistent_command(workspace_root)
            results.append(_measure_persistent(persistent_command, payload, args.iterations))
        if args.mode == "http":
            results.append(
                _measure_http(
                    endpoint_url=args.endpoint_url or "",
                    model=args.model_id or "",
                    payload=payload,
                    iterations=args.iterations,
                    max_new_tokens=args.max_new_tokens,
                )
            )
    except Exception as exc:
        emit_error(str(exc))
        return 1

    emit_json_stdout(
        {
            "cwd": os.getcwd(),
            "python_executable": sys.executable,
            "iterations": args.iterations,
            "model_id": os.environ.get("QWEN_REWRITER_MODEL"),
            "max_new_tokens": int(os.environ.get("QWEN_REWRITER_MAX_NEW_TOKENS", "0")) or None,
            "results": results,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
