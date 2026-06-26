# -*- coding: utf-8 -*-
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from src.config.config_manager import ConfigManager
from src.design_parser.design_inference import DesignInferenceEngine


class _StubResolver:
    def __init__(self, *args, **kwargs):
        pass


class _ConfigurableResolver:
    def __init__(
        self,
        step_token: str,
        score: float,
        entities=None,
        alt_step_token=None,
        alt_score: float = 0.0,
        intent_hints=None,
    ):
        self.step_token = step_token
        self.score = score
        self.entities = entities or {}
        self.alt_step_token = alt_step_token
        self.alt_score = alt_score
        self.intent_hints = intent_hints or {}

    def infer_step_with_score(self, line, method_name):
        return self.step_token, self.score

    def infer_step_with_score_excluding_intents(self, line, method_name, exclude_intents):
        return self.alt_step_token, self.alt_score

    def get_entities(self, line):
        return self.entities

    def get_intent_hints(self, line):
        return self.intent_hints


class TestDesignInferenceEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.workspace_root = Path(self.temp_dir.name)
        (self.workspace_root / "config").mkdir(parents=True, exist_ok=True)
        (self.workspace_root / "resources").mkdir(parents=True, exist_ok=True)
        (self.workspace_root / "config" / "config.json").write_text("{}", encoding="utf-8")
        (self.workspace_root / "config" / "safety_policy.json").write_text(
            json.dumps({"safe_commands": ["git", "echo", "python", "py"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.workspace_root / "resources" / "entity_schema.json").write_text(
            json.dumps(
                {
                    "entities": [
                        {
                            "name": "User",
                            "keywords": ["ユーザー"],
                            "properties": {
                                "Name": "string",
                                "Price": "decimal",
                                "Id": "int",
                            },
                        },
                        {
                            "name": "Inventory",
                            "keywords": ["在庫"],
                            "properties": {
                                "Id": "int",
                                "Stock": "int",
                            },
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.design_path = self.workspace_root / "Sample.design.md"

    def _write_design(self, body: str) -> None:
        self.design_path.write_text(body, encoding="utf-8")

    def _build_engine(self) -> DesignInferenceEngine:
        config = ConfigManager(workspace_root=str(self.workspace_root))
        with patch("src.design_parser.design_inference.MorphAnalyzer", return_value=object()):
            with patch("src.design_parser.design_inference.DesignOpsResolver", _StubResolver):
                return DesignInferenceEngine(
                    config_manager=config,
                    morph_analyzer=object(),
                )

    def test_infer_then_freeze_writes_inferred_design_without_mutating_original(self):
        original = """# Sample
## Purpose
推論テスト
## Structured Specification
### Input
- **Description**: none
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
1. 入力を整形する
### Test Cases
- **Scenario**: Default
- **Expected**: true
"""
        self._write_design(original)
        engine = self._build_engine()

        def _fake_infer_line(line, step_idx, module_name, last_output_type, **kwargs):
            return (
                True,
                None,
                '1. [ACTION|TRANSFORM|Item|void|NONE] 入力を整形する',
                [],
            )

        engine._infer_line = _fake_infer_line

        result = engine.infer_then_freeze(str(self.design_path))

        self.assertEqual(result["status"], "updated")
        inferred_path = Path(result["output_path"])
        self.assertTrue(inferred_path.exists())
        inferred_text = inferred_path.read_text(encoding="utf-8")
        self.assertIn("### Inference Metadata", inferred_text)
        self.assertIn("[ACTION|TRANSFORM|Item|void|NONE]", inferred_text)
        self.assertEqual(self.design_path.read_text(encoding="utf-8"), original)

    def test_infer_then_freeze_returns_blocked_when_inference_reports_issue(self):
        original = """# Sample
## Purpose
推論テスト
## Structured Specification
### Input
- **Description**: none
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
1. 不足情報のある処理を実行する
### Test Cases
- **Scenario**: Default
- **Expected**: true
"""
        self._write_design(original)
        engine = self._build_engine()

        def _fake_blocked(line, step_idx, module_name, last_output_type, **kwargs):
            from src.design_parser.design_inference import InferenceIssue

            return (
                False,
                InferenceIssue(step_index=1, reason="LOW_CONFIDENCE", detail="score=0.42"),
                line,
                [],
            )

        engine._infer_line = _fake_blocked

        result = engine.infer_then_freeze(str(self.design_path))

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(len(result["issues"]), 1)
        self.assertEqual(result["issues"][0]["reason"], "LOW_CONFIDENCE")
        inferred_path = self.workspace_root / "Sample.inferred.design.md"
        self.assertFalse(inferred_path.exists())

    def test_infer_then_freeze_applies_literal_suggestions_before_inference(self):
        original = """# Sample
## Purpose
推論テスト
## Structured Specification
### Input
- **Description**: none
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
1. 'users.json' を読み込む
2. データをユーザー一覧に変換する
### Test Cases
- **Scenario**: Default
- **Expected**: true
"""
        self._write_design(original)
        engine = self._build_engine()

        def _fake_infer_line(line, step_idx, module_name, last_output_type, **kwargs):
            if step_idx == 1:
                self.assertIn('[semantic_roles:{"path":"users.json"}]', line)
            return (
                True,
                None,
                f"{step_idx}. [ACTION|TRANSFORM|Item|void|NONE] {engine._strip_leading_numbering(line)}",
                [],
            )

        engine._infer_line = _fake_infer_line
        payload = {
            "provider": "openai_compatible_http",
            "model_id": "local-assist",
            "mode": "literal_roles_only",
            "result": {
                "accepted_suggestions": [
                    {
                        "step_number": 1,
                        "semantic_roles": {"path": "users.json"},
                    }
                ]
            },
        }

        result = engine.infer_then_freeze(str(self.design_path), suggestion_payload=payload)

        self.assertEqual(result["status"], "updated")
        inferred_text = Path(result["output_path"]).read_text(encoding="utf-8")
        self.assertIn("llm_literal_assist: true", inferred_text)
        self.assertIn("llm_literal_assist_model_id: local-assist", inferred_text)
        self.assertIn("llm_literal_assist_applied_steps: 1", inferred_text)

    def test_infer_line_adds_path_semantic_role_for_json_deserialize_filename(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token="intent.JSON_DESERIALIZE",
            score=0.95,
            entities={"filename": {"value": "users.json"}},
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "users.json を読み込み、ユーザー一覧に変換する",
            step_idx=1,
            module_name="Sample",
            last_output_type=None,
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|JSON_DESERIALIZE|User|List<User>|NONE]", new_line)
        self.assertIn('[semantic_roles:{"path":"users.json"}]', new_line)

    def test_infer_line_adds_url_semantic_role_for_http_request(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token="intent.HTTP_REQUEST",
            score=0.95,
            entities={"url": {"value": "https://api.example.com/products"}},
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "API 'https://api.example.com/products' からJSON文字列を取得する。",
            step_idx=1,
            module_name="Sample",
            last_output_type=None,
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|HTTP_REQUEST|Item|string|NETWORK]", new_line)
        self.assertIn('[semantic_roles:{"url":"https://api.example.com/products"}]', new_line)

    def test_infer_line_falls_back_to_cmd_run_for_safe_command_literal(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
            entities={"command": {"value": "git status"}},
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "コマンド「git status」を実行する",
            step_idx=1,
            module_name="Sample",
            last_output_type=None,
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|CMD_RUN|string|void|NONE]", new_line)
        self.assertIn('[semantic_roles:{"command":"git status"}]', new_line)

    def test_infer_line_blocks_unsafe_command_literal(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
            entities={"command": {"value": "powershell Remove-Item victim.txt"}},
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "コマンド「powershell Remove-Item victim.txt」を実行する",
            step_idx=1,
            module_name="Sample",
            last_output_type=None,
        )

        self.assertFalse(inferred)
        self.assertIsNotNone(issue)
        self.assertEqual(issue.reason, "UNSAFE_COMMAND")
        self.assertEqual(new_line, "コマンド「powershell Remove-Item victim.txt」を実行する")
        self.assertEqual(data_sources, [])

    def test_infer_line_adds_trim_upper_ops_and_string_output(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token="intent.TRANSFORM",
            score=0.95,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "取得した文字列をトリムし、大文字に変換する",
            step_idx=2,
            module_name="Sample",
            last_output_type="string",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|TRANSFORM|string|string|NONE]", new_line)
        self.assertIn('[semantic_roles:{"ops":["trim_upper"]}]', new_line)

    def test_infer_line_adds_split_lines_ops_and_list_output(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token="intent.TRANSFORM",
            score=0.95,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "CSVを行配列に分割する",
            step_idx=2,
            module_name="Sample",
            last_output_type="string",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|TRANSFORM|string|List<string>|NONE]", new_line)
        self.assertIn('[semantic_roles:{"ops":["split_lines"]}]', new_line)

    def test_infer_line_adds_aggregate_by_product_ops(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token="intent.CALC",
            score=0.95,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "商品別の合計金額を集計する",
            step_idx=4,
            module_name="Sample",
            last_output_type="List<string>",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|CALC|decimal|Dictionary<string, decimal>|NONE]", new_line)
        self.assertIn('[semantic_roles:{"ops":["aggregate_by_product"]}]', new_line)

    def test_collect_data_sources_infers_plain_stdin_source_line(self):
        engine = self._build_engine()

        data_sources = engine._collect_data_sources(["標準入力", "1. 標準入力から1行取得する"])

        self.assertIn("[data_source|STDIN|stdin]", data_sources)

    def test_collect_data_sources_infers_plain_filename_source_line(self):
        engine = self._build_engine()

        data_sources = engine._collect_data_sources(["users.json", "1. 'users.json' を読み込む"])

        self.assertIn("[data_source|users_json|file]", data_sources)

    def test_infer_line_falls_back_to_plain_stdin_fetch(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
        )
        engine._current_data_sources = [{"id": "STDIN", "kind": "stdin", "description": "標準入力"}]

        inferred, issue, new_line, data_sources = engine._infer_line(
            "標準入力から1行取得する",
            step_idx=1,
            module_name="Sample",
            last_output_type=None,
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|FETCH|string|string|IO|STDIN|stdin]", new_line)

    def test_infer_line_falls_back_to_plain_http_request(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
        )
        engine._current_data_sources = [{"id": "product_api", "kind": "http", "description": "Product API Endpoint"}]

        inferred, issue, new_line, data_sources = engine._infer_line(
            "API 'https://api.example.com/products' からJSON文字列を取得する。",
            step_idx=1,
            module_name="Sample",
            last_output_type=None,
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|HTTP_REQUEST|Item|string|NETWORK|product_api|http]", new_line)
        self.assertIn('[semantic_roles:{"url":"https://api.example.com/products"}]', new_line)

    def test_infer_line_preserves_http_source_when_resolver_supplies_http_intent(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token="intent.HTTP_REQUEST",
            score=1.0,
        )
        engine._current_data_sources = [{"id": "product_api", "kind": "http", "description": "Product API Endpoint"}]

        inferred, issue, new_line, data_sources = engine._infer_line(
            "API 'https://api.example.com/products' からJSON文字列を取得する。",
            step_idx=1,
            module_name="Sample",
            last_output_type=None,
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|HTTP_REQUEST|Item|string|NETWORK|product_api|http]", new_line)
        self.assertIn('[semantic_roles:{"url":"https://api.example.com/products"}]', new_line)

    def test_infer_line_falls_back_to_ops_only_transform(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "取得した文字列をトリムし、大文字に変換する",
            step_idx=2,
            module_name="Sample",
            last_output_type="string",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|TRANSFORM|string|string|NONE]", new_line)
        self.assertIn('[semantic_roles:{"ops":["trim_upper"]}]', new_line)

    def test_collect_data_sources_infers_plain_file_source_lines_from_io_names(self):
        engine = self._build_engine()
        engine._current_io_inputs = [
            {"name": "input_path", "format": "string"},
            {"name": "output_path", "format": "string"},
        ]

        data_sources = engine._collect_data_sources(["入力CSV", "出力CSV"])

        self.assertIn("[data_source|input_path|file]", data_sources)
        self.assertIn("[data_source|output_path|file]", data_sources)

    def test_infer_line_prefers_ops_only_calc_when_explicit_op_cue_exists(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token="intent.FILE_IO",
            score=0.95,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "各行の1列目を商品名、2列目を金額として商品別に合計金額を集計する",
            step_idx=4,
            module_name="Sample",
            last_output_type="List<string>",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|CALC|decimal|Dictionary<string, decimal>|NONE]", new_line)
        self.assertIn('[semantic_roles:{"ops":["aggregate_by_product"]}]', new_line)

    def test_infer_line_maps_plain_output_path_phrase_to_file_persist(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token="intent.FETCH",
            score=0.95,
        )
        engine._current_data_sources = [{"id": "output_path", "kind": "file", "description": "出力CSV"}]

        inferred, issue, new_line, data_sources = engine._infer_line(
            "出力ファイルパスにCSVを書き出す",
            step_idx=5,
            module_name="Sample",
            last_output_type="string",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|PERSIST|string|void|IO|output_path|file]", new_line)

    def test_infer_line_overrides_plain_loop_phrase_to_loop_meta(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token="intent.FILE_IO",
            score=0.95,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "CSVの各行を順に処理する",
            step_idx=3,
            module_name="Sample",
            last_output_type="List<string>",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[LOOP|GENERAL|List<string>|void|NONE]", new_line)

    def test_infer_line_overrides_last_return_phrase_to_return_value(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token="intent.FETCH",
            score=0.95,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "出力ファイルパスを返す",
            step_idx=8,
            module_name="Sample",
            last_output_type="string",
            is_last_step=True,
            output_format="string",
            last_persist_path="output_path",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|TRANSFORM|string|string|NONE]", new_line)
        self.assertIn('[semantic_roles:{"return_value":"output_path"}]', new_line)

    def test_infer_line_falls_back_to_plain_file_fetch_with_path_role(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "'users.json' を読み込む",
            step_idx=1,
            module_name="Sample",
            last_output_type=None,
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|FETCH|string|string|IO]", new_line)
        self.assertIn('[semantic_roles:{"path":"users.json"}]', new_line)

    def test_infer_line_falls_back_to_plain_json_deserialize(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "データをユーザーリストに変換する",
            step_idx=2,
            module_name="Sample",
            last_output_type="string",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|JSON_DESERIALIZE|User|List<User>|NONE]", new_line)

    def test_infer_line_falls_back_to_plain_linq_filter(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "名前が 'A' で始まるユーザーを抽出する",
            step_idx=3,
            module_name="Sample",
            last_output_type="List<User>",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|LINQ|User|List<User>|NONE]", new_line)
        self.assertIn('"property":"Name"', new_line)

    def test_infer_line_strips_non_step_metadata_prefixes_for_fallback(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            '1. [refs:step_2] [semantic_roles:{"property":"Price"}] 価格が 500 より大きいユーザーを抽出する',
            step_idx=4,
            module_name="Sample",
            last_output_type="List<User>",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|LINQ|User|List<User>|NONE] [refs:step_3]", new_line)
        self.assertIn('[semantic_roles:{"property":"Price"}]', new_line)
        self.assertNotIn("[refs:step_2] [semantic_roles", new_line)

    def test_infer_line_adds_filter_property_for_price_linq(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token="intent.LINQ",
            score=0.95,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "価格が 500 より大きいユーザーを抽出する",
            step_idx=4,
            module_name="Sample",
            last_output_type="List<User>",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|LINQ|User|List<User>|NONE]", new_line)
        self.assertIn('"property":"Price"', new_line)

    def test_collect_data_sources_infers_plain_http_and_db_source_lines(self):
        engine = self._build_engine()

        data_sources = engine._collect_data_sources(["Product API Endpoint", "Local SQL Database"])

        self.assertIn("[data_source|product_api|http]", data_sources)
        self.assertIn("[data_source|local_db|db]", data_sources)

    def test_infer_line_falls_back_to_plain_db_persist_with_sql(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
        )
        engine._current_data_sources = [{"id": "local_db", "kind": "db", "description": "Local SQL Database"}]

        inferred, issue, new_line, data_sources = engine._infer_line(
            "商品リストの各項目に対し、SQL 'INSERT INTO Products (Name, Price) VALUES (@Name, @Price)' を実行して保存する。",
            step_idx=3,
            module_name="Sample",
            last_output_type="IEnumerable<Product>",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|PERSIST|Item|void|DB|local_db|db]", new_line)
        self.assertIn('"sql":"INSERT INTO Products (Name, Price) VALUES (@Name, @Price)"', new_line)

    def test_infer_line_falls_back_to_plain_db_query_with_existing_sql_role(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
        )
        engine._current_data_sources = [{"id": "inventory_db", "kind": "db", "description": "Inventory Database"}]

        inferred, issue, new_line, data_sources = engine._infer_line(
            '1. [semantic_roles:{"sql":"SELECT * FROM Inventory"}] SQL を実行して在庫情報を取得する',
            step_idx=1,
            module_name="Sample",
            last_output_type=None,
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|DATABASE_QUERY|Inventory|IEnumerable<Inventory>|DB|inventory_db|db]", new_line)
        self.assertIn('[semantic_roles:{"sql":"SELECT * FROM Inventory"}]', new_line)

    def test_infer_line_falls_back_to_file_data_source_fetch(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
        )
        engine._current_data_sources = [{"id": "input_path", "kind": "file", "description": "入力CSV"}]

        inferred, issue, new_line, data_sources = engine._infer_line(
            "入力ファイルパスのCSVを読み込む",
            step_idx=1,
            module_name="Sample",
            last_output_type=None,
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|FETCH|string|string|IO|input_path|file]", new_line)
        self.assertIn('[semantic_roles:{"path":"input_path"}]', new_line)

    def test_infer_line_falls_back_to_file_data_source_persist_with_path_role(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
        )
        engine._current_data_sources = [{"id": "output_path", "kind": "file", "description": "出力CSV"}]

        inferred, issue, new_line, data_sources = engine._infer_line(
            "出力ファイルパスにCSVを書き出す",
            step_idx=7,
            module_name="Sample",
            last_output_type="string",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|PERSIST|string|void|IO|output_path|file]", new_line)
        self.assertIn('[semantic_roles:{"path":"output_path"}]', new_line)

    def test_infer_line_falls_back_to_plain_return_true(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "処理が成功したとして true を返す。",
            step_idx=4,
            module_name="Sample",
            last_output_type="void",
            is_last_step=True,
            output_format="task<bool>",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|RETURN|bool|task<bool>|NONE]", new_line)
        self.assertIn('[semantic_roles:{"return_value":"true"}]', new_line)

    def test_infer_line_plain_display_uses_collection_item_entity(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token=None,
            score=0.0,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "条件に合致したユーザー一覧を表示する",
            step_idx=5,
            module_name="Sample",
            last_output_type="List<User>",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|DISPLAY|User|void|NONE]", new_line)

    def test_infer_line_resolver_display_still_uses_collection_item_entity(self):
        engine = self._build_engine()
        engine.resolver = _ConfigurableResolver(
            step_token="intent.DISPLAY",
            score=1.0,
        )

        inferred, issue, new_line, data_sources = engine._infer_line(
            "条件に合致したユーザー一覧を表示する",
            step_idx=5,
            module_name="Sample",
            last_output_type="List<User>",
        )

        self.assertTrue(inferred)
        self.assertIsNone(issue)
        self.assertEqual(data_sources, [])
        self.assertIn("[ACTION|DISPLAY|User|void|NONE]", new_line)


if __name__ == "__main__":
    unittest.main()
