# -*- coding: utf-8 -*-
# src/autonomous_learning/autonomous_learning.py

"""
対話ログからの自律学習機能 - メインコーディネーター
"""

import json
import os
import logging
import threading
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# サブコンポーネントのインポート
from .log_analyzer import LogAnalyzer, LearningPattern
from .pattern_learner import PatternLearner, RuleSuggestion
from .event_processor import EventProcessor
from .safety_evaluator import SafetyEvaluator

# 既存コンポーネントのインポート
from src.advanced_tdd.knowledge_base import RepairKnowledgeBase
from .structural_memory import StructuralMemory
from .compliance_auditor import ComplianceAuditor
from src.config.config_manager import ConfigManager
from src.vector_engine.vector_engine import VectorEngine

class AutonomousLearning:
    """自律学習のメインクラス"""

    def __init__(self, workspace_root: str, log_manager=None, intent_detector=None, vector_engine=None, morph_analyzer=None):
        self.workspace_root = Path(workspace_root)
        self.log_manager = log_manager
        self.intent_detector = intent_detector
        cfg = None
        try:
            cfg = ConfigManager(str(self.workspace_root))
        except Exception:
            cfg = None

        if vector_engine is None:
            try:
                model_path = cfg.vector_model_path if cfg else None
                vector_engine = VectorEngine(model_path=model_path)
            except Exception:
                vector_engine = None

        self.vector_engine = vector_engine
        self.morph_analyzer = morph_analyzer
        self.logger = logging.getLogger(__name__)
        self.learning_diagnostics: List[Dict[str, Any]] = []

        # 設定の読み込み
        self.config = self._load_config()

        # 既存コンポーネントの初期化
        self.repair_kb = RepairKnowledgeBase(
            str(self.workspace_root),
            vector_engine=vector_engine,
            morph_analyzer=morph_analyzer,
            config_manager=cfg
        )
        structural_storage_dir = str(self.workspace_root / "resources" / "vectors" / "vector_db")
        if cfg and getattr(cfg, "storage_dir", None):
            structural_storage_dir = str(cfg.storage_dir)
        self._migrate_legacy_structural_memory(structural_storage_dir)
        self.structural_memory = StructuralMemory(
            structural_storage_dir,
            config_manager=cfg,
            vector_engine=vector_engine,
            morph_analyzer=morph_analyzer
        )
        self.compliance_auditor = ComplianceAuditor(str(self.workspace_root), structural_memory=self.structural_memory)

        # 新規サブコンポーネントの初期化
        log_directory = self.workspace_root / 'logs'
        self.log_analyzer = LogAnalyzer(str(log_directory))
        self.pattern_learner = PatternLearner(self.config.get('learning', {}))
        self.safety_evaluator = SafetyEvaluator(self.config.get('safety', {}))
        self.event_processor = EventProcessor(self.workspace_root, repair_kb=self.repair_kb)
        self._event_threads = []
        self._event_threads_lock = threading.Lock()

        # ConfigManager と Planner が参照する config/retry_rules.json に統一
        self.retry_rules_path = self.workspace_root / 'config' / 'retry_rules.json'

    def _migrate_legacy_structural_memory(self, target_dir: str):
        """Legacy 配置（workspace_root / cache）から統一保存先へ移行する。"""
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception:
            return

        legacy_dirs = [
            str(self.workspace_root),
            str(self.workspace_root / "resources"),
            str(self.workspace_root / "cache")
        ]
        target_meta = os.path.join(target_dir, "structural_memory_meta.json")
        target_vec = os.path.join(target_dir, "structural_memory_vectors.npy")

        for legacy_dir in legacy_dirs:
            legacy_meta = os.path.join(legacy_dir, "structural_memory_meta.json")
            legacy_vec = os.path.join(legacy_dir, "structural_memory_vectors.npy")
            try:
                if os.path.exists(legacy_meta):
                    if not os.path.exists(target_meta):
                        shutil.move(legacy_meta, target_meta)
                    else:
                        # Keep the freshest copy, then remove legacy to avoid split state.
                        if os.path.getmtime(legacy_meta) > os.path.getmtime(target_meta):
                            shutil.copy2(legacy_meta, target_meta)
                        os.remove(legacy_meta)
                if os.path.exists(legacy_vec):
                    if not os.path.exists(target_vec):
                        shutil.move(legacy_vec, target_vec)
                    else:
                        if os.path.getmtime(legacy_vec) > os.path.getmtime(target_vec):
                            shutil.copy2(legacy_vec, target_vec)
                        os.remove(legacy_vec)
            except Exception as e:
                self.logger.warning(f"Failed to migrate structural memory from {legacy_dir}: {e}")

    def find_relevant_code(
        self,
        query: str,
        top_k: int = 3,
        *,
        component_type: Optional[str] = None,
        role: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        symbol_id: Optional[str] = None,
        return_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """明示された構造条件を満たすコード要素を検索する。"""
        return self.structural_memory.search_component(
            query,
            top_k=top_k,
            component_type=component_type,
            role=role,
            capabilities=capabilities,
            symbol_id=symbol_id,
            return_type=return_type,
        )

    def get_repair_suggestion(self, error_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """エラー情報に基づき、修復またはリトライの提案を取得する"""
        error_type = error_data.get('original_error_type') or error_data.get('error_type')
        error_msg = error_data.get('message') or error_data.get('original_error', '')

        if error_type and error_msg:
            fix_direction = self.repair_kb.get_best_fix_direction(error_type, error_msg)
            if fix_direction:
                suggestion = self._map_fix_direction_to_plan(fix_direction, error_data)
                if suggestion:
                    suggestion['evidence'] = f"RepairKnowledgeBaseに過去の解決パターン（原因: {error_type}）が記録されています。"
                    return suggestion

        retry_rules = self._load_retry_rules()
        for rule in retry_rules:
            if rule.get('error_type') == error_type:
                if 'message_pattern' in rule and rule['message_pattern'] not in error_msg:
                    continue

                return {
                    'action': 'RETRY_WITH_ADJUSTMENT',
                    'parameters': rule.get('parameters', {}),
                    'suggestion_text': rule.get('suggestion_text', '再試行しますか？'),
                    'reason': f"リトライルール「{error_type}」に適合しました。",
                    'evidence': f"config/retry_rules.json に定義された自動回復ルールに基づいています。"
                }
        return None

    def _map_fix_direction_to_plan(self, fix_direction: str, error_data: Dict[str, Any]) -> Dict[str, Any]:
        if fix_direction == 'self_healing_test':
            return {
                'action': 'ANALYZE_TEST_FAILURE',
                'parameters': {'test_file': 'auto_detect'},
                'reason': 'テスト失敗に対する修復ナレッジあり'
            }
        return None

    def _load_retry_rules(self) -> List[Dict[str, Any]]:
        if not self.retry_rules_path.exists():
            return []
        try:
            with self.retry_rules_path.open('r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('retry_rules', [])
        except Exception:
            return []

    def _save_retry_rules(self, rules: List[Dict[str, Any]]):
        self.retry_rules_path.parent.mkdir(parents=True, exist_ok=True)
        data = {'retry_rules': rules}
        try:
            with self.retry_rules_path.open('w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save retry rules: {e}")

    def _load_config(self) -> Dict[str, Any]:
        config_path = self.workspace_root / 'config' / 'autonomous_learning.json'
        default_config = {
            'learning': {
                'days_back': 7
            },
            'safety': {
                'allowed_risk_levels': ['low', 'medium'],
                'require_safety_review': True
            }
        }
        if config_path.exists():
            try:
                with config_path.open('r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                self.logger.warning(f"設定ファイルの読み込みに失敗、デフォルト設定を使用: {e}")
        return default_config

    def trigger_learning(self, event_type: str, data: Dict[str, Any], async_mode: bool = True) -> Dict[str, Any]:
        if async_mode:
            def process_and_unregister():
                try:
                    self.event_processor.process_event(event_type, data)
                except Exception as exc:
                    with self._event_threads_lock:
                        self.learning_diagnostics.append({
                            "type": "ASYNC_LEARNING_ERROR",
                            "event_type": event_type,
                            "error_type": type(exc).__name__,
                        })
                finally:
                    current = threading.current_thread()
                    with self._event_threads_lock:
                        if current in self._event_threads:
                            self._event_threads.remove(current)

            thread = threading.Thread(
                target=process_and_unregister,
                name=f"learning-event-{event_type}",
            )
            thread.daemon = False
            with self._event_threads_lock:
                self._event_threads.append(thread)
            try:
                thread.start()
            except Exception:
                with self._event_threads_lock:
                    self._event_threads.remove(thread)
                raise
            return {'status': 'accepted', 'mode': 'async'}
        else:
            return self.event_processor.process_event(event_type, data)

    def wait_for_pending_events(self, timeout: float | None = None) -> bool:
        """開始済みイベントが完了するまで待機する。"""
        with self._event_threads_lock:
            pending = list(self._event_threads)
        for thread in pending:
            thread.join(timeout=timeout)
            if thread.is_alive():
                return False
        return True

    def close(self, timeout: float | None = None) -> bool:
        return self.wait_for_pending_events(timeout=timeout)

    def record_user_feedback(self, finding_id: str, feedback: str):
        return self.trigger_learning('USER_FEEDBACK', {
            'finding_id': finding_id,
            'feedback': feedback,
            'timestamp': datetime.now().isoformat()
        }, async_mode=False)

    def record_terminology_mapping(
        self,
        finding_id: str,
        source: str,
        target: str,
    ):
        return self.trigger_learning('USER_FEEDBACK', {
            'finding_id': finding_id,
            'terminology_mapping': {
                'source': source,
                'target': target,
            },
            'timestamp': datetime.now().isoformat(),
        }, async_mode=False)

    def _merge_learned_mappings_to_dictionary(self):
        mappings_path = self.workspace_root / 'logs' / 'learned_mappings.jsonl'
        if not mappings_path.exists(): return

        learned = []
        try:
            with open(mappings_path, 'r', encoding='utf-8') as mapping_file:
                for line_number, line in enumerate(mapping_file, start=1):
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError as exc:
                        self.learning_diagnostics.append({
                            "type": "INVALID_LEARNED_MAPPING",
                            "file": str(mappings_path),
                            "line": line_number,
                            "error_type": type(exc).__name__,
                        })
                        continue
                    if not isinstance(entry, dict):
                        self.learning_diagnostics.append({
                            "type": "INVALID_LEARNED_MAPPING",
                            "file": str(mappings_path),
                            "line": line_number,
                            "error_type": "mapping_must_be_object",
                        })
                        continue
                    learned.append(entry)
        except OSError as exc:
            self.learning_diagnostics.append({
                "type": "LEARNED_MAPPING_READ_ERROR",
                "file": str(mappings_path),
                "error_type": type(exc).__name__,
            })
            return

        if not learned: return

        dict_path = self.workspace_root / 'resources' / 'domain_dictionary.json'
        if not dict_path.exists():
             self.logger.warning(f"Dictionary not found at {dict_path}")
             return

        try:
            with open(dict_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            self.learning_diagnostics.append({
                "type": "DOMAIN_DICTIONARY_READ_ERROR",
                "file": str(dict_path),
                "error_type": type(exc).__name__,
            })
            return

        try:
            mappings = data.get("mappings", {})
            updated = False
            for entry in learned:
                jp, en = entry.get("jp"), entry.get("en")
                if jp and en:
                    if jp not in mappings:
                        mappings[jp] = [en]
                        updated = True
                    elif en not in mappings[jp]:
                        mappings[jp].append(en)
                        updated = True

            if updated:
                data["mappings"] = mappings
                with open(dict_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.logger.info(f"Updated domain_dictionary.json with learned mappings.")

                processed_path = mappings_path.with_name('learned_mappings.jsonl.processed')
                if processed_path.exists(): processed_path.unlink()
                mappings_path.rename(processed_path)
        except OSError as exc:
            self.learning_diagnostics.append({
                "type": "LEARNED_MAPPING_WRITE_ERROR",
                "file": str(dict_path),
                "error_type": type(exc).__name__,
            })

    def generate_knowledge_summary(self) -> Dict[str, Any]:
        summary = {
            "timestamp": datetime.now().isoformat(),
            "repair_knowledge": {
                "patterns_count": len(self.repair_kb.items),
                "stats_count": len(self.repair_kb.fix_stats),
                "type_mappings_count": len(self.repair_kb.type_mappings)
            },
            "retry_rules": {
                "count": len(self._load_retry_rules())
            },
            "compliance": {
                "findings_count": len(self.compliance_auditor.findings),
                "proactive_suggestion": self.compliance_auditor.generate_proactive_suggestion()
            },
            "recent_feedback": []
        }
        feedback_path = self.workspace_root / 'logs' / 'behavioral_feedback.jsonl'
        if feedback_path.exists():
            try:
                with open(feedback_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                first_line_number = max(1, len(lines) - 4)
                for offset, line in enumerate(lines[-5:]):
                    try:
                        feedback = json.loads(line)
                    except json.JSONDecodeError as exc:
                        self.learning_diagnostics.append({
                            "type": "INVALID_BEHAVIORAL_FEEDBACK",
                            "file": str(feedback_path),
                            "line": first_line_number + offset,
                            "error_type": type(exc).__name__,
                        })
                        continue
                    if isinstance(feedback, dict):
                        summary["recent_feedback"].append(feedback)
                    else:
                        self.learning_diagnostics.append({
                            "type": "INVALID_BEHAVIORAL_FEEDBACK",
                            "file": str(feedback_path),
                            "line": first_line_number + offset,
                            "error_type": "feedback_must_be_object",
                        })
            except OSError as exc:
                self.learning_diagnostics.append({
                    "type": "BEHAVIORAL_FEEDBACK_READ_ERROR",
                    "file": str(feedback_path),
                    "error_type": type(exc).__name__,
                })
        return summary

    def run_learning_cycle(self) -> Dict[str, Any]:
        """学習サイクルを実行（Batch Path）"""
        try:
            self.logger.info("自律学習サイクルを開始")
            days_back = self.config['learning']['days_back']
            logs = self.log_analyzer.collect_logs(days_back)

            if len(logs) < 10:
                return {'status': 'skipped', 'reason': 'insufficient_data', 'log_count': len(logs)}

            patterns = self.log_analyzer.extract_patterns(logs)
            total_patterns = sum(len(p) for p in patterns.values())
            suggestions = self.pattern_learner.learn_from_patterns(patterns)
            safe_suggestions = self.safety_evaluator.evaluate_suggestions(suggestions)
            applied_count = self.apply_suggestions(safe_suggestions)

            # 追加学習プロセス
            log_directory = self.workspace_root / 'logs'
            self.repair_kb.learn_from_session_logs(str(log_directory))
            self._merge_learned_mappings_to_dictionary()
            self.structural_memory.index_project()
            self.compliance_auditor.run_full_audit()

            report = self._generate_report(logs, patterns, safe_suggestions)
            report['applied_count'] = applied_count

            return {
                'status': 'success',
                'log_count': len(logs),
                'patterns_found': total_patterns,
                'suggestions_generated': len(suggestions),
                'safe_suggestions': len(safe_suggestions),
                'rules_applied': applied_count,
                'report': report
            }
        except Exception as e:
            self.logger.error(f"学習サイクル中にエラーが発生: {e}")
            return {'status': 'error', 'error': str(e)}

    def apply_suggestions(self, suggestions: List[RuleSuggestion]) -> int:
        applied_count = 0
        for suggestion in suggestions:
            if suggestion.rule_type == 'intent_rule':
                if not self.intent_detector:
                    continue
                rule = suggestion.rule_definition
                self.intent_detector.add_intent_rule(rule.get('intent'), rule.get('pattern'), 0.9)
                applied_count += 1
            elif suggestion.rule_type == 'retry_rule':
                rule = suggestion.rule_definition
                current_rules = self._load_retry_rules()
                if not any(r.get('error_pattern') == rule.get('error_pattern') for r in current_rules):
                    new_rule = {
                        "error_type": rule.get('error_pattern'),
                        "suggestion_text": f"{rule.get('error_pattern')}が発生しました。再試行します。",
                        "parameters": {}
                    }
                    current_rules.append(new_rule)
                    self._save_retry_rules(current_rules)
                    applied_count += 1
        return applied_count

    def _generate_report(self, logs: List[Dict[str, Any]], patterns: Dict[str, List[LearningPattern]], suggestions: List[RuleSuggestion]) -> Dict[str, Any]:
        return {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_logs': len(logs),
                'success_patterns': len(patterns['success']),
                'error_patterns': len(patterns['error']),
                'improvement_patterns': len(patterns['improvement']),
                'rule_suggestions': len(suggestions)
            },
            'patterns': {
                'success': [self._pattern_to_dict(p) for p in patterns['success']],
                'error': [self._pattern_to_dict(p) for p in patterns['error']],
                'improvement': [self._pattern_to_dict(p) for p in patterns['improvement']]
            },
            'suggestions': [self._suggestion_to_dict(s) for s in suggestions],
            'recommendations': self._generate_recommendations(suggestions)
        }

    def _pattern_to_dict(self, pattern: LearningPattern) -> Dict[str, Any]:
        return {
            'pattern_type': pattern.pattern_type,
            'pattern': pattern.pattern,
            'frequency': pattern.frequency,
            'confidence': pattern.confidence,
            'context': pattern.context,
            'example_count': len(pattern.examples)
        }

    def _suggestion_to_dict(self, suggestion: RuleSuggestion) -> Dict[str, Any]:
        return {
            'rule_type': suggestion.rule_type,
            'rule_definition': suggestion.rule_definition,
            'confidence': suggestion.confidence,
            'impact_scope': suggestion.impact_scope,
            'risk_level': suggestion.risk_level,
            'explanation': suggestion.explanation,
            'supporting_evidence': suggestion.supporting_evidence
        }

    def _generate_recommendations(self, suggestions: List[RuleSuggestion]) -> List[str]:
        recommendations = []
        if not suggestions:
            recommendations.append("新しいルール提案はありません。より多くのデータが必要です。")
            return recommendations

        low_risk = [s for s in suggestions if s.risk_level == 'low']
        medium_risk = [s for s in suggestions if s.risk_level == 'medium']

        if low_risk: recommendations.append(f"{len(low_risk)}個の低リスクルールは自動適用を推奨します。")
        if medium_risk: recommendations.append(f"{len(medium_risk)}個の中リスクルールは慎重な検討後の適用を推奨します。")
        return recommendations
