# -*- coding: utf-8 -*-
# src/autonomous_learning/event_processor.py

import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

class EventProcessor:
    """イベント駆動学習（Fast Path）を担当するクラス"""

    def __init__(self, workspace_root: Path, repair_kb=None):
        self.workspace_root = workspace_root
        self.repair_kb = repair_kb
        self.learning_queue_dir = self.workspace_root / 'logs' / 'learning_queue'
        self.learning_queue_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def process_event(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """イベントを処理し、必要に応じて即時学習を行う"""
        try:
            timestamp = datetime.now().isoformat()
            event_id = f"{event_type}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

            # イベントをキューに保存（後続のバッチ処理や分析のため）
            self._save_event(event_id, event_type, data, timestamp)

            result = {
                'status': 'accepted',
                'event_id': event_id,
                'immediate_action': None
            }

            if event_type == 'SESSION_COMPLETED':
                self._handle_session_completed(data)
            elif event_type in ['TEST_FAILED', 'ACTION_FAILED']:
                self._handle_failure(event_type, data)
            elif event_type == 'USER_FEEDBACK':
                self._handle_user_feedback(data)

            return result

        except Exception as e:
            self.logger.error(f"イベント処理中にエラーが発生: {e}")
            return {'status': 'error', 'message': str(e)}

    def _save_event(self, event_id: str, event_type: str, data: Dict[str, Any], timestamp: str):
        """イベントをJSONファイルとして保存"""
        self.learning_queue_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.learning_queue_dir / f"{event_id}.json"
        event_record = {
            'event_id': event_id,
            'event_type': event_type,
            'timestamp': timestamp,
            'data': data
        }
        with file_path.open('w', encoding='utf-8') as f:
            json.dump(event_record, f, ensure_ascii=False, indent=2)

    def _handle_session_completed(self, context: Dict[str, Any]):
        """対話終了時の学習（明確化があった場合の意図強化や修復ナレッジの抽出）"""
        # 1. 明確化が必要だった場合、最終的な意図と入力をペアにして学習候補とする
        if context.get('clarification_needed') or context.get('pipeline_history', []).count('clarification_manager') > 0:
             self.logger.info(f"Clarification detected in session {context.get('session_id')}. Queued for intent reinforcement.")

        # 2. 回復タスクが成功して終了した場合、即座にナレッジを抽出する
        task = context.get('task')
        if task and task.get('name') == 'RECOVERY_FROM_TEST_FAILURE' and task.get('state') == 'COMPLETED':
            if self.repair_kb:
                self.logger.info(f"Successful recovery detected in session {context.get('session_id')}. Extracting knowledge immediately.")
                # RepairKnowledgeBase に直接コンテキストを渡して学習
                session_data = {
                    'event_type': 'SESSION_COMPLETED',
                    'timestamp': datetime.now().isoformat(),
                    'data': context
                }
                self.repair_kb._extract_knowledge_from_session(session_data)
                self.repair_kb.save_knowledge()

    def _handle_failure(self, event_type: str, data: Dict[str, Any]):
        """失敗時の学習（エラーパターンの登録など）"""
        failure_record = self._build_failure_record(
            event_type,
            data,
            datetime.now().isoformat(),
        )
        self._record_failure_event(failure_record)
        self._record_repair_failure_observation(failure_record)

    def _build_failure_record(
        self,
        event_type: str,
        data: Dict[str, Any],
        timestamp: str,
    ) -> Dict[str, Any]:
        analysis = self._extract_primary_analysis(data)
        exception_info = data.get("exception") if isinstance(data.get("exception"), dict) else {}

        error_type = self._first_non_empty_string(
            data.get("error_type"),
            data.get("original_error_type"),
            analysis.get("error_type"),
            exception_info.get("type"),
        )
        root_cause = self._first_non_empty_string(
            data.get("root_cause"),
            analysis.get("root_cause"),
        )
        message = self._first_non_empty_string(
            data.get("error_message"),
            data.get("message"),
            data.get("original_error"),
            exception_info.get("message"),
            analysis.get("error_message"),
        )
        target = self._extract_failure_target(data, analysis)

        return {
            "type": "failure",
            "event_type": event_type,
            "timestamp": timestamp,
            "failure_signature": self._failure_signature(
                event_type=event_type,
                error_type=error_type,
                root_cause=root_cause,
                target=target,
                message=message,
            ),
            "error_type": error_type,
            "root_cause": root_cause,
            "message": message,
            "target": target,
            "analysis": analysis,
            "status": "pending_analysis",
        }

    def _extract_primary_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        direct = data.get("analysis")
        if isinstance(direct, dict):
            return dict(direct)

        for parent_key in ("analysis_result", "action_result"):
            parent = data.get(parent_key)
            if not isinstance(parent, dict):
                continue
            analysis_result = parent
            if parent_key == "action_result":
                analysis_result = parent.get("analysis_result")
                if not isinstance(analysis_result, dict):
                    continue
            analyses = analysis_result.get("analyses")
            if isinstance(analyses, list):
                for item in analyses:
                    if isinstance(item, dict):
                        return dict(item)
        return {}

    def _extract_failure_target(
        self,
        data: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        target = data.get("target")
        if isinstance(target, dict):
            return dict(target)

        target_code = data.get("target_code")
        if isinstance(target_code, dict):
            return {
                "file": target_code.get("file"),
                "method": target_code.get("method"),
                "line": target_code.get("line_number") or data.get("line_number"),
            }

        test_context = analysis.get("test_context")
        if isinstance(test_context, dict):
            return {
                "file": test_context.get("test_file"),
                "method": test_context.get("test_method"),
                "line": analysis.get("line_number") or data.get("line_number"),
            }

        return {
            "file": data.get("file") or data.get("test_file"),
            "method": data.get("method") or data.get("test_method") or data.get("test_name"),
            "line": data.get("line") or data.get("line_number"),
        }

    @staticmethod
    def _first_non_empty_string(*values: Any) -> Optional[str]:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _failure_signature(
        event_type: str,
        error_type: Optional[str],
        root_cause: Optional[str],
        target: Dict[str, Any],
        message: Optional[str],
    ) -> str:
        payload = {
            "event_type": event_type,
            "error_type": error_type,
            "root_cause": root_cause,
            "target": {
                "file": target.get("file"),
                "method": target.get("method"),
                "line": target.get("line"),
            },
            "message": message,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
        return f"failure.{digest}"

    def _record_failure_event(self, failure_record: Dict[str, Any]):
        path = self.workspace_root / "logs" / "failure_events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(failure_record, ensure_ascii=False) + "\n")

    def _record_repair_failure_observation(self, failure_record: Dict[str, Any]):
        if not self.repair_kb:
            return
        error_type = failure_record.get("error_type")
        if not error_type:
            return

        try:
            self.repair_kb.add_repair_experience({
                "root_cause": failure_record.get("root_cause") or "unknown",
                "error_type": error_type,
                "fix_type": None,
                "success": False,
            })
        except Exception as exc:
            self.logger.warning(
                "Failed to record repair failure observation: %s",
                exc,
            )

    def _handle_user_feedback(self, data: Dict[str, Any]):
        """ユーザーフィードバックの学習"""
        finding_id = data.get('finding_id')
        feedback = data.get('feedback', '')
        terminology_mapping = data.get("terminology_mapping")
        if isinstance(terminology_mapping, dict):
            source_term = terminology_mapping.get("source")
            target_term = terminology_mapping.get("target")
            if (
                isinstance(source_term, str)
                and source_term.strip()
                and isinstance(target_term, str)
                and target_term.strip()
            ):
                self._record_learned_mapping(
                    source_term.strip(),
                    target_term.strip(),
                )
                return
        if finding_id and feedback:
            self.logger.info(f"User feedback received for {finding_id}: {feedback}")
            self._record_behavioral_feedback(finding_id, feedback)

    def _record_learned_mapping(self, jp: str, en: str):
        """学習したマッピングを保存"""
        path = self.workspace_root / 'logs' / 'learned_mappings.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"type": "terminology", "jp": jp, "en": en, "timestamp": datetime.now().isoformat()}
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _record_behavioral_feedback(self, session_id: str, feedback: str):
        """振る舞いに関するフィードバックを保存"""
        path = self.workspace_root / 'logs' / 'behavioral_feedback.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "type": "behavior",
            "session_id": session_id,
            "feedback": feedback,
            "timestamp": datetime.now().isoformat(),
            "status": "pending_analysis"
        }
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
