# -*- coding: utf-8 -*-
import os
import json
import logging
from typing import Dict, List, Any, Optional
from .models import TestFailure, TDDGoal, CodeFixSuggestion
from .failure_analyzer import TestFailureAnalyzer
from .fix_engine import CodeFixSuggestionEngine

class AdvancedTDDSupport:
    """高度TDD支援のメインクラス"""
    
    def __init__(self, workspace_root: str = ".", test_generator=None, failure_analyzer=None, fix_engine=None, refactoring_analyzer=None, semantic_analyzer=None):
        self.workspace_root = workspace_root
        self.logger = logging.getLogger(__name__)
        
        # 設定の読み込み
        self.config = self._load_config()
        
        # コンポーネントの初期化
        self.test_generator = test_generator # Passed from outside
        self.semantic_analyzer = semantic_analyzer

        # failure_analyzerの初期化
        if failure_analyzer:
            self.failure_analyzer = failure_analyzer
        else:
            self.failure_analyzer = TestFailureAnalyzer(self.config.get('phase3', {}).get('failure_analysis', {}))
        
        # fix_engineの初期化 (外部から渡されない場合は内部で生成)
        if fix_engine:
            self.fix_engine = fix_engine
        else:
            self.fix_engine = CodeFixSuggestionEngine(self.config.get('phase3', {}).get('code_fix', {}), self.semantic_analyzer)

        self.refactoring_analyzer = refactoring_analyzer # Passed from outside
        
        # GoalDrivenTDDEngine was deprecated. Using AutonomousSynthesizer.
        from src.code_synthesis.autonomous_synthesizer import AutonomousSynthesizer
        
        # Create ConfigManager wrapping the raw config
        # Assuming ConfigManager can be initialized meaningfully or we pass a mock/wrapper if needed.
        # Ideally we should use the singleton or proper init if possible, but for now we create one.
        # If ConfigManager requires a path, we might need to handle it.
        # Let's assume ConfigManager(workspace_root) pattern or similar if standard.
        # If not, we might need a dummy adapter. 
        # Checking ConfigManager usage in other files: it usually takes a config_path or similar.
        # Here we have self.config dict.
        
        # Simplest approach: Create a ConfigManager and inject our dict if possible, 
        # or just pass it if AutonomousSynthesizer supports it (it doesn't, it expects object with properties).
        
        # Let's inspect code_synthesizer.py again to see how it uses config_manager.
        # It accesses self.config_manager.scoring_rules.
        
        # So we need an object that has 'scoring_rules' as attribute or property.
        class ConfigAdapter:
            def __init__(self, config_dict, workspace_root):
                self.config = config_dict
                self.workspace_root = workspace_root
                self.scoring_rules = config_dict.get("scoring_rules", {})
                self.domain_dictionary_path = os.path.join(workspace_root, "resources", "domain_dictionary.json") # Default fallback
                self.intent_corpus_path = os.path.join(workspace_root, "resources", "intent_corpus.json") # Default fallback
                self.custom_knowledge_path = os.path.join(workspace_root, "resources", "custom_knowledge.json") # Default fallback
                self.knowledge_base_path = self.custom_knowledge_path
                self.dictionary_db_path = os.path.join(workspace_root, "resources", "dictionary.db") # Default fallback
                self.dependency_map_path = os.path.join(workspace_root, "resources", "dependency_map.json") # Default fallback
                self.error_patterns_path = os.path.join(workspace_root, "resources", "error_patterns.json") # Default fallback
                self.safety_policy_path = os.path.join(workspace_root, "config", "safety_policy.json") # Default fallback
                self.repair_knowledge_path = os.path.join(workspace_root, "resources", "repair_knowledge.json") # Default fallback
                self.storage_dir = os.path.join(workspace_root, "resources")
                self.task_definitions_path = os.path.join(workspace_root, "resources", "task_definitions.json")
                self.method_store_path = os.path.join(workspace_root, "resources", "method_store.json")

            def get_section(self, section_name):
                return self.config.get(section_name, {})

            def get_safety_policy(self):
                # Placeholder for safety policy
                return {}

            def get(self, key, default=None):
                return self.config.get(key, default)

        config_adapter = ConfigAdapter(self.config, self.workspace_root)

        self.tdd_engine = AutonomousSynthesizer(
            config_manager=config_adapter,
            morph_analyzer=None, # will be created internally if None
            vector_engine=None   # will be created internally if None
        )
    
    def _load_config(self) -> Dict[str, Any]:
        """設定ファイルを読み込み"""
        config_path = os.path.join(self.workspace_root, 'config', 'advanced_tdd_config.json')
        
        default_config = {
            'phase3': {
                'failure_analysis': {
                    'confidence_threshold': 0.8,
                    'max_fix_suggestions': 5
                },
                'code_fix': {
                    'safety_levels': ['conservative', 'moderate', 'aggressive'],
                    'auto_apply_threshold': 0.95,
                    'backup_enabled': True
                }
            },
            'phase4': {
                'goal_driven_tdd': {
                    'max_iterations': 10,
                    'quality_gates': {
                        'min_coverage': 80,
                        'max_complexity': 5
                    }
                }
            }
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # デフォルト設定とマージ
                    self._deep_merge(default_config, user_config)
            except Exception as e:
                self.logger.warning(f"設定ファイルの読み込みに失敗、デフォルト設定を使用: {e}")
        
        return default_config
    
    def _deep_merge(self, base: Dict, update: Dict) -> None:
        """辞書の深いマージ"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    # Phase 3: テスト失敗分析・修正提案
    def analyze_and_fix_test_failure(self, test_failure_data: Dict[str, Any], roslyn_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """テスト失敗を分析して修正提案を生成"""
        try:
            # テスト失敗情報の構造化
            test_failure = TestFailure(
                test_file=test_failure_data.get('test_file', ''),
                test_method=test_failure_data.get('test_method', ''),
                error_type=test_failure_data.get('error_type', ''),
                error_message=test_failure_data.get('error_message', ''),
                stack_trace=test_failure_data.get('stack_trace', ''),
                line_number=test_failure_data.get('line_number')
            )
            
            # 失敗分析 (Roslynデータを渡す)
            analysis = self.failure_analyzer.analyze_test_failure(test_failure, roslyn_data)
            
            if analysis['status'] != 'success':
                return analysis
            
            # 修正提案生成
            target_code = test_failure_data.get('target_code', {})
            
            # Handle fix_test_arrange by loading test code instead of production code
            if analysis.get('fix_direction') == 'fix_test_arrange':
                try:
                    # Find test file path from stack trace analysis
                    file_locations = analysis.get('analysis_details', {}).get('stack_trace_analysis', {}).get('file_locations', [])
                    test_file_path = None
                    for loc in file_locations:
                        fpath = loc.get('file', '')
                        if fpath.endswith('Tests.cs') or fpath.endswith('Test.cs') or 'test' in fpath.lower():
                            test_file_path = fpath
                            break
                    
                    if not test_file_path:
                         test_file_path = test_failure_data.get('test_file') # Fallback

                    if test_file_path and os.path.exists(test_file_path):
                        with open(test_file_path, 'r', encoding='utf-8') as f:
                            test_content = f.read()
                        
                        target_code = {
                            'file': test_file_path,
                            'method': test_failure_data.get('test_method', ''),
                            'current_implementation': test_content
                        }
                        self.logger.info(f"Switched target code to test file: {test_file_path} for fix_test_arrange")
                except Exception as ex:
                    self.logger.warning(f"Failed to load test file for fix_test_arrange: {ex}")

            fix_suggestions = self.fix_engine.generate_fix_suggestions(analysis, target_code)
            
            return {
                'status': 'success',
                'analysis': analysis,
                'fix_suggestions': [self._suggestion_to_dict(s) for s in fix_suggestions],
                'validation_plan': self._create_validation_plan(fix_suggestions)
            }
            
        except Exception as e:
            self.logger.error(f"テスト失敗分析中にエラーが発生: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    # Phase 4: ゴール駆動型TDD
    def execute_goal_driven_tdd(self, goal_data: Dict[str, Any]) -> Dict[str, Any]:
        """ゴール駆動型TDDを実行"""
        print(f"[DEBUG] execute_goal_driven_tdd CALLED with goal: {goal_data.get('description')}")
        try:
            # 目標の構造化
            goal = TDDGoal(
                description=goal_data.get('description', ''),
                acceptance_criteria=goal_data.get('acceptance_criteria', []),
                priority=goal_data.get('priority', 'medium'),
                estimated_effort=goal_data.get('estimated_effort', '1 hour')
            )
            
            constraints = goal_data.get('constraints', {})
            context = goal_data.get('context', {})
            
            # TDDサイクル実行 (Using Unified Engine)
            # execute_goal_driven_tdd returns {'status': ..., 'tdd_cycle_results': ..., 'generated_artifacts': ...}
            # decompose_and_synthesize returns {'status': ..., 'results': [{'requirement': ..., 'result': ...}]}
            
            synth_result = self.tdd_engine.decompose_and_synthesize(goal)
            
            # Map result format for compatibility
            cycle_results = []
            code_artifacts = []
            
            if synth_result.get("status") == "success":
                for item in synth_result.get("results", []):
                    req_res = item["result"]
                    code_artifacts.append(req_res.get("code", ""))
                    cycle_results.append({
                        "success": req_res.get("status") in ["success", "partial_success"],
                        "attempts": req_res.get("attempts", 0)
                    })
            
            return {
                'status': synth_result.get("status"),
                'tdd_cycle_results': {
                    'total': len(cycle_results), 
                    'success': sum(1 for c in cycle_results if c["success"]),
                    'total_iterations': len(cycle_results),
                    'success_rate': sum(1 for c in cycle_results if c["success"]) / max(1, len(cycle_results)),
                    'total_time_seconds': 0.0 # Placeholder
                },
                'generated_artifacts': {
                    'code': code_artifacts,
                    'tests': [] # Placeholder
                },
                'quality_metrics': {
                    'score': 80,
                    'estimated_coverage': 0,
                    'cyclomatic_complexity': 0,
                    'technical_debt': "low"
                } # Dummy for compatibility
            }
            
        except Exception as e:
            self.logger.error(f"ゴール駆動型TDD実行中にエラーが発生: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _suggestion_to_dict(self, suggestion: CodeFixSuggestion) -> Dict[str, Any]:
        """CodeFixSuggestionを辞書に変換"""
        return {
            'id': suggestion.id,
            'type': suggestion.type,
            'priority': suggestion.priority,
            'description': suggestion.description,
            'current_code': suggestion.current_code,
            'suggested_code': suggestion.suggested_code,
            'safety_score': suggestion.safety_score,
            'impact_analysis': suggestion.impact_analysis,
            'auto_applicable': suggestion.auto_applicable,
            'line_number': suggestion.line_number
        }
    
    def _create_validation_plan(self, suggestions: List[CodeFixSuggestion]) -> Dict[str, Any]:
        """検証計画を作成"""
        if not suggestions:
            return {'steps': [], 'estimated_time': '0 seconds'}
        
        steps = [
            'Apply suggested fix',
            'Run failing test',
            'Run all related tests',
            'Verify no regression'
        ]
        
        estimated_time = f"{len(suggestions) * 30} seconds"
        
        return {
            'steps': steps,
            'estimated_time': estimated_time,
            'safety_checks': ['Backup original code', 'Validate syntax', 'Check test results']
        }

def create_sample_config(workspace_root: str):
    """サンプル設定ファイルを作成"""
    config_dir = os.path.join(workspace_root, 'config')
    os.makedirs(config_dir, exist_ok=True)
    
    sample_config = {
        'phase3': {
            'failure_analysis': {
                'supported_error_types': ['assertion_failure', 'compile_error', 'runtime_error'],
                'confidence_threshold': 0.8,
                'max_fix_suggestions': 5
            },
            'code_fix': {
                'safety_levels': ['conservative', 'moderate', 'aggressive'],
                'auto_apply_threshold': 0.95,
                'backup_enabled': True,
                'impact_analysis_depth': 3
            }
        },
        'phase4': {
            'goal_driven_tdd': {
                'max_iterations': 10,
                'requirement_decomposition_depth': 3,
                'quality_gates': {
                    'min_coverage': 80,
                    'max_complexity': 5,
                    'min_maintainability': 70
                }
            },
            'tdd_cycle': {
                'red_phase_timeout': 30,
                'green_phase_timeout': 120,
                'refactor_phase_timeout': 60
            }
        },
        'integration': {
            'autonomous_learning_enabled': True,
            'coverage_integration_enabled': True,
            'pattern_learning_threshold': 5
        }
    }
    
    config_path = os.path.join(config_dir, 'advanced_tdd_config.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(sample_config, f, ensure_ascii=False, indent=2)
    
    return config_path

if __name__ == "__main__":
    # 基本的な使用例
    workspace_root = "."
    
    # サンプル設定作成
    create_sample_config(workspace_root)
    
    # 高度TDD支援実行
    tdd_support = AdvancedTDDSupport(workspace_root)
    
    # Phase 3 例: テスト失敗分析
    test_failure_example = {
        'test_file': 'tests/CalculatorTests.cs',
        'test_method': 'Add_ShouldReturnSum_WhenValidInput',
        'error_type': 'assertion_failure',
        'error_message': 'Expected: 5, Actual: 0',
        'stack_trace': 'at Calculator.Add(Int32 a, Int32 b) in Calculator.cs:line 15',
        'target_code': {
            'file': 'src/Calculator.cs',
            'method': 'Add',
            'current_implementation': 'public int Add(int a, int b) { return 0; }'
        }
    }
    
    phase3_result = tdd_support.analyze_and_fix_test_failure(test_failure_example)
    print("Phase 3 結果:")
    print(json.dumps(phase3_result, ensure_ascii=False, indent=2))
    
    # Phase 4 例: ゴール駆動型TDD
    goal_example = {
        'description': '電卓アプリケーションに四則演算機能を追加',
        'acceptance_criteria': [
            '加算機能の実装',
            '減算機能の実装',
            'ゼロ除算エラーの処理'
        ],
        'constraints': {
            'language': 'csharp',
            'test_framework': 'xunit',
            'coverage_target': 90
        },
        'context': {
            'existing_code': 'src/Calculator.cs'
        }
    }
    
    phase4_result = tdd_support.execute_goal_driven_tdd(goal_example)
    print("\nPhase 4 結果:")
    print(json.dumps(phase4_result, ensure_ascii=False, indent=2))
