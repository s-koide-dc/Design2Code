# -*- coding: utf-8 -*-
# src/autonomous_learning/log_analyzer.py

import json
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter
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
    
    def collect_logs(self, days_back: int = 7) -> List[Dict[str, Any]]:
        """指定期間のログを収集し、トランザクションごとに集約"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        raw_events = []
        
        try:
            if not self.log_directory.exists():
                return []

            for file_path in self.log_directory.glob('*.json'):
                if 'learning_queue' in str(file_path):
                    continue

                file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if file_date >= cutoff_date:
                    with file_path.open('r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if not line: continue
                            if line.endswith(','): line = line[:-1]
                            try:
                                event = json.loads(line)
                                raw_events.append(event)
                            except: continue
        except Exception as e:
            self.logger.error(f"ログ収集中にエラーが発生: {e}")
            return []

        raw_events.sort(key=lambda x: x.get('timestamp', ''))

        transactions = defaultdict(lambda: {
            'original_text': '',
            'session_id': '',
            'analysis': {},
            'action_result': {},
            'errors': [],
            'clarification_needed': False,
            'suggested_intent': None,
            'timestamp': ''
        })

        current_tx_id = {} 

        for event in raw_events:
            data = event.get('data', {})
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
        """明確化後に成功した事例から、新しい意図パターンを抽出"""
        patterns = []
        session_logs = defaultdict(list)
        for log in logs:
            if 'session_id' not in log:
                continue
            session_logs[log['session_id']].append(log)
        
        for session_id, turns in session_logs.items():
            turns.sort(key=lambda x: x['timestamp'])
            
            for i in range(len(turns) - 1):
                current_turn = turns[i]
                next_turn = turns[i+1]
                
                if current_turn.get('clarification_needed') and current_turn.get('suggested_intent'):
                    suggested = current_turn['suggested_intent']
                    original_text = current_turn['original_text']
                    
                    if next_turn['analysis'].get('intent') == 'AGREE' or next_turn['analysis'].get('intent') == suggested:
                        patterns.append(LearningPattern(
                            pattern_type='improvement',
                            pattern=original_text,
                            frequency=1,
                            confidence=0.8,
                            context={'intent': suggested, 'issue': 'clarification_learned'},
                            examples=[current_turn]
                        ))
        return patterns
    
    def _extract_success_patterns(self, logs: List[Dict[str, Any]]) -> List[LearningPattern]:
        """成功パターンを抽出"""
        success_logs = [log for log in logs if self._is_successful_interaction(log)]
        intent_patterns = defaultdict(list)
        for log in success_logs:
            if 'analysis' in log and 'intent' in log['analysis']:
                intent = log['analysis']['intent']
                original_text = log.get('original_text', '')
                confidence = log['analysis'].get('intent_confidence', 0.0)
                
                if confidence > 0.7:
                    intent_patterns[intent].append({
                        'text': original_text,
                        'confidence': confidence,
                        'context': log
                    })
        
        patterns = []
        for intent, examples in intent_patterns.items():
            if len(examples) >= 2:
                common_pattern = self._find_common_pattern([ex['text'] for ex in examples])
                avg_confidence = sum(ex['confidence'] for ex in examples) / len(examples)
                if common_pattern:
                    patterns.append(LearningPattern(
                        pattern_type='success',
                        pattern=common_pattern,
                        frequency=len(examples),
                        confidence=avg_confidence,
                        context={'intent': intent, 'type': 'intent_detection'},
                        examples=examples[:5]
                    ))
                elif len(examples) >= 3:
                    patterns.append(LearningPattern(
                        pattern_type='success',
                        pattern=f"{intent}_pattern",
                        frequency=len(examples),
                        confidence=avg_confidence,
                        context={'intent': intent, 'type': 'intent_detection'},
                        examples=examples[:5]
                    ))
        return patterns
    
    def _extract_error_patterns(self, logs: List[Dict[str, Any]]) -> List[LearningPattern]:
        """エラーパターンを抽出"""
        error_logs = [log for log in logs if self._has_error(log)]
        error_types = defaultdict(list)
        for log in error_logs:
            error_info = self._extract_error_info(log)
            if error_info:
                error_types[error_info['type']].append({
                    'error': error_info,
                    'context': log
                })
        
        patterns = []
        for error_type, examples in error_types.items():
            if len(examples) >= 2:
                patterns.append(LearningPattern(
                    pattern_type='error',
                    pattern=error_type,
                    frequency=len(examples),
                    confidence=1.0,
                    context={'error_type': error_type},
                    examples=examples[:5]
                ))
        return patterns
    
    def _identify_improvement_opportunities(self, logs: List[Dict[str, Any]]) -> List[LearningPattern]:
        """改善機会を特定"""
        patterns = []
        low_confidence_logs = [
            log for log in logs 
            if 'analysis' in log and 
            log['analysis'].get('intent_confidence', 1.0) < 0.6
        ]
        
        if len(low_confidence_logs) >= 3:
            texts = [log.get('original_text', '') for log in low_confidence_logs]
            common_pattern = self._find_common_pattern(texts)
            pattern_name = common_pattern if common_pattern else 'low_confidence_general'
            patterns.append(LearningPattern(
                pattern_type='improvement',
                pattern=pattern_name,
                frequency=len(low_confidence_logs),
                confidence=0.7,
                context={'issue': 'low_intent_confidence'},
                examples=low_confidence_logs[:5]
            ))
        
        clarification_logs = [
            log for log in logs 
            if log.get('clarification_needed', False)
        ]
        
        if len(clarification_logs) >= 3:
            patterns.append(LearningPattern(
                pattern_type='improvement',
                pattern='frequent_clarification',
                frequency=len(clarification_logs),
                confidence=0.8,
                context={'issue': 'frequent_clarification'},
                examples=clarification_logs[:5]
            ))
        return patterns
    
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
    
    def _extract_error_info(self, log: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """エラー情報を抽出"""
        if 'errors' in log and log['errors']:
            return {
                'type': 'pipeline_error',
                'message': str(log['errors'][0]) if log['errors'] else 'Unknown error'
            }
        if 'action_result' in log and log['action_result'].get('status') == 'error':
            return {
                'type': 'action_error',
                'message': log['action_result'].get('message', 'Unknown action error')
            }
        return None
    
    def _find_common_pattern(self, texts: List[str]) -> Optional[str]:
        """テキストリストから共通パターンを見つける"""
        if len(texts) < 2: return None
        if not texts: return None
        
        first_text = texts[0]
        potential_patterns = []
        for length in range(3, min(20, len(first_text) + 1)):
            for start in range(len(first_text) - length + 1):
                sub = first_text[start:start+length]
                if all(sub in t for t in texts[1:]):
                    potential_patterns.append(sub)
        
        if potential_patterns:
            return max(potential_patterns, key=len)

        words_counter = Counter()
        for text in texts:
            words = re.findall(r'\w+', text.lower())
            words_counter.update(words)
        
        common_words = [
            word for word, count in words_counter.items() 
            if count >= len(texts) * 0.5
        ]
        if len(common_words) >= 2:
            return '|'.join(sorted(common_words))
        return None
