# -*- coding: utf-8 -*-
# src/autonomous_learning/event_processor.py

import json
import re
import logging
from datetime import datetime
from typing import Dict, Any
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
        pass

    def _handle_user_feedback(self, data: Dict[str, Any]):
        """ユーザーフィードバックの学習"""
        finding_id = data.get('finding_id')
        feedback = data.get('feedback', '')
        if finding_id and feedback:
            self.logger.info(f"User feedback received for {finding_id}: {feedback}")
            
            # 1. 用語マッピングの抽出試行
            mapping_match = re.search(r'「(.+?)」\s*は\s*(.+?)\s*の[こと|意味]', feedback)
            if mapping_match:
                jp_term = mapping_match.group(1)
                en_term = mapping_match.group(2)
                self.logger.info(f"Learned mapping: {jp_term} -> {en_term}")
                self._record_learned_mapping(jp_term, en_term)
                return

            # 2. 振る舞い/一般フィードバックとして保存
            self._record_behavioral_feedback(finding_id, feedback)

    def _record_learned_mapping(self, jp: str, en: str):
        """学習したマッピングを保存"""
        path = self.workspace_root / 'logs' / 'learned_mappings.jsonl'
        record = {"type": "terminology", "jp": jp, "en": en, "timestamp": datetime.now().isoformat()}
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _record_behavioral_feedback(self, session_id: str, feedback: str):
        """振る舞いに関するフィードバックを保存"""
        path = self.workspace_root / 'logs' / 'behavioral_feedback.jsonl'
        record = {
            "type": "behavior",
            "session_id": session_id,
            "feedback": feedback,
            "timestamp": datetime.now().isoformat(),
            "status": "pending_analysis"
        }
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
