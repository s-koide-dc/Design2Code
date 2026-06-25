import unittest
import sys
import tempfile
import textwrap
from pathlib import Path
from src.response_generator.response_generator import ResponseGenerator
from src.response_rewriter.response_rewriter import ResponseRewriter
from src.utils.dialogue_state import PENDING_CONFIRMATION


class _StubRewritePlugin:
    def __init__(self, rewritten_text):
        self.rewritten_text = rewritten_text

    def rewrite(self, request):
        return self.rewritten_text


class _StubConfigManager:
    def __init__(self, enabled=True):
        self.response_rewriter_config = {
            "enabled": enabled,
            "provider": "stub",
            "rewrite_allowed_intents": ["GENERAL"],
            "max_input_chars": 1200,
            "max_length_ratio": 1.6,
            "rewrite_error_messages": False,
        }

class TestResponseGenerator(unittest.TestCase):

    def setUp(self):
        self.generator = ResponseGenerator()
        self._temp_dirs = []

    def tearDown(self):
        for temp_dir in self._temp_dirs:
            temp_dir.cleanup()

    def _make_temp_backend(self, body: str) -> str:
        temp_dir = tempfile.TemporaryDirectory()
        self._temp_dirs.append(temp_dir)
        script_path = Path(temp_dir.name) / "rewrite_backend.py"
        script_path.write_text(textwrap.dedent(body), encoding="utf-8")
        return str(script_path)

    def test_happy_path_weather_question_with_concept(self):
        """
        ハッピーパス: 「天気」と関連概念「晴れ」がトピックにある場合、テンプレート応答を生成する。
        """
        initial_context = {
            "analysis": {"topics": ["今日", "天気", "晴れ"]},
            "pipeline_history": ["morph_analyzer", "syntactic_analyzer", "semantic_analyzer"]
        }
        
        result_context = self.generator.generate(initial_context)
        
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertGreater(len(result_context["response"]["text"]), 0) # Check if response text is not empty
        self.assertIn("response_generator", result_context["pipeline_history"])
        self.assertEqual(len(result_context.get("errors", [])), 0)

    def test_unknown_concept(self):
        """
        主要トピックは存在するが、関連概念が見つからない場合、トピックに特化したデフォルト応答を返す。
        """
        initial_context = {"analysis": {"topics": ["今日", "天気"]}, "pipeline_history": []}
        
        result_context = self.generator.generate(initial_context)
        
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertGreater(len(result_context["response"]["text"]), 0) # Check if response text is not empty

    def test_no_known_topic(self):
        """
        既知のトピックが一つもない場合、汎用のデフォルト応答を返す。
        """
        initial_context = {"analysis": {"topics": ["猫", "かわいい"]}, "pipeline_history": []}
        
        result_context = self.generator.generate(initial_context)
        
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertGreater(len(result_context["response"]["text"]), 0) # Check if response text is not empty

    def test_edge_case_empty_topics(self):
        """
        エッジケース: 空のトピックリスト。
        """
        initial_context = {"analysis": {"topics": []}, "pipeline_history": []}
        
        result_context = self.generator.generate(initial_context)
        
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertGreater(len(result_context["response"]["text"]), 0) # Check if response text is not empty
        self.assertIn("response_generator", result_context["pipeline_history"])

    def test_edge_case_no_topics(self):
        """
        エッジケース: contextにtopicsキーが存在しない場合、エラーではなくデフォルト応答を返す。
        """
        initial_context = {"analysis": {}, "pipeline_history": []}
        
        result_context = self.generator.generate(initial_context)
        
        self.assertEqual(len(result_context.get("errors", [])), 0) # No errors should be generated
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertEqual(result_context["response"]["text"], self.generator.default_response) # Should return default response

    def test_smalltalk_uses_concise_natural_response(self):
        context = {
            "analysis": {"intent": "SMALLTALK"},
            "pipeline_history": [],
        }

        result_context = self.generator.generate(context)

        self.assertEqual(
            result_context["response"]["text"],
            "もちろんです。少しお話ししましょうか。",
        )

    def test_in_progress_task_uses_dynamic_status_message(self):
        context = {
            "analysis": {},
            "pipeline_history": [],
            "task": {
                "name": "GENERATE_TESTS",
                "state": "IN_PROGRESS",
                "parameters": {"filename": {"value": "src/sample.py"}}
            }
        }

        result_context = self.generator.generate(context)

        self.assertIn("GENERATE_TESTSを進めています。対象はsrc/sample.pyです。完了したらお知らせします。", result_context["response"]["text"])

    def test_task_clarification_status_uses_natural_prompt(self):
        context = {
            "analysis": {},
            "pipeline_history": [],
            "task": {
                "name": "FILE_CREATE",
                "clarification_needed": True,
                "clarification_type": "MISSING_ENTITY",
                "awaiting_entity": "ファイル名",
            }
        }

        result_context = self.generator.generate(context)

        self.assertIn("FILE_CREATEを進めるために、ファイル名を教えてください。", result_context["response"]["text"])

    def test_task_approval_status_uses_natural_prompt(self):
        context = {
            "analysis": {},
            "pipeline_history": [],
            "task": {
                "name": "CMD_RUN",
                "clarification_needed": True,
                "clarification_type": "APPROVAL",
                "parameters": {"command": {"value": "dir"}},
            }
        }

        result_context = self.generator.generate(context)

        self.assertIn("CMD_RUNを進める前に、対象のdirについて承認をお願いします。", result_context["response"]["text"])

    def test_success_action_uses_dynamic_binding_and_generated_files(self):
        context = {
            "analysis": {"intent": "GENERATE_TESTS"},
            "pipeline_history": [],
            "task": {
                "name": "GENERATE_TESTS",
                "parameters": {"filename": {"value": "src/sample.py"}}
            },
            "action_result": {
                "status": "success",
                "generated_files": [
                    "C:\\workspace\\NLP\\tests\\generated\\test_sample.py"
                ]
            }
        }

        result_context = self.generator.generate(context)

        self.assertIn("GENERATE_TESTSが完了しました。対象は src/sample.py です。", result_context["response"]["text"])
        self.assertIn("生成物: tests\\generated\\test_sample.py", result_context["response"]["text"])

    def test_error_action_translates_structured_error(self):
        context = {
            "analysis": {"intent": "CS_BUILD"},
            "pipeline_history": [],
            "task": {
                "name": "CS_BUILD",
                "parameters": {"project_path": {"value": "src/App.csproj"}}
            },
            "action_result": {
                "status": "error",
                "message": "build failed",
                "type": "TimeoutExpired"
            }
        }

        result_context = self.generator.generate(context)

        self.assertIn("CS_BUILDの実行中に問題が発生しました。", result_context["response"]["text"])
        self.assertIn("処理時間の上限を超えたため、途中で停止しました。", result_context["response"]["text"])

    def test_task_interruption_appends_resumption_message(self):
        context = {
            "analysis": {"intent": "GENERAL"},
            "pipeline_history": [],
            "task_interruption": True,
            "task": {
                "name": "BACKUP_AND_DELETE",
                "clarification_message": "続けるには承認してください。"
            }
        }

        result_context = self.generator.generate(context)

        self.assertIn("元の作業に戻るため、次の確認をお願いします。", result_context["response"]["text"])
        self.assertIn("続けるには承認してください。", result_context["response"]["text"])

    def test_finalize_response_uses_rewriter_when_enabled(self):
        rewriter = ResponseRewriter(
            config_manager=_StubConfigManager(enabled=True),
            plugin=_StubRewritePlugin("丁寧に言い換えた応答です。"),
        )
        generator = ResponseGenerator(response_rewriter=rewriter)
        context = {
            "analysis": {"intent": "GENERAL"},
            "pipeline_history": [],
        }

        result_context = generator.generate(context)

        self.assertEqual(result_context["response"]["text"], "丁寧に言い換えた応答です。")

    def test_finalize_response_accepts_llm_backend_rewrite(self):
        script_path = self._make_temp_backend(
            """
            import json
            import sys

            for raw_line in sys.stdin:
                line = raw_line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                rewritten = payload["input"]["response_text"] + "（LLM自然化）。"
                sys.stdout.write(json.dumps({"text": rewritten}, ensure_ascii=False) + "\\n")
                sys.stdout.flush()
            """
        )
        config_manager = _StubConfigManager(enabled=True)
        config_manager.response_rewriter_config.update(
            {
                "provider": "persistent_subprocess_jsonl",
                "command": [sys.executable, script_path],
                "response_format": "json",
                "timeout_seconds": 5,
                "prompt_contract": {
                    "rewrite_style": "natural_japanese",
                    "instruction": "与えられた response_text の事実を変えずに、日本語の自然さだけを整えてください。"
                },
                "max_length_ratio": 3.0,
            }
        )
        rewriter = ResponseRewriter(config_manager=config_manager)
        self.addCleanup(getattr(rewriter.plugin, "close", lambda: None))
        generator = ResponseGenerator(response_rewriter=rewriter)

        result_context = generator.generate({"analysis": {"intent": "GENERAL"}, "pipeline_history": []})

        self.assertTrue(result_context["response"]["text"].endswith("（LLM自然化）。"))

    def test_finalize_response_skips_rewriter_for_structured_output(self):
        rewriter = ResponseRewriter(
            config_manager=_StubConfigManager(enabled=True),
            plugin=_StubRewritePlugin("書き換えられてはいけない"),
        )
        generator = ResponseGenerator(response_rewriter=rewriter)
        context = {
            "analysis": {"intent": "CS_IMPACT_SCOPE"},
            "pipeline_history": [],
            "task": {"name": "CS_IMPACT_SCOPE"},
            "action_result": {
                "status": "success",
                "target_name": "TargetMethod",
                "impacted_methods": ["OtherMethod"],
                "message": "解析結果"
            },
        }

        result_context = generator.generate(context)

        self.assertIn("```mermaid", result_context["response"]["text"])
        self.assertNotEqual(result_context["response"]["text"], "書き換えられてはいけない")

    def test_goal_driven_tdd_dialogue_metadata_creates_specific_response(self):
        context = {
            "analysis": {"intent": "EXECUTE_GOAL_DRIVEN_TDD"},
            "pipeline_history": [],
            "task": {
                "name": "EXECUTE_GOAL_DRIVEN_TDD",
                "parameters": {"goal_description": {"value": "注文割引ロジックを実装"}}
            },
            "action_result": {
                "status": "success",
                "dialogue_metadata": {
                    "phase": "goal_driven_tdd",
                    "goal_description": "注文割引ロジックを実装",
                    "iteration_count": 3,
                    "generated_code_count": 2,
                    "generated_test_count": 1
                }
            }
        }

        result_context = self.generator.generate(context)

        self.assertIn("注文割引ロジックを実装 のTDD実行が完了しました。", result_context["response"]["text"])
        self.assertIn("コード 2 件、テスト 1 件", result_context["response"]["text"])

    def test_failure_analysis_dialogue_metadata_creates_specific_response(self):
        context = {
            "analysis": {"intent": "ANALYZE_TEST_FAILURE"},
            "pipeline_history": [],
            "action_result": {
                "status": "success",
                "dialogue_metadata": {
                    "phase": "failure_analysis",
                    "failure_count": 2,
                    "suggestion_count": 3,
                    "primary_target_file": "src\\Calculator.cs",
                    "failed_test_names": ["CalculatorTests.Add_ShouldReturnSum"],
                    "primary_reason": "method_returns_default_value により Add の修正が必要です。",
                    "primary_recommended_action": "apply_code_fix",
                    "primary_target_summary": "CalculatorTests.Add_ShouldReturnSum / Add"
                }
            }
        }

        result_context = self.generator.generate(context)

        self.assertIn("テスト失敗分析が完了しました。", result_context["response"]["text"])
        self.assertIn("src\\Calculator.cs を中心に 3 件の修正案", result_context["response"]["text"])
        self.assertIn("原因要約: method_returns_default_value により Add の修正が必要です。", result_context["response"]["text"])
        self.assertIn("次は 修正案の適用 を進めてください。", result_context["response"]["text"])
        self.assertIn("修正案をコードへ反映します。", result_context["response"]["text"])

    def test_code_fix_dialogue_metadata_uses_action_description(self):
        context = {
            "analysis": {"intent": "APPLY_CODE_FIX"},
            "pipeline_history": [],
            "action_result": {
                "status": "success",
                "dialogue_metadata": {
                    "phase": "code_fix",
                    "applied_count": 2,
                    "modified_files": ["src\\Calculator.cs", "tests\\CalculatorTests.cs"],
                    "reason": "Add メソッドの戻り値とテスト期待値を揃えました。",
                    "recommended_action": "run_related_tests"
                }
            }
        }

        result_context = self.generator.generate(context)

        self.assertIn("コード修正の適用が完了しました。", result_context["response"]["text"])
        self.assertIn("2 件を src\\Calculator.cs を含む 2 ファイルへ反映しました。", result_context["response"]["text"])
        self.assertIn("次は 関連テストの再実行 を進めてください。", result_context["response"]["text"])
        self.assertIn("修正後の関連テストを再実行します。", result_context["response"]["text"])

    def test_generate_confirmation_message_create_file(self):
        context = {
            "plan": {
                "action_method": "_create_file",
                "parameters": {"filename": "new_report.txt", "content": "test content"},
                "confirmation_needed": True
            },
            "pipeline_history": []
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertIn("ファイル 'new_report.txt' を作成します。よろしいですか？", result_context["response"]["text"])
        self.assertIn("response_generator_confirmation", result_context["pipeline_history"])

    def test_generate_confirmation_message_delete_file(self):
        context = {
            "plan": {
                "action_method": "_delete_file",
                "parameters": {"filename": "old_data.csv"},
                "confirmation_needed": True
            },
            "pipeline_history": []
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertIn("ファイル 'old_data.csv' を削除します。よろしいですか？", result_context["response"]["text"])
        self.assertIn("response_generator_confirmation", result_context["pipeline_history"])

    def test_generate_confirmation_message_run_command(self):
        context = {
            "plan": {
                "action_method": "_run_command",
                "parameters": {"command": "ls -la"},
                "confirmation_needed": True
            },
            "pipeline_history": []
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertIn("コマンド 'ls -la' を実行します。よろしいですか？", result_context["response"]["text"])
        self.assertIn("response_generator_confirmation", result_context["pipeline_history"])

    def test_generate_confirmation_message_uses_recommended_action_metadata(self):
        context = {
            "plan": {
                "action_method": "_apply_code_fix",
                "recommended_action": "apply_code_fix",
                "parameters": {"filename": "src/Calculator.cs"},
                "confirmation_needed": True
            },
            "pipeline_history": []
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("修正案の適用を行います。", result_context["response"]["text"])
        self.assertIn("対象は src/Calculator.cs です。", result_context["response"]["text"])
        self.assertIn("修正案をコードへ反映します。", result_context["response"]["text"])
        self.assertIn("よろしいですか？", result_context["response"]["text"])
        self.assertIn("response_generator_confirmation", result_context["pipeline_history"])
        self.assertEqual(result_context["dialogue_state"], PENDING_CONFIRMATION)

    def test_generate_confirmation_message_maps_apply_code_fix_action_method(self):
        context = {
            "plan": {
                "action_method": "_apply_code_fix",
                "parameters": {"filename": "src/Calculator.cs"},
                "confirmation_needed": True
            },
            "pipeline_history": []
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("修正案の適用を行います。", result_context["response"]["text"])
        self.assertIn("対象は src/Calculator.cs です。", result_context["response"]["text"])
        self.assertIn("修正案をコードへ反映します。", result_context["response"]["text"])

    def test_generate_confirmation_message_unknown_action(self):
        context = {
            "plan": {
                "action_method": "_unknown_action",
                "parameters": {"item": "something"},
                "confirmation_needed": True
            },
            "pipeline_history": []
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertIn("不明な操作 (_unknown_action)します。よろしいですか？", result_context["response"]["text"])
        self.assertIn("response_generator_confirmation", result_context["pipeline_history"])

    def test_generate_compound_overall_approval_message(self):
        context = {
            "pipeline_history": [],
            "task": {
                "name": "BACKUP_AND_DELETE",
                "type": "COMPOUND_TASK",
                "parameters": {
                    "source_filename": {"value": "orig.txt"},
                    "destination_filename": {"value": "backup.txt"}
                },
                "subtasks": [
                    {"name": "FILE_COPY", "parameters": {"source_filename": {"value": "orig.txt"}}},
                    {"name": "FILE_DELETE", "parameters": {"filename": {"value": "orig.txt"}}}
                ],
                "clarification_message": "COMPOUND_TASK_OVERALL_APPROVAL"
            }
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertIn("ファイル 'orig.txt' を 'backup.txt' にバックアップして削除します。よろしいですか？", result_context["response"]["text"])

    def test_generate_compound_subtask_approval_message(self):
        context = {
            "pipeline_history": [],
            "task": {
                "name": "BACKUP_AND_DELETE",
                "type": "COMPOUND_TASK",
                "subtasks": [
                    {"name": "FILE_COPY", "parameters": {"source_filename": {"value": "orig.txt"}}},
                    {"name": "FILE_DELETE", "parameters": {"filename": {"value": "orig.txt"}}}
                ],
                "current_subtask_index": 1, # Index of FILE_DELETE
                "clarification_message": "COMPOUND_TASK_SUBTASK_APPROVAL"
            }
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertIn("複合タスク「BACKUP_AND_DELETE」の次のステップ：サブタスク「FILE_DELETE」を実行します。よろしいですか？", result_context["response"]["text"])

if __name__ == '__main__':
    unittest.main()
