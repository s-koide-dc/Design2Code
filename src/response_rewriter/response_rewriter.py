import logging
import json
import subprocess
import os
import sys
import queue
import threading
import atexit
from urllib import error as urllib_error
from urllib import request as urllib_request
from dataclasses import dataclass
from pathlib import Path
from src.utils.dialogue_state import PENDING_CONFIRMATION, TASK_CLARIFICATION

_SENTENCE_FINAL_CHARS = ("。", "！", "？", ".", "!", "?", "」", "』", '"', "'")


def build_rewrite_messages(payload: dict) -> list[dict]:
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


@dataclass
class RewriteRequest:
    response_text: str
    original_text: str
    intent: str | None
    dialogue_state: str | None
    task_name: str | None
    action_status: str | None


class ResponseRewritePlugin:
    def rewrite(self, request: RewriteRequest) -> str | None:
        raise NotImplementedError


class NoOpResponseRewritePlugin(ResponseRewritePlugin):
    def rewrite(self, request: RewriteRequest) -> str | None:
        return request.response_text


class SubprocessResponseRewritePlugin(ResponseRewritePlugin):
    def __init__(self, command, timeout_seconds=5, response_format="json", payload_builder=None):
        self.command = command or []
        self.timeout_seconds = timeout_seconds
        self.response_format = response_format
        self.payload_builder = payload_builder

    def rewrite(self, request: RewriteRequest) -> str | None:
        if not isinstance(self.command, list) or not self.command:
            return None

        payload = self.payload_builder(request) if self.payload_builder else {
            "response_text": request.response_text,
            "original_text": request.original_text,
            "intent": request.intent,
            "dialogue_state": request.dialogue_state,
            "task_name": request.task_name,
            "action_status": request.action_status,
        }
        completed = subprocess.run(
            self.command,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=self.timeout_seconds,
            check=False,
            shell=False,
        )
        if completed.returncode != 0:
            return None

        stdout_text = (completed.stdout or "").strip()
        if not stdout_text:
            return None

        if self.response_format == "text":
            return stdout_text

        data = json.loads(stdout_text)
        if isinstance(data, dict):
            return data.get("text")
        return None


class PersistentSubprocessResponseRewritePlugin(ResponseRewritePlugin):
    def __init__(self, command, timeout_seconds=5, response_format="json", payload_builder=None):
        self.command = command or []
        self.timeout_seconds = timeout_seconds
        self.response_format = response_format
        self.payload_builder = payload_builder
        self._lock = threading.Lock()
        self._process = None
        self._stdout_queue = None
        self._stderr_queue = None
        atexit.register(self.close)

    def _start_process(self):
        if not isinstance(self.command, list) or not self.command:
            return False
        if self._process is not None and self._process.poll() is None:
            return True

        self.close()
        self._process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            shell=False,
            bufsize=1,
        )
        self._stdout_queue = queue.Queue()
        self._stderr_queue = queue.Queue()
        threading.Thread(
            target=self._pump_stream,
            args=(self._process.stdout, self._stdout_queue),
            daemon=True,
        ).start()
        threading.Thread(
            target=self._pump_stream,
            args=(self._process.stderr, self._stderr_queue),
            daemon=True,
        ).start()
        return True

    @staticmethod
    def _pump_stream(stream, target_queue):
        try:
            for line in iter(stream.readline, ""):
                target_queue.put(line)
        finally:
            target_queue.put(None)

    def close(self):
        process = self._process
        self._process = None
        self._stdout_queue = None
        self._stderr_queue = None
        if process is None:
            return
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=1)
            except Exception:
                process.kill()
                process.wait(timeout=1)
        for stream_name in ("stdin", "stdout", "stderr"):
            stream = getattr(process, stream_name, None)
            if stream is None:
                continue
            try:
                stream.close()
            except Exception:
                pass

    def _read_response_line(self, target_queue):
        line = target_queue.get(timeout=self.timeout_seconds)
        if line is None:
            return None
        return line.rstrip("\r\n")

    def rewrite(self, request: RewriteRequest) -> str | None:
        payload = self.payload_builder(request) if self.payload_builder else {
            "response_text": request.response_text,
            "original_text": request.original_text,
            "intent": request.intent,
            "dialogue_state": request.dialogue_state,
            "task_name": request.task_name,
            "action_status": request.action_status,
        }
        with self._lock:
            if not self._start_process():
                return None
            if self._process.poll() is not None or self._process.stdin is None:
                return None
            try:
                self._process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                self._process.stdin.flush()
                stdout_text = self._read_response_line(self._stdout_queue)
            except (OSError, queue.Empty):
                self.close()
                return None

            if self._process.poll() is not None:
                self.close()
                return None

        if not stdout_text:
            return None

        if self.response_format == "text":
            return stdout_text

        data = json.loads(stdout_text)
        if isinstance(data, dict):
            return data.get("text")
        return None


class OpenAICompatibleHttpResponseRewritePlugin(ResponseRewritePlugin):
    def __init__(self, endpoint_url, model, timeout_seconds=30, api_key=None, max_new_tokens=32, payload_builder=None):
        self.endpoint_url = endpoint_url or ""
        self.model = model or ""
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key
        self.max_new_tokens = max_new_tokens
        self.payload_builder = payload_builder

    def rewrite(self, request: RewriteRequest) -> str | None:
        if not self.endpoint_url or not self.model:
            return None

        payload = self.payload_builder(request) if self.payload_builder else {
            "response_text": request.response_text,
            "original_text": request.original_text,
            "intent": request.intent,
            "dialogue_state": request.dialogue_state,
            "task_name": request.task_name,
            "action_status": request.action_status,
        }
        body = {
            "model": self.model,
            "messages": build_rewrite_messages(payload),
            "temperature": 0,
            "max_tokens": self.max_new_tokens,
            "stream": False,
        }
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request_obj = urllib_request.Request(
            self.endpoint_url,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib_request.urlopen(request_obj, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except (urllib_error.URLError, TimeoutError, OSError):
            return None

        response_json = json.loads(response_body)
        choices = response_json.get("choices", [])
        if not choices:
            return None
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            return "".join(text_parts) or None
        return None


class ResponseRewriter:
    def __init__(self, config_manager=None, plugin=None):
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.config = {}
        if config_manager and hasattr(config_manager, "response_rewriter_config"):
            self.config = config_manager.response_rewriter_config or {}
        self.plugin = plugin or self._build_plugin()

    def _build_plugin(self) -> ResponseRewritePlugin:
        provider = self.config.get("provider", "none")
        if provider == "subprocess_stdio":
            return SubprocessResponseRewritePlugin(
                command=self._resolve_command(self.config.get("command", [])),
                timeout_seconds=int(self.config.get("timeout_seconds", 5)),
                response_format=self.config.get("response_format", "json"),
                payload_builder=self._build_backend_payload,
            )
        if provider == "persistent_subprocess_jsonl":
            return PersistentSubprocessResponseRewritePlugin(
                command=self._resolve_command(self.config.get("command", [])),
                timeout_seconds=int(self.config.get("timeout_seconds", 5)),
                response_format=self.config.get("response_format", "json"),
                payload_builder=self._build_backend_payload,
            )
        if provider == "openai_compatible_http":
            return OpenAICompatibleHttpResponseRewritePlugin(
                endpoint_url=self.config.get("endpoint_url", ""),
                model=self.config.get("model", ""),
                timeout_seconds=int(self.config.get("timeout_seconds", 30)),
                api_key=self.config.get("api_key"),
                max_new_tokens=int(self.config.get("max_new_tokens", 32)),
                payload_builder=self._build_backend_payload,
            )
        return NoOpResponseRewritePlugin()

    def _resolve_command(self, command) -> list[str]:
        if not isinstance(command, list):
            return []

        workspace_root = None
        if self.config_manager and hasattr(self.config_manager, "workspace_root"):
            workspace_root = str(self.config_manager.workspace_root)
        else:
            workspace_root = os.getcwd()

        resolved = []
        for item in command:
            if not isinstance(item, str):
                continue
            value = item.replace("${PYTHON_EXECUTABLE}", sys.executable)
            value = value.replace("${WORKSPACE_ROOT}", workspace_root)
            if value.startswith(".\\") or value.startswith("./"):
                value = str(Path(workspace_root) / value[2:])
            resolved.append(value)
        return resolved

    def is_enabled(self) -> bool:
        return bool(self.config.get("enabled", False))

    def _normalize_allowed_values(self, values) -> set[str]:
        if not isinstance(values, list):
            return set()
        return {
            str(value).strip()
            for value in values
            if isinstance(value, str) and value.strip()
        }

    def _default_allowed_intents(self) -> set[str]:
        return set()

    def _is_allowed_intent(self, intent: str | None) -> bool:
        if intent is None:
            return False
        if "rewrite_allowed_intents" in self.config:
            allowed_intents = self._normalize_allowed_values(
                self.config.get("rewrite_allowed_intents")
            )
        else:
            allowed_intents = self._default_allowed_intents()
        return intent in allowed_intents

    def _is_allowed_action_status(self, action_status: str | None) -> bool:
        allowed_statuses = self._normalize_allowed_values(
            self.config.get("rewrite_allowed_action_statuses")
        )
        if not allowed_statuses:
            return True
        if action_status is None:
            return True
        return action_status in allowed_statuses

    def _contains_structured_output(self, text: str) -> bool:
        if not text:
            return False
        return "```" in text or "```mermaid" in text or "![" in text

    def _breaks_sentence_ending(self, original_text: str, rewritten_text: str) -> bool:
        if not original_text or not rewritten_text:
            return False
        return original_text.endswith(_SENTENCE_FINAL_CHARS) and not rewritten_text.endswith(
            _SENTENCE_FINAL_CHARS
        )

    def _build_request(self, context, response_text: str) -> RewriteRequest:
        task = context.get("task", {})
        action_result = context.get("action_result", {})
        analysis = context.get("analysis", {})
        return RewriteRequest(
            response_text=response_text,
            original_text=context.get("original_text", ""),
            intent=analysis.get("intent"),
            dialogue_state=context.get("dialogue_state"),
            task_name=task.get("name"),
            action_status=action_result.get("status"),
        )

    def _build_backend_payload(self, request: RewriteRequest) -> dict:
        prompt_contract = self.config.get("prompt_contract", {})
        return {
            "contract_version": "1.0",
            "mode": "rewrite_response_text",
            "input": {
                "response_text": request.response_text,
                "original_text": request.original_text,
                "intent": request.intent,
                "dialogue_state": request.dialogue_state,
                "task_name": request.task_name,
                "action_status": request.action_status,
            },
            "constraints": {
                "rewrite_style": prompt_contract.get("rewrite_style", "natural_japanese"),
                "preserve_facts": True,
                "forbid_code_generation": True,
                "forbid_new_commands": True,
                "forbid_markdown_blocks": True,
                "max_length_ratio": float(self.config.get("max_length_ratio", 1.6)),
            },
            "instruction": prompt_contract.get(
                "instruction",
                "与えられた response_text の事実を変えずに、日本語の自然さだけを整えてください。"
            ),
        }

    def should_rewrite(self, context, response_text: str) -> bool:
        if not self.is_enabled():
            return False
        if not response_text or not response_text.strip():
            return False
        if self._contains_structured_output(response_text):
            return False
        max_chars = int(self.config.get("max_input_chars", 1200))
        if len(response_text) > max_chars:
            return False
        dialogue_state = context.get("dialogue_state")
        allow_confirmation = bool(self.config.get("rewrite_confirmation_messages", False))
        if dialogue_state == PENDING_CONFIRMATION and not allow_confirmation:
            return False
        allow_clarification = bool(self.config.get("rewrite_clarification_messages", False))
        if (
            (dialogue_state == TASK_CLARIFICATION or context.get("clarification_needed"))
            and not allow_clarification
        ):
            return False
        allow_error = bool(self.config.get("rewrite_error_messages", False))
        action_status = context.get("action_result", {}).get("status")
        if action_status == "error" and not allow_error:
            return False
        if dialogue_state == PENDING_CONFIRMATION and allow_confirmation:
            return True
        if (dialogue_state == TASK_CLARIFICATION or context.get("clarification_needed")) and allow_clarification:
            return True
        analysis = context.get("analysis", {})
        intent = analysis.get("intent")
        if not self._is_allowed_intent(intent):
            return False
        if not self._is_allowed_action_status(action_status):
            return False
        return True

    def rewrite(self, context, response_text: str) -> str:
        if not self.should_rewrite(context, response_text):
            return response_text

        try:
            request = self._build_request(context, response_text)
            rewritten = self.plugin.rewrite(request)
        except Exception as exc:
            self.logger.warning("response rewrite failed: %s", exc)
            return response_text

        if not isinstance(rewritten, str):
            return response_text
        rewritten = rewritten.strip()
        if not rewritten:
            return response_text
        if request.original_text and rewritten == request.original_text and rewritten != response_text:
            return response_text
        if self._contains_structured_output(rewritten):
            return response_text
        if self._breaks_sentence_ending(response_text, rewritten):
            return response_text

        max_ratio = float(self.config.get("max_length_ratio", 1.6))
        if len(rewritten) > max(1, int(len(response_text) * max_ratio)):
            return response_text
        return rewritten
