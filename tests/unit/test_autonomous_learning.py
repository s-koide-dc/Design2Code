# -*- coding: utf-8 -*-
# tests/test_autonomous_learning.py

"""
自律学習機能のテスト
"""

import unittest
import os
import tempfile
import shutil
import json
import logging
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.autonomous_learning.autonomous_learning import (
    AutonomousLearning, LogAnalyzer, PatternLearner, SafetyEvaluator, EventProcessor,
    LearningPattern, RuleSuggestion
)

def create_sample_config(workspace_root: str):
    """サンプル設定ファイルを作成"""
    config_dir = os.path.join(workspace_root, 'config')
    os.makedirs(config_dir, exist_ok=True)
    
    sample_config = {
        'learning': {
            'min_pattern_frequency': 3,
            'confidence_threshold': 0.7,
            'days_back': 7
        },
        'safety': {
            'dangerous_keywords': ['delete', 'remove', 'destroy', 'format'],
            'max_risk_level': 'medium',
            'require_approval': True
        }
    }
    
    config_path = os.path.join(config_dir, 'autonomous_learning.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(sample_config, f, ensure_ascii=False, indent=2)
    
    return config_path


class TestLogAnalyzer(unittest.TestCase):
    """LogAnalyzerのテストクラス"""
    
    def setUp(self):
        """テスト前の準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = os.path.join(self.temp_dir, 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.analyzer = LogAnalyzer(self.log_dir)
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_collect_logs_success(self):
        """ログ収集成功テスト"""
        # テスト用ログファイルを作成（イベント形式）
        timestamp = datetime.now().isoformat()
        log_data = [
            {
                'event_type': 'pipeline_start',
                'timestamp': timestamp,
                'data': {
                    'session_id': 'test_session',
                    'original_text': 'ファイルを作成して'
                }
            },
            {
                'event_type': 'pipeline_stage_completion',
                'timestamp': timestamp,
                'data': {
                    'session_id': 'test_session',
                    'context_summary': {
                        'intent': 'FILE_CREATE',
                        'intent_confidence': 0.9,
                        'action_result_status': 'success'
                    },
                    'learning_evidence': {
                        'type': 'intent_example',
                        'approved': True,
                        'intent': 'FILE_CREATE',
                        'pattern': 'create_file_request',
                    },
                }
            }
        ]
        
        log_file = os.path.join(self.log_dir, 'test_log.json')
        with open(log_file, 'w', encoding='utf-8') as f:
            for entry in log_data:
                json.dump(entry, f, ensure_ascii=False)
                f.write('\n')
        
        # ログ収集実行
        logs = self.analyzer.collect_logs(days_back=1)
        
        # 結果検証
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]['session_id'], 'test_session')
        self.assertEqual(logs[0]['analysis']['intent'], 'FILE_CREATE')
        self.assertEqual(
            "create_file_request",
            logs[0]["learning_evidence"][0]["pattern"],
        )
    
    def test_collect_logs_empty_directory(self):
        """空ディレクトリでのログ収集テスト"""
        logs = self.analyzer.collect_logs(days_back=1)
        self.assertEqual(len(logs), 0)

    def test_collect_logs_reports_invalid_record_and_continues(self):
        timestamp = datetime.now().isoformat()
        log_file = os.path.join(self.log_dir, "mixed.json")
        valid_events = [{
            "event_type": "pipeline_start",
            "timestamp": timestamp,
            "data": {
                "session_id": "valid_session",
                "original_text": "valid input",
            },
        }]
        with open(log_file, "w", encoding="utf-8") as output:
            output.write("{invalid\n")
            output.write(json.dumps(valid_events[0]) + ",\n")

        logs = self.analyzer.collect_logs(days_back=1)

        self.assertEqual(1, len(logs))
        self.assertEqual("valid_session", logs[0]["session_id"])
        self.assertEqual([{
            "type": "INVALID_LOG_RECORD",
            "file": log_file,
            "line": 1,
            "error_type": "JSONDecodeError",
        }], self.analyzer.collection_diagnostics)

    def test_collect_logs_rejects_invalid_days_back(self):
        with self.assertRaises(ValueError):
            self.analyzer.collect_logs(days_back=-1)
        with self.assertRaises(TypeError):
            self.analyzer.collect_logs(days_back=1.5)
    
    def test_extract_success_patterns(self):
        """成功パターン抽出テスト"""
        # 成功ログのサンプル
        logs = [
            {
                'original_text': 'ファイルを作成して',
                'analysis': {
                    'intent': 'FILE_CREATE',
                    'intent_confidence': 0.9
                },
                'learning_evidence': [{
                    'type': 'intent_example',
                    'approved': True,
                    'intent': 'FILE_CREATE',
                    'pattern': 'create_file_request',
                }],
                'action_result': {'status': 'success'}
            },
            {
                'original_text': 'ファイル作成をお願いします',
                'analysis': {
                    'intent': 'FILE_CREATE',
                    'intent_confidence': 0.85
                },
                'learning_evidence': [{
                    'type': 'intent_example',
                    'approved': True,
                    'intent': 'FILE_CREATE',
                    'pattern': 'create_file_request',
                }],
                'action_result': {'status': 'success'}
            },
            {
                'original_text': 'ファイルを新規作成',
                'analysis': {
                    'intent': 'FILE_CREATE',
                    'intent_confidence': 0.88
                },
                'learning_evidence': [{
                    'type': 'intent_example',
                    'approved': True,
                    'intent': 'FILE_CREATE',
                    'pattern': 'create_file_request',
                }],
                'action_result': {'status': 'success'}
            }
        ]
        
        patterns = self.analyzer.extract_patterns(logs)
        
        # 成功パターンが抽出されることを確認
        self.assertGreater(len(patterns['success']), 0)
        
        # FILE_CREATEパターンが含まれることを確認
        file_create_patterns = [
            p for p in patterns['success'] 
            if p.context.get('intent') == 'FILE_CREATE'
        ]
        self.assertGreater(len(file_create_patterns), 0)

    def test_success_pattern_requires_approved_structured_evidence(self):
        logs = [{
            "original_text": "ファイルを作成して",
            "analysis": {
                "intent": "FILE_CREATE",
                "intent_confidence": 0.99,
            },
            "action_result": {"status": "success"},
        }]

        patterns = self.analyzer.extract_patterns(logs)

        self.assertEqual([], patterns["success"])
    
    def test_extract_error_patterns(self):
        """エラーパターン抽出テスト"""
        logs = [
            {
                'original_text': 'ファイルを削除して',
                'analysis': {'intent': 'FILE_DELETE'},
                'action_result': {
                    'status': 'error',
                    'message': 'ファイルが見つかりません'
                },
                'learning_evidence': [{
                    'type': 'error',
                    'approved': True,
                    'error_code': 'file_not_found',
                }],
            },
            {
                'original_text': '別のファイルを削除',
                'analysis': {'intent': 'FILE_DELETE'},
                'action_result': {
                    'status': 'error',
                    'message': 'ファイルが見つかりません'
                },
                'learning_evidence': [{
                    'type': 'error',
                    'approved': True,
                    'error_code': 'file_not_found',
                }],
            }
        ]
        
        patterns = self.analyzer.extract_patterns(logs)
        
        # エラーパターンが抽出されることを確認
        self.assertGreater(len(patterns['error']), 0)
    
    def test_identify_improvement_opportunities(self):
        """改善機会特定テスト"""
        logs = [
            {
                'original_text': '何かして',
                'analysis': {
                    'intent': 'GENERAL',
                    'intent_confidence': 0.3
                },
                'clarification_needed': True,
                'learning_evidence': [{
                    'type': 'improvement',
                    'approved': True,
                    'issue': 'low_intent_confidence',
                    'pattern': 'missing_intent_evidence',
                }, {
                    'type': 'improvement',
                    'approved': True,
                    'issue': 'frequent_clarification',
                    'pattern': 'clarification_requested',
                }],
            },
            {
                'original_text': 'よくわからない',
                'analysis': {
                    'intent': 'GENERAL',
                    'intent_confidence': 0.2
                },
                'clarification_needed': True
            },
            {
                'original_text': 'あれをして',
                'analysis': {
                    'intent': 'GENERAL',
                    'intent_confidence': 0.4
                },
                'clarification_needed': True
            },
            {
                'original_text': 'それをお願い',
                'analysis': {
                    'intent': 'GENERAL',
                    'intent_confidence': 0.35
                },
                'clarification_needed': True
            },
            {
                'original_text': 'どうにかして',
                'analysis': {
                    'intent': 'GENERAL',
                    'intent_confidence': 0.25
                },
                'clarification_needed': True
            }
        ]
        
        patterns = self.analyzer.extract_patterns(logs)
        
        # 改善機会が特定されることを確認
        self.assertGreater(len(patterns['improvement']), 0)
        
        # 低信頼度と頻繁な明確化の問題が特定されることを確認
        issues = [p.context.get('issue') for p in patterns['improvement']]
        self.assertIn('low_intent_confidence', issues)
        self.assertIn('frequent_clarification', issues)


class TestPatternLearner(unittest.TestCase):
    """PatternLearnerのテストクラス"""
    
    def setUp(self):
        """テスト前の準備"""
        self.config = {}
        self.learner = PatternLearner(self.config)
    
    def test_learn_from_success_patterns(self):
        """成功パターンからの学習テスト"""
        patterns = {
            'success': [
                LearningPattern(
                    pattern_type='success',
                    pattern='ファイル|作成',
                    frequency=5,
                    confidence=0.85,
                    context={
                        'intent': 'FILE_CREATE',
                        'type': 'intent_detection',
                        'evidence_type': 'intent_example',
                        'proposed_rule': {
                            'rule_type': 'intent_rule',
                            'rule_definition': {
                                'type': 'intent_detection',
                                'intent': 'FILE_CREATE',
                                'pattern': 'create_file_request',
                            },
                            'impact_scope': 'intent_detection',
                            'risk_level': 'low',
                            'explanation': 'Approved intent example.',
                            'safety_evidence': {
                                'reviewed': True,
                                'decision': 'approve',
                                'controls': [{
                                    'control_id': 'intent_scope_review',
                                    'passed': True,
                                }],
                            },
                        },
                    },
                    examples=[]
                )
            ],
            'error': [],
            'improvement': []
        }
        
        suggestions = self.learner.learn_from_patterns(patterns)
        
        # 意図検出ルールが提案されることを確認
        intent_suggestions = [s for s in suggestions if s.rule_type == 'intent_rule']
        self.assertGreater(len(intent_suggestions), 0)
        
        # 提案内容の確認
        suggestion = intent_suggestions[0]
        self.assertEqual(suggestion.rule_definition['intent'], 'FILE_CREATE')
        self.assertEqual(suggestion.impact_scope, 'intent_detection')
        self.assertEqual(suggestion.risk_level, 'low')
    
    def test_learn_from_error_patterns(self):
        """エラーパターンからの学習テスト"""
        patterns = {
            'success': [],
            'error': [
                LearningPattern(
                    pattern_type='error',
                    pattern='file_not_found',
                    frequency=3,
                    confidence=1.0,
                    context={
                        'error_type': 'file_not_found',
                        'evidence_type': 'error',
                        'proposed_rule': {
                            'rule_type': 'retry_rule',
                            'rule_definition': {
                                'type': 'retry_strategy',
                                'error_pattern': 'file_not_found',
                                'max_retries': 2,
                            },
                            'impact_scope': 'error_handling',
                            'risk_level': 'medium',
                            'explanation': 'Approved retry policy.',
                            'safety_evidence': {
                                'reviewed': True,
                                'decision': 'approve',
                                'controls': [{
                                    'control_id': 'retry_scope_review',
                                    'passed': True,
                                }],
                            },
                        },
                    },
                    examples=[]
                )
            ],
            'improvement': []
        }
        
        suggestions = self.learner.learn_from_patterns(patterns)
        
        # リトライルールが提案されることを確認
        retry_suggestions = [s for s in suggestions if s.rule_type == 'retry_rule']
        self.assertGreater(len(retry_suggestions), 0)
        
        # 提案内容の確認
        suggestion = retry_suggestions[0]
        self.assertEqual(suggestion.rule_definition['error_pattern'], 'file_not_found')
        self.assertEqual(suggestion.impact_scope, 'error_handling')
        self.assertEqual(suggestion.risk_level, 'medium')
    
    def test_learn_from_improvement_patterns(self):
        """改善パターンからの学習テスト"""
        patterns = {
            'success': [],
            'error': [],
            'improvement': [
                LearningPattern(
                    pattern_type='improvement',
                    pattern='low_confidence_pattern',
                    frequency=8,
                    confidence=0.7,
                    context={
                        'issue': 'low_intent_confidence',
                        'evidence_type': 'improvement',
                        'proposed_rule': {
                            'rule_type': 'clarification_rule',
                            'rule_definition': {
                                'type': 'clarification_trigger',
                                'condition': {
                                    'type': 'missing_intent_evidence',
                                },
                            },
                            'impact_scope': 'user_experience',
                            'risk_level': 'low',
                            'explanation': 'Approved clarification policy.',
                            'safety_evidence': {
                                'reviewed': True,
                                'decision': 'approve',
                                'controls': [{
                                    'control_id': 'clarification_scope_review',
                                    'passed': True,
                                }],
                            },
                        },
                    },
                    examples=[]
                )
            ]
        }
        
        suggestions = self.learner.learn_from_patterns(patterns)
        
        # 明確化ルールが提案されることを確認
        clarification_suggestions = [s for s in suggestions if s.rule_type == 'clarification_rule']
        self.assertGreater(len(clarification_suggestions), 0)
        
        # 提案内容の確認
        suggestion = clarification_suggestions[0]
        self.assertEqual(suggestion.rule_definition['type'], 'clarification_trigger')
        self.assertEqual(suggestion.impact_scope, 'user_experience')
        self.assertEqual(suggestion.risk_level, 'low')

    def test_rejects_pattern_without_structured_rule_proposal(self):
        patterns = {
            'success': [LearningPattern(
                pattern_type='success',
                pattern='unapproved',
                frequency=100,
                confidence=1.0,
                context={
                    'intent': 'FILE_CREATE',
                    'evidence_type': 'intent_example',
                },
                examples=[],
            )],
            'error': [],
            'improvement': [],
        }

        suggestions = self.learner.learn_from_patterns(patterns)

        self.assertEqual([], suggestions)
        self.assertEqual(
            'proposed_rule_missing',
            self.learner.validation_diagnostics[0]['reason'],
        )


class TestSafetyEvaluator(unittest.TestCase):
    """SafetyEvaluatorのテストクラス"""
    
    def setUp(self):
        """テスト前の準備"""
        self.safety_config = {
            'allowed_risk_levels': ['low', 'medium'],
            'require_safety_review': True,
        }
        self.evaluator = SafetyEvaluator(self.safety_config)
    
    def test_evaluate_safe_suggestions(self):
        """安全な提案の評価テスト"""
        suggestions = [
            RuleSuggestion(
                rule_type='intent_rule',
                rule_definition={
                    'type': 'intent_detection',
                    'pattern': 'ファイル|作成',
                    'intent': 'FILE_CREATE'
                },
                confidence=0.8,
                impact_scope='intent_detection',
                risk_level='low',
                explanation='ファイル作成の意図検出を改善',
                supporting_evidence=[],
                safety_evidence={
                    'reviewed': True,
                    'decision': 'approve',
                    'controls': [{
                        'control_id': 'intent_scope_review',
                        'passed': True,
                    }],
                },
            )
        ]
        
        evaluated = self.evaluator.evaluate_suggestions(suggestions)
        
        # 安全な提案は通ることを確認
        self.assertEqual(len(evaluated), 1)
        self.assertEqual('low', evaluated[0].risk_level)
    
    def test_evaluate_dangerous_suggestions(self):
        """危険な提案の評価テスト"""
        suggestions = [
            RuleSuggestion(
                rule_type='intent_rule',
                rule_definition={
                    'type': 'intent_detection',
                    'pattern': 'delete|all|files',
                    'intent': 'FILE_DELETE'
                },
                confidence=0.9,
                impact_scope='system_wide',
                risk_level='high',
                explanation='ファイル削除の意図検出',
                supporting_evidence=[],
                safety_evidence={
                    'reviewed': True,
                    'decision': 'reject',
                    'controls': [{
                        'control_id': 'destructive_action_review',
                        'passed': False,
                    }],
                },
            )
        ]
        
        evaluated = self.evaluator.evaluate_suggestions(suggestions)
        
        # 危険な提案は除外されることを確認
        self.assertEqual(len(evaluated), 0)
        self.assertEqual(
            'risk_level_not_allowed',
            self.evaluator.evaluation_diagnostics[0]['reason'],
        )
    
    def test_rejects_missing_safety_review(self):
        suggestion = RuleSuggestion(
            rule_type='retry_rule',
            rule_definition={'type': 'retry_strategy'},
            confidence=1.0,
            impact_scope='error_handling',
            risk_level='medium',
            explanation='リトライ戦略',
            supporting_evidence=[],
        )

        evaluated = self.evaluator.evaluate_suggestions([suggestion])

        self.assertEqual([], evaluated)
        self.assertEqual(
            'safety_evidence_missing',
            self.evaluator.evaluation_diagnostics[0]['reason'],
        )


class TestEventProcessor(unittest.TestCase):
    """EventProcessorのテストクラス"""

    def setUp(self):
        """テスト前の準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_root = Path(self.temp_dir)
        self.log_dir = self.workspace_root / 'logs' / 'learning_queue'
        self.processor = EventProcessor(self.workspace_root)

    def tearDown(self):
        """テスト後のクリーンアップ"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_process_event_session_completed(self):
        """セッション完了イベントの処理テスト"""
        event_type = 'SESSION_COMPLETED'
        data = {
            'session_id': 'test_session',
            'clarification_needed': True,
            'pipeline_history': ['clarification_manager']
        }
        
        result = self.processor.process_event(event_type, data)
        
        self.assertEqual(result['status'], 'accepted')
        self.assertIsNotNone(result['event_id'])
        
        # キューファイルが作成されたか確認
        files = list(self.log_dir.glob('*.json'))
        self.assertEqual(len(files), 1)
        
        with files[0].open('r', encoding='utf-8') as f:
            saved_event = json.load(f)
            self.assertEqual(saved_event['event_type'], event_type)
            self.assertEqual(saved_event['data']['session_id'], 'test_session')

    def test_process_event_test_failed(self):
        """テスト失敗イベントの処理テスト"""
        event_type = 'TEST_FAILED'
        data = {
            'test_name': 'test_func',
            'error_message': 'Error occurred'
        }
        
        result = self.processor.process_event(event_type, data)
        self.assertEqual(result['status'], 'accepted')

    def test_process_event_test_failed_records_structured_failure(self):
        repair_kb = Mock()
        processor = EventProcessor(self.workspace_root, repair_kb=repair_kb)
        data = {
            "test_file": "tests/test_calc.py",
            "test_method": "test_add",
            "error_type": "assertion_failure",
            "error_message": "Expected 5 but got 4",
            "analysis_result": {
                "analyses": [{
                    "root_cause": "calculation_logic_error",
                    "fix_direction": "adjust_expression",
                }],
            },
        }

        result = processor.process_event("TEST_FAILED", data)

        self.assertEqual("accepted", result["status"])
        failure_path = self.workspace_root / "logs" / "failure_events.jsonl"
        records = [
            json.loads(line)
            for line in failure_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual("failure", record["type"])
        self.assertEqual("TEST_FAILED", record["event_type"])
        self.assertEqual("assertion_failure", record["error_type"])
        self.assertEqual("calculation_logic_error", record["root_cause"])
        self.assertEqual("tests/test_calc.py", record["target"]["file"])
        self.assertEqual("test_add", record["target"]["method"])
        self.assertTrue(record["failure_signature"].startswith("failure."))
        repair_kb.add_repair_experience.assert_called_once_with({
            "root_cause": "calculation_logic_error",
            "error_type": "assertion_failure",
            "fix_type": None,
            "success": False,
        })

    def test_failure_recording_accepts_event_when_repair_kb_fails(self):
        repair_kb = Mock()
        repair_kb.add_repair_experience.side_effect = RuntimeError("store unavailable")
        processor = EventProcessor(self.workspace_root, repair_kb=repair_kb)

        with self.assertLogs("src.autonomous_learning.event_processor", level="WARNING"):
            result = processor.process_event("ACTION_FAILED", {
                "target": {"file": "src/tool.py", "method": "run"},
                "exception": {
                    "type": "RuntimeError",
                    "message": "execution failed",
                },
            })

        self.assertEqual("accepted", result["status"])
        failure_path = self.workspace_root / "logs" / "failure_events.jsonl"
        record = json.loads(failure_path.read_text(encoding="utf-8").strip())
        self.assertEqual("ACTION_FAILED", record["event_type"])
        self.assertEqual("RuntimeError", record["error_type"])
        self.assertEqual("src/tool.py", record["target"]["file"])

    def test_structured_terminology_mapping_is_recorded(self):
        result = self.processor.process_event("USER_FEEDBACK", {
            "finding_id": "finding-1",
            "terminology_mapping": {
                "source": "顧客",
                "target": "Customer",
            },
        })

        self.assertEqual("accepted", result["status"])
        mapping_path = self.workspace_root / "logs" / "learned_mappings.jsonl"
        record = json.loads(mapping_path.read_text(encoding="utf-8").strip())
        self.assertEqual("顧客", record["jp"])
        self.assertEqual("Customer", record["en"])

    def test_free_text_feedback_is_not_inferred_as_mapping(self):
        result = self.processor.process_event("USER_FEEDBACK", {
            "finding_id": "finding-2",
            "feedback": "「顧客」は Customer の意味",
        })

        self.assertEqual("accepted", result["status"])
        self.assertFalse(
            (self.workspace_root / "logs" / "learned_mappings.jsonl").exists()
        )
        self.assertTrue(
            (self.workspace_root / "logs" / "behavioral_feedback.jsonl").exists()
        )


class TestAutonomousLearning(unittest.TestCase):
    """AutonomousLearningのテストクラス"""
    
    def setUp(self):
        """テスト前の準備"""
        # ログ出力を抑制
        logging.getLogger('src.autonomous_learning.autonomous_learning').setLevel(logging.ERROR)
        
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = os.path.join(self.temp_dir, 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        
        # サンプル設定作成
        create_sample_config(self.temp_dir)
        
        self.mock_log_manager = Mock()
        self.learner = AutonomousLearning(self.temp_dir, self.mock_log_manager)
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        self.learner.close(timeout=5)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """初期化テスト"""
        self.assertIsNotNone(self.learner.log_analyzer)
        self.assertIsNotNone(self.learner.pattern_learner)
        self.assertIsNotNone(self.learner.safety_evaluator)
        self.assertIsNotNone(self.learner.event_processor) # Fast Path check
        self.assertIsNotNone(self.learner.config)

    def test_trigger_learning_sync(self):
        """同期モードでの学習トリガーテスト"""
        event_type = 'TEST_FAILED'
        data = {'message': 'test'}
        
        result = self.learner.trigger_learning(event_type, data, async_mode=False)
        self.assertEqual(result['status'], 'accepted')
    
    def test_trigger_learning_async(self):
        """非同期モードでの学習トリガーテスト"""
        event_type = 'SESSION_COMPLETED'
        data = {'session_id': 'async_test'}
        
        result = self.learner.trigger_learning(event_type, data, async_mode=True)
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(result['mode'], 'async')
        self.assertTrue(self.learner.wait_for_pending_events(timeout=5))

    def test_async_learning_failure_is_recorded(self):
        self.learner.event_processor.process_event = Mock(
            side_effect=RuntimeError("failed"),
        )

        result = self.learner.trigger_learning(
            "SESSION_COMPLETED",
            {"session_id": "failure"},
            async_mode=True,
        )

        self.assertEqual("accepted", result["status"])
        self.assertTrue(self.learner.wait_for_pending_events(timeout=5))
        self.assertEqual(
            "ASYNC_LEARNING_ERROR",
            self.learner.learning_diagnostics[-1]["type"],
        )
        self.assertEqual(
            "RuntimeError",
            self.learner.learning_diagnostics[-1]["error_type"],
        )

    def test_knowledge_summary_keeps_valid_feedback_after_invalid_record(self):
        feedback_path = Path(self.log_dir) / "behavioral_feedback.jsonl"
        feedback_path.write_text(
            "{invalid\n"
            + json.dumps({"finding_id": "valid"}) + "\n",
            encoding="utf-8",
        )

        summary = self.learner.generate_knowledge_summary()

        self.assertEqual(
            [{"finding_id": "valid"}],
            summary["recent_feedback"],
        )
        self.assertEqual(
            "INVALID_BEHAVIORAL_FEEDBACK",
            self.learner.learning_diagnostics[-1]["type"],
        )

    def test_mapping_merge_reports_invalid_record_and_merges_valid_entry(self):
        resources_dir = Path(self.temp_dir) / "resources"
        resources_dir.mkdir(exist_ok=True)
        dictionary_path = resources_dir / "domain_dictionary.json"
        dictionary_path.write_text(
            json.dumps({"mappings": {}}),
            encoding="utf-8",
        )
        mappings_path = Path(self.log_dir) / "learned_mappings.jsonl"
        mappings_path.write_text(
            "{invalid\n"
            + json.dumps({"jp": "顧客", "en": "Customer"}) + "\n",
            encoding="utf-8",
        )

        self.learner._merge_learned_mappings_to_dictionary()

        dictionary = json.loads(dictionary_path.read_text(encoding="utf-8"))
        self.assertEqual(["Customer"], dictionary["mappings"]["顧客"])
        self.assertEqual(
            "INVALID_LEARNED_MAPPING",
            self.learner.learning_diagnostics[-1]["type"],
        )
        self.assertTrue(
            mappings_path.with_name(
                "learned_mappings.jsonl.processed"
            ).exists()
        )
    
    def test_run_learning_cycle_insufficient_data(self):
        """データ不足時の学習サイクルテスト"""
        # 少量のログファイルを作成
        log_data = [{'test': 'data'}]
        log_file = os.path.join(self.log_dir, 'small_log.json')
        with open(log_file, 'w', encoding='utf-8') as f:
            for entry in log_data:
                json.dump(entry, f)
                f.write('\n')
        
        result = self.learner.run_learning_cycle()
        
        # データ不足でスキップされることを確認
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'insufficient_data')
    
    def test_run_learning_cycle_success(self):
        """成功時の学習サイクルテスト"""
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            # 十分なログデータを作成（イベント形式）
            log_data = []
            timestamp = datetime.now().isoformat()
            for i in range(15):
                session_id = f'session_{i}'
                # Start event
                log_data.append({
                    'event_type': 'pipeline_start',
                    'timestamp': timestamp,
                    'data': {
                        'session_id': session_id,
                        'original_text': f'ファイル{i}を作成して'
                    }
                })
                # Completion event
                status = 'success' if i % 4 != 0 else 'error'
                log_data.append({
                    'event_type': 'pipeline_stage_completion',
                    'timestamp': timestamp,
                    'data': {
                        'session_id': session_id,
                        'context_summary': {
                            'intent': 'FILE_CREATE',
                            'intent_confidence': 0.8 + (i % 3) * 0.05,
                            'action_result_status': status
                        }
                    }
                })
                if status == 'error':
                    log_data.append({
                        'event_type': 'action_execution_error',
                        'timestamp': timestamp,
                        'data': {
                            'session_id': session_id,
                            'message': 'Error occurred'
                        }
                    })
            
            log_file = os.path.join(self.log_dir, 'learning_log.json')
            with open(log_file, 'w', encoding='utf-8') as f:
                for entry in log_data:
                    json.dump(entry, f, ensure_ascii=False)
                    f.write('\n')
            
            result = self.learner.run_learning_cycle()
            
            # 成功することを確認
            self.assertEqual(result['status'], 'success')
            self.assertGreater(result['log_count'], 10)
            self.assertIn('report', result)
            
            # レポート内容の確認
            report = result['report']
            self.assertIn('summary', report)
            self.assertIn('patterns', report)
            self.assertIn('suggestions', report)
            self.assertIn('recommendations', report)
    
    def test_config_loading(self):
        """設定読み込みテスト"""
        config = self.learner.config
        
        # デフォルト設定が読み込まれることを確認
        self.assertIn('learning', config)
        self.assertIn('safety', config)
        self.assertEqual(config['learning']['min_pattern_frequency'], 3)
        self.assertEqual(config['learning']['confidence_threshold'], 0.7)
    
    def test_generate_report(self):
        """レポート生成テスト"""
        # サンプルデータ
        logs = [{'test': 'log'}]
        patterns = {
            'success': [
                LearningPattern('success', 'test_pattern', 5, 0.8, {}, [])
            ],
            'error': [],
            'improvement': []
        }
        suggestions = [
            RuleSuggestion(
                'intent_rule',
                {'type': 'test'},
                0.8,
                'test_scope',
                'low',
                'test explanation',
                []
            )
        ]
        
        report = self.learner._generate_report(logs, patterns, suggestions)
        
        # レポート構造の確認
        self.assertIn('timestamp', report)
        self.assertIn('summary', report)
        self.assertIn('patterns', report)
        self.assertIn('suggestions', report)
        self.assertIn('recommendations', report)
        
        # サマリー内容の確認
        summary = report['summary']
        self.assertEqual(summary['total_logs'], 1)
        self.assertEqual(summary['success_patterns'], 1)
        self.assertEqual(summary['rule_suggestions'], 1)

    def test_repair_knowledge_vector_store_is_unified_to_vector_db(self):
        """repair_knowledge のベクトル保存先が vector_db に統一されることを確認"""
        temp_root = tempfile.mkdtemp()
        try:
            create_sample_config(temp_root)
            legacy_dir = os.path.join(temp_root, "resources")
            target_dir = os.path.join(temp_root, "resources", "vectors", "vector_db")
            os.makedirs(legacy_dir, exist_ok=True)

            legacy_meta = os.path.join(legacy_dir, "repair_knowledge_meta.json")
            legacy_vec = os.path.join(legacy_dir, "repair_knowledge_vectors.npy")
            with open(legacy_meta, "w", encoding="utf-8") as f:
                json.dump([{"id": "legacy_pattern", "error_message_regex": "X", "fix_direction": "Y"}], f)
            np.save(legacy_vec, np.zeros((1, 300)))

            _ = AutonomousLearning(temp_root)

            self.assertFalse(os.path.exists(legacy_meta))
            self.assertFalse(os.path.exists(legacy_vec))
            self.assertTrue(os.path.exists(os.path.join(target_dir, "repair_knowledge_meta.json")))
            self.assertTrue(os.path.exists(os.path.join(target_dir, "repair_knowledge_vectors.npy")))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_structural_memory_vector_store_is_unified_to_vector_db(self):
        """structural_memory のベクトル保存先が vector_db に統一されることを確認"""
        temp_root = tempfile.mkdtemp()
        try:
            create_sample_config(temp_root)
            legacy_dir = os.path.join(temp_root, "resources")
            target_dir = os.path.join(temp_root, "resources", "vectors", "vector_db")
            os.makedirs(legacy_dir, exist_ok=True)

            legacy_meta = os.path.join(legacy_dir, "structural_memory_meta.json")
            legacy_vec = os.path.join(legacy_dir, "structural_memory_vectors.npy")
            with open(legacy_meta, "w", encoding="utf-8") as f:
                json.dump([{"id": "legacy_component", "name": "LegacyComponent"}], f)
            np.save(legacy_vec, np.zeros((1, 300)))

            _ = AutonomousLearning(temp_root)

            self.assertFalse(os.path.exists(legacy_meta))
            self.assertFalse(os.path.exists(legacy_vec))
            self.assertTrue(os.path.exists(os.path.join(target_dir, "structural_memory_meta.json")))
            self.assertTrue(os.path.exists(os.path.join(target_dir, "structural_memory_vectors.npy")))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)


class TestIntegration(unittest.TestCase):
    """統合テストクラス"""
    
    def setUp(self):
        """テスト前の準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = os.path.join(self.temp_dir, 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        
        create_sample_config(self.temp_dir)
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_end_to_end_learning_workflow(self):
        """エンドツーエンドの学習ワークフローテスト"""
        import io
        from contextlib import redirect_stdout
        
        # テスト出力を綺麗にするため、標準出力をキャプチャし、警告ログを一時的に無効化
        with redirect_stdout(io.StringIO()):
            with self.assertLogs('src.autonomous_learning.autonomous_learning', level='INFO') as cm:
                # Step 1: 現実的なログデータを作成
                def create_event_sequence(session_id, text, intent, confidence, status, clarification=False, error_msg=None):
                    timestamp = datetime.now().isoformat()
                    events = [
                        {
                            'event_type': 'pipeline_start',
                            'timestamp': timestamp,
                            'data': {'session_id': session_id, 'original_text': text}
                        }
                    ]
                    if clarification:
                        events.append({
                            'event_type': 'clarification_needed',
                            'timestamp': timestamp,
                            'data': {'session_id': session_id}
                        })
                    
                    summary = {
                        'intent': intent,
                        'intent_confidence': confidence,
                        'action_result_status': status
                    }
                    learning_evidence = []
                    if status == "success" and intent == "FILE_CREATE":
                        learning_evidence.append({
                            "type": "intent_example",
                            "approved": True,
                            "intent": "FILE_CREATE",
                            "pattern": "create_file_request",
                            "proposed_rule": {
                                "rule_type": "intent_rule",
                                "rule_definition": {
                                    "type": "intent_detection",
                                    "intent": "FILE_CREATE",
                                    "pattern": "create_file_request",
                                },
                                "impact_scope": "intent_detection",
                                "risk_level": "low",
                                "explanation": "Approved intent example.",
                                "safety_evidence": {
                                    "reviewed": True,
                                    "decision": "approve",
                                    "controls": [{
                                        "control_id": "intent_scope_review",
                                        "passed": True,
                                    }],
                                },
                            },
                        })
                    if status == "error":
                        learning_evidence.append({
                            "type": "error",
                            "approved": True,
                            "error_code": "file_not_found",
                            "proposed_rule": {
                                "rule_type": "retry_rule",
                                "rule_definition": {
                                    "type": "retry_strategy",
                                    "error_pattern": "file_not_found",
                                    "max_retries": 2,
                                },
                                "impact_scope": "error_handling",
                                "risk_level": "medium",
                                "explanation": "Approved retry policy.",
                                "safety_evidence": {
                                    "reviewed": True,
                                    "decision": "approve",
                                    "controls": [{
                                        "control_id": "retry_scope_review",
                                        "passed": True,
                                    }],
                                },
                            },
                        })
                    if clarification:
                        learning_evidence.append({
                            "type": "improvement",
                            "approved": True,
                            "issue": "clarification_required",
                            "pattern": "missing_intent_evidence",
                            "proposed_rule": {
                                "rule_type": "clarification_rule",
                                "rule_definition": {
                                    "type": "clarification_trigger",
                                    "condition": {
                                        "type": "missing_intent_evidence",
                                    },
                                },
                                "impact_scope": "user_experience",
                                "risk_level": "low",
                                "explanation": "Approved clarification policy.",
                                "safety_evidence": {
                                    "reviewed": True,
                                    "decision": "approve",
                                    "controls": [{
                                        "control_id": "clarification_scope_review",
                                        "passed": True,
                                    }],
                                },
                            },
                        })
                    events.append({
                        'event_type': 'pipeline_stage_completion',
                        'timestamp': timestamp,
                        'data': {
                            'session_id': session_id,
                            'context_summary': summary,
                            'learning_evidence': learning_evidence,
                        }
                    })
                    
                    if status == 'error':
                        events.append({
                            'event_type': 'action_execution_error',
                            'timestamp': timestamp,
                            'data': {'session_id': session_id, 'message': error_msg or 'Unknown error'}
                        })
                    return events

                realistic_logs = []
                
                # 成功パターン
                realistic_logs.extend(create_event_sequence('session_1', 'ファイルを作成してください', 'FILE_CREATE', 0.9, 'success'))
                realistic_logs.extend(create_event_sequence('session_2', '新しいファイルを作って', 'FILE_CREATE', 0.85, 'success'))
                realistic_logs.extend(create_event_sequence('session_3', 'ファイル作成をお願いします', 'FILE_CREATE', 0.88, 'success'))
                
                # エラーパターン
                realistic_logs.extend(create_event_sequence('session_4', 'ファイルを削除して', 'FILE_DELETE', 0.8, 'error', error_msg='ファイルが見つかりません'))
                realistic_logs.extend(create_event_sequence('session_5', '別のファイルを削除', 'FILE_DELETE', 0.75, 'error', error_msg='ファイルが見つかりません'))
                
                # 低信頼度パターン
                realistic_logs.extend(create_event_sequence('session_6', 'なんかして', 'GENERAL', 0.3, 'success', clarification=True))
                realistic_logs.extend(create_event_sequence('session_7', 'あれをやって', 'GENERAL', 0.25, 'success', clarification=True))
                realistic_logs.extend(create_event_sequence('session_8', 'よくわからない', 'GENERAL', 0.2, 'success', clarification=True))
                realistic_logs.extend(create_event_sequence('session_9', 'それをお願い', 'GENERAL', 0.35, 'success', clarification=True))
                realistic_logs.extend(create_event_sequence('session_10', 'どうにかして', 'GENERAL', 0.28, 'success', clarification=True))
                
                # 追加: 十分なデータ数を確保するためのダミーログ
                realistic_logs.extend(create_event_sequence('session_11', '予備のログ', 'FILE_CREATE', 0.9, 'success'))

                log_file = os.path.join(self.log_dir, 'realistic_log.json')
                with open(log_file, 'w', encoding='utf-8') as f:
                    for entry in realistic_logs:
                        json.dump(entry, f, ensure_ascii=False)
                        f.write('\n')
                
                # Step 2: 自律学習実行
                learner = AutonomousLearning(self.temp_dir)
                result = learner.run_learning_cycle()
                
                # Step 3: 結果検証
                self.assertEqual(result['status'], 'success')
                self.assertGreaterEqual(result['log_count'], 10)
                self.assertGreater(result['patterns_found'], 0)
                
                # Step 4: レポート内容確認
                report = result['report']
                
                # 成功パターンの確認
                success_patterns = report['patterns']['success']
                self.assertGreater(len(success_patterns), 0)
                
                # エラーパターンの確認
                error_patterns = report['patterns']['error']
                self.assertGreater(len(error_patterns), 0)
                
                # 改善パターンの確認
                improvement_patterns = report['patterns']['improvement']
                self.assertGreater(len(improvement_patterns), 0)
                
                # 推奨事項の確認
                recommendations = report['recommendations']
                self.assertGreater(len(recommendations), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
