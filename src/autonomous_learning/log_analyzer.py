# -*- coding: utf-8 -*-
# src/autonomous_learning/log_analyzer.py

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

@dataclass
class LearningPattern:
    """学習されたパターンを表すデータクラス"""
    pattern_type: str  # 'success', 'error', 'improvement'
    pattern: str
    frequency: int
    confidence: float
    context: Dict[str, Any]
    examples: List[Dict[str, Any]]

class LogAnalyzer:
    """ログ分析を担当するクラス"""
    
    def __init__(self, log_directory: str):
        self.log_directory = Path(log_directory)
        self.logger = logging.getLogger(__name__)
        self.collection_diagnostics: List[Dict[str, Any]] = []
    
    def collect_logs(self, days_back: int = 7) -> List[Dict[str, Any]]:
        """指定期間のログを収集し、トランザクションごとに集約"""
        if not isinstance(days_back, int) or isinstance(days_back, bool):
            raise TypeError("days_back must be an integer")
        if days_back < 0:
            raise ValueError("days_back must be non-negative")
        self.collection_diagnostics = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        raw_events = []
        if not self.log_directory.exists():
            return []

        for file_path in self.log_directory.glob('*.json'):
            if file_path.name == "learning_queue.json":
                continue
            try:
                file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_date < cutoff_date:
                    continue
                with file_path.open('r', encoding='utf-8') as log_file:
                    for line_number, line in enumerate(log_file, start=1):
                        record = line.strip()
                        if not record:
                            continue
                        if record.endswith(','):
                            record = record[:-1].rstrip()
                        try:
                            event = json.loads(record)
                        except json.JSONDecodeError as exc:
                            self.collection_diagnostics.append({
                                "type": "INVALID_LOG_RECORD",
                                "file": str(file_path),
                                "line": line_number,
                                "error_type": type(exc).__name__,
                            })
                            continue
                        if not isinstance(event, dict):
                            self.collection_diagnostics.append({
                                "type": "INVALID_LOG_EVENT",
                                "file": str(file_path),
                                "line": line_number,
                                "error_type": "event_must_be_object",
                            })
                            continue
                        raw_events.append(event)
            except OSError as exc:
                self.collection_diagnostics.append({
                    "type": "LOG_FILE_READ_ERROR",
                    "file": str(file_path),
                    "error_type": type(exc).__name__,
                })

        raw_events.sort(
            key=lambda event: (
                event.get("timestamp")
                if isinstance(event.get("timestamp"), str)
                else ""
            )
        )

        transactions = defaultdict(lambda: {
            'original_text': '',
            'session_id': '',
            'analysis': {},
            'action_result': {},
            'errors': [],
            'clarification_needed': False,
            'suggested_intent': None,
            'learning_evidence': [],
            'timestamp': ''
        })

        current_tx_id = {} 

        for event in raw_events:
            data = event.get('data', {})
            if not isinstance(data, dict):
                self.collection_diagnostics.append({
                    "type": "INVALID_LOG_EVENT",
                    "error_type": "data_must_be_object",
                    "event_type": event.get("event_type"),
                })
                continue
            session_id = data.get('session_id', 'unknown')
            event_type = event.get('event_type')
            
            if event_type == 'pipeline_start':
                tx_key = f"{session_id}_{event.get('timestamp')}"
                current_tx_id[session_id] = tx_key
                transactions[tx_key]['original_text'] = data.get('original_text', '')
                transactions[tx_key]['session_id'] = session_id
                transactions[tx_key]['timestamp'] = event.get('timestamp')
            
            tx_key = current_tx_id.get(session_id)
            if not tx_key: continue

            learning_evidence = data.get("learning_evidence")
            if isinstance(learning_evidence, dict):
                transactions[tx_key]["learning_evidence"].append(
                    learning_evidence
                )
            elif isinstance(learning_evidence, list):
                transactions[tx_key]["learning_evidence"].extend(
                    evidence for evidence in learning_evidence
                    if isinstance(evidence, dict)
                )

            if event_type == 'pipeline_stage_completion':
                summary = data.get('context_summary', {})
                if summary.get('intent'):
                    if 'intent' not in transactions[tx_key]['analysis']:
                        transactions[tx_key]['analysis']['intent'] = summary.get('intent')
                    transactions[tx_key]['analysis']['intent_confidence'] = summary.get('intent_confidence', 0.0)
                if summary.get('entities'):
                    if 'entities' not in transactions[tx_key]['analysis']:
                        transactions[tx_key]['analysis']['entities'] = {}
                    transactions[tx_key]['analysis']['entities'].update(summary.get('entities'))
                if summary.get('action_result_status'):
                    status = summary.get('action_result_status')
                    transactions[tx_key]['action_result']['status'] = status
                    if status == 'error' and summary.get('errors'):
                        msg = summary.get('errors')[0].get('message', 'Unknown error')
                        transactions[tx_key]['errors'].append(msg)
            
            elif event_type == 'clarification_needed':
                transactions[tx_key]['clarification_needed'] = True
                if data.get('reason') == 'low_intent_confidence':
                    transactions[tx_key]['suggested_intent'] = data.get('intent')
            
            elif event_type == 'action_execution_error' or event_type == 'test_failed':
                transactions[tx_key]['action_result']['status'] = 'error'
                msg = data.get('message') or data.get('error_message') or (data.get('errors', [{}])[0].get('message') if data.get('errors') else 'Unknown error')
                transactions[tx_key]['action_result']['message'] = msg
                transactions[tx_key]['errors'].append(msg)

        return [tx for tx in transactions.values() if tx['original_text']]
    
    def extract_patterns(self, logs: List[Dict[str, Any]]) -> Dict[str, List[LearningPattern]]:
        """ログからパターンを抽出"""
        self.logger.info(f"Processing {len(logs)} aggregated transactions")
        patterns = {
            'success': [],
            'error': [],
            'improvement': [],
            'clarification_fix': []
        }
        
        patterns['success'] = self._extract_success_patterns(logs)
        patterns['error'] = self._extract_error_patterns(logs)
        patterns['improvement'] = self._identify_improvement_opportunities(logs)
        patterns['clarification_fix'] = self._extract_clarification_fix_patterns(logs)
        
        return patterns

    def _extract_clarification_fix_patterns(self, logs: List[Dict[str, Any]]) -> List[LearningPattern]:
        """明示承認された意図訂正だけを学習候補として抽出する。"""
        patterns = []
        for log in logs:
            for evidence in self._approved_evidence(log, "intent_correction"):
                source_text = evidence.get("source_text")
                corrected_intent = evidence.get("corrected_intent")
                if not isinstance(source_text, str) or not source_text:
                    continue
                if not isinstance(corrected_intent, str) or not corrected_intent:
                    continue
                patterns.append(LearningPattern(
                    pattern_type="improvement",
                    pattern=source_text,
                    frequency=1,
                    confidence=1.0,
                    context={
                        "intent": corrected_intent,
                        "issue": "clarification_learned",
                        "evidence_type": "intent_correction",
                        "proposed_rule": evidence.get("proposed_rule"),
                    },
                    examples=[log],
                ))
        return patterns
    
    def _extract_success_patterns(self, logs: List[Dict[str, Any]]) -> List[LearningPattern]:
        """明示承認された意図例だけを抽出する。"""
        success_logs = [log for log in logs if self._is_successful_interaction(log)]
        intent_patterns = defaultdict(list)
        for log in success_logs:
            for evidence in self._approved_evidence(log, "intent_example"):
                intent = evidence.get("intent")
                pattern = evidence.get("pattern")
                if not isinstance(intent, str) or not intent:
                    continue
                if not isinstance(pattern, str) or not pattern:
                    continue
                intent_patterns[(intent, pattern)].append({
                    "log": log,
                    "evidence": evidence,
                })
        
        patterns = []
        for (intent, pattern), entries in intent_patterns.items():
            patterns.append(LearningPattern(
                pattern_type="success",
                pattern=pattern,
                frequency=len(entries),
                confidence=1.0,
                context={
                    "intent": intent,
                    "type": "intent_detection",
                    "evidence_type": "intent_example",
                    "proposed_rule": entries[0]["evidence"].get(
                        "proposed_rule"
                    ),
                },
                examples=[
                    entry["log"] for entry in entries[:5]
                ],
            ))
        return patterns
    
    def _extract_error_patterns(self, logs: List[Dict[str, Any]]) -> List[LearningPattern]:
        """明示されたエラーコードだけを学習候補として抽出する。"""
        error_logs = [log for log in logs if self._has_error(log)]
        error_types = defaultdict(list)
        for log in error_logs:
            for evidence in self._approved_evidence(log, "error"):
                error_code = evidence.get("error_code")
                if isinstance(error_code, str) and error_code:
                    error_types[error_code].append(log)
        
        patterns = []
        for error_type, examples in error_types.items():
            patterns.append(LearningPattern(
                pattern_type="error",
                pattern=error_type,
                frequency=len(examples),
                confidence=1.0,
                context={
                    "error_type": error_type,
                    "evidence_type": "error",
                    "proposed_rule": next(
                        (
                            evidence.get("proposed_rule")
                            for evidence in examples[0].get(
                                "learning_evidence",
                                [],
                            )
                            if isinstance(evidence, dict)
                            and evidence.get("type") == "error"
                            and evidence.get("error_code") == error_type
                        ),
                        None,
                    ),
                },
                examples=examples[:5],
            ))
        return patterns
    
    def _identify_improvement_opportunities(self, logs: List[Dict[str, Any]]) -> List[LearningPattern]:
        """明示承認された改善根拠だけを抽出する。"""
        patterns = []
        for log in logs:
            for evidence in self._approved_evidence(log, "improvement"):
                issue = evidence.get("issue")
                pattern = evidence.get("pattern")
                if not isinstance(issue, str) or not issue:
                    continue
                if not isinstance(pattern, str) or not pattern:
                    continue
                patterns.append(LearningPattern(
                    pattern_type="improvement",
                    pattern=pattern,
                    frequency=1,
                    confidence=1.0,
                    context={
                        "issue": issue,
                        "evidence_type": "improvement",
                        "proposed_rule": evidence.get("proposed_rule"),
                    },
                    examples=[log],
                ))
        return patterns

    @staticmethod
    def _approved_evidence(
        log: Dict[str, Any],
        evidence_type: str,
    ) -> List[Dict[str, Any]]:
        evidence_items = log.get("learning_evidence", [])
        if isinstance(evidence_items, dict):
            evidence_items = [evidence_items]
        if not isinstance(evidence_items, list):
            return []
        return [
            evidence for evidence in evidence_items
            if isinstance(evidence, dict)
            and evidence.get("type") == evidence_type
            and evidence.get("approved") is True
        ]
    
    def _is_successful_interaction(self, log: Dict[str, Any]) -> bool:
        """成功した対話かどうかを判定"""
        if 'action_result' in log:
            return log['action_result'].get('status') == 'success'
        return not self._has_error(log) and not log.get('clarification_needed', False)
    
    def _has_error(self, log: Dict[str, Any]) -> bool:
        """エラーがあるかどうかを判定"""
        if 'errors' in log and log['errors']:
            return True
        if 'action_result' in log:
            return log['action_result'].get('status') == 'error'
        return False
    
