import json
import os
import subprocess
import sys
import tempfile
import unittest
import hashlib
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np

from src.pipeline_core.pipeline_core import Pipeline


class TestDocumentedEntrypoints(unittest.TestCase):
    def setUp(self):
        self.workspace_root = Path(os.getcwd())
        self.cache_dir = self.workspace_root / "cache"
        self.cache_dir.mkdir(exist_ok=True)

    def _register_http_server_cleanup(self, server, thread):
        def _cleanup():
            server.shutdown()
            thread.join(timeout=1)
            server.server_close()

        self.addCleanup(_cleanup)

    def _make_asset_free_pipeline(self) -> Pipeline:
        intent_cache = self.cache_dir / "intent_vectors.pkl"
        backup_cache = self.cache_dir / "intent_vectors.pkl.integration_backup"
        if backup_cache.exists():
            backup_cache.unlink()
        if intent_cache.exists():
            intent_cache.replace(backup_cache)

            def restore_intent_cache():
                intent_cache.unlink(missing_ok=True)
                if backup_cache.exists():
                    backup_cache.replace(intent_cache)

            self.addCleanup(restore_intent_cache)
        else:
            self.addCleanup(intent_cache.unlink, missing_ok=True)

        class DummyVectorEngine:
            def __init__(self, dim: int = 300):
                self.is_ready = True
                self._dim = dim

            def get_sentence_vector(self, words):
                if not words:
                    return None
                vec = np.zeros(self._dim, dtype=np.float32)
                for word in words:
                    token = str(word)
                    digest = hashlib.sha256(token.encode("utf-8")).digest()
                    idx = int.from_bytes(digest[:4], "little") % self._dim
                    sign = 1.0 if (digest[4] & 1) == 0 else -1.0
                    vec[idx] += sign
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec /= norm
                return vec

            def vector_similarity(self, v1, v2):
                if v1 is None or v2 is None:
                    return 0.0
                return float(np.dot(v1, v2))

        pipeline = Pipeline(is_test_mode=True)
        pipeline._vector_engine = DummyVectorEngine()
        pipeline.action_executor.vector_engine = pipeline._vector_engine
        return pipeline

    def test_readme_generate_from_design_example_runs(self):
        output_path = self.cache_dir / "ReadmeSampleImpact.cs"
        if output_path.exists():
            output_path.unlink()

        command = [
            sys.executable,
            "scripts/generate/generate_from_design.py",
            "--design",
            "scenarios/SampleProject.design.md",
            "--output",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        self.assertTrue(output_path.exists())
        generated_code = output_path.read_text(encoding="utf-8")
        self.assertIn("public partial class GeneratedProcessor", generated_code)
        self.assertIn("SampleProject", generated_code)

    def test_generate_from_design_reports_missing_design_to_stderr(self):
        command = [
            sys.executable,
            "scripts/generate/generate_from_design.py",
            "--design",
            "scenarios/DoesNotExist.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("設計書が見つかりません", completed.stderr)

    def test_generate_from_design_is_deterministic_for_fixed_design(self):
        output_a = self.cache_dir / "DeterminismSampleA.cs"
        output_b = self.cache_dir / "DeterminismSampleB.cs"
        for path in [output_a, output_b]:
            if path.exists():
                path.unlink()

        env = os.environ.copy()
        env["SKIP_VECTOR_MODEL"] = "1"

        for output_path in [output_a, output_b]:
            command = [
                sys.executable,
                "scripts/generate/generate_from_design.py",
                "--design",
                "scenarios/ComplexLinqSearch.design.md",
                "--output",
                str(output_path),
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
            )

        generated_a = output_a.read_text(encoding="utf-8")
        generated_b = output_b.read_text(encoding="utf-8")
        self.assertEqual(generated_a, generated_b)

    def test_strip_design_tags_cli_removes_explicit_bracket_tags_from_core_logic(self):
        input_path = self.cache_dir / "TaggedSample.design.md"
        output_path = self.cache_dir / "TaggedSampleStripped.design.md"
        input_path.write_text(
            "\n".join(
                [
                    "# TaggedSample",
                    "## 1. Purpose",
                    "tag strip",
                    "## 2. Structured Specification",
                    "### Core Logic",
                    "- [data_source|STDIN|stdin] 標準入力",
                    "1. [ACTION|FETCH|string|string|IO|STDIN|stdin] 標準入力から1行取得する",
                    '2. [ACTION|TRANSFORM|string|string|NONE] [ops:trim_upper] [semantic_roles:{"hint":"x"}] 取得した文字列をトリムし、大文字に変換する',
                    "3. [END|GENERAL]",
                    "### Inference Metadata",
                    "- inference_mode: infer_then_freeze",
                    "### Test Cases",
                    "- **Scenario**: Default",
                    "- **Expected**: true",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        command = [
            sys.executable,
            "scripts/strip_design_tags.py",
            "--design",
            str(input_path),
            "--output",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        stripped_text = output_path.read_text(encoding="utf-8")
        self.assertIn("- 標準入力", stripped_text)
        self.assertIn("1. 標準入力から1行取得する", stripped_text)
        self.assertIn("2. 取得した文字列をトリムし、大文字に変換する", stripped_text)
        self.assertNotIn("[ACTION|", stripped_text)
        self.assertNotIn("[ops:", stripped_text)
        self.assertNotIn("[semantic_roles:", stripped_text)
        self.assertNotIn("### Inference Metadata", stripped_text)
        self.assertNotIn("3. [END|GENERAL]", stripped_text)

    def test_generate_from_design_accepts_stripped_stdin_transform_design(self):
        stripped_dir = self.cache_dir / "StdinToStdoutTransformStripped"
        stripped_dir.mkdir(exist_ok=True)
        stripped_design = stripped_dir / "StdinToStdoutTransform.design.md"
        output_path = stripped_dir / "StdinToStdoutTransform.cs"

        strip_command = [
            sys.executable,
            "scripts/strip_design_tags.py",
            "--design",
            "scenarios/StdinToStdoutTransform.design.md",
            "--output",
            str(stripped_design),
        ]
        strip_completed = subprocess.run(
            strip_command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            strip_completed.returncode,
            0,
            msg=f"stdout:\n{strip_completed.stdout}\n\nstderr:\n{strip_completed.stderr}",
        )

        command = [
            sys.executable,
            "scripts/generate/generate_from_design.py",
            "--design",
            str(stripped_design),
            "--output",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        generated_code = output_path.read_text(encoding="utf-8")
        self.assertIn("Console.ReadLine", generated_code)
        self.assertIn("ToUpperInvariant", generated_code)

    def test_generate_from_design_accepts_stripped_csv_aggregation_design(self):
        stripped_dir = self.cache_dir / "CsvSalesAggregationStripped"
        stripped_dir.mkdir(exist_ok=True)
        stripped_design = stripped_dir / "CsvSalesAggregation.design.md"
        output_path = stripped_dir / "CsvSalesAggregation.cs"

        strip_command = [
            sys.executable,
            "scripts/strip_design_tags.py",
            "--design",
            "scenarios/CsvSalesAggregation.design.md",
            "--output",
            str(stripped_design),
        ]
        strip_completed = subprocess.run(
            strip_command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            strip_completed.returncode,
            0,
            msg=f"stdout:\n{strip_completed.stdout}\n\nstderr:\n{strip_completed.stderr}",
        )

        command = [
            sys.executable,
            "scripts/generate/generate_from_design.py",
            "--design",
            str(stripped_design),
            "--output",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        generated_code = output_path.read_text(encoding="utf-8")
        self.assertIn("File.ReadAllText(input_path)", generated_code)
        self.assertIn("Split(new[] { \"\\r\\n\", \"\\n\" }", generated_code)
        self.assertIn("new Dictionary<string, decimal>()", generated_code)
        self.assertIn("File.WriteAllText(output_path, csv)", generated_code)
        self.assertIn("return output_path;", generated_code)

    def test_generate_from_design_accepts_stripped_complex_linq_search_design(self):
        stripped_dir = self.cache_dir / "ComplexLinqSearchStripped"
        stripped_dir.mkdir(exist_ok=True)
        stripped_design = stripped_dir / "ComplexLinqSearch.design.md"
        inferred_design = stripped_dir / "ComplexLinqSearch.inferred.design.md"
        output_path = stripped_dir / "ComplexLinqSearch.cs"

        strip_command = [
            sys.executable,
            "scripts/strip_design_tags.py",
            "--design",
            "scenarios/ComplexLinqSearch.design.md",
            "--output",
            str(stripped_design),
        ]
        strip_completed = subprocess.run(
            strip_command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            strip_completed.returncode,
            0,
            msg=f"stdout:\n{strip_completed.stdout}\n\nstderr:\n{strip_completed.stderr}",
        )

        command = [
            sys.executable,
            "scripts/generate/generate_from_design.py",
            "--design",
            str(stripped_design),
            "--output",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        self.assertTrue(inferred_design.exists())
        inferred_text = inferred_design.read_text(encoding="utf-8")
        self.assertIn('[ACTION|FETCH|string|string|IO] [semantic_roles:{"path":"users.json"}]', inferred_text)
        self.assertIn("[ACTION|JSON_DESERIALIZE|User|List<User>|NONE]", inferred_text)
        self.assertIn("[ACTION|LINQ|User|List<User>|NONE]", inferred_text)
        self.assertIn("[ACTION|DISPLAY|User|void|NONE]", inferred_text)
        generated_code = output_path.read_text(encoding="utf-8")
        self.assertIn('File.ReadAllText("users.json")', generated_code)
        self.assertIn("JsonSerializer.Deserialize<List<User>>(content)", generated_code)
        self.assertIn('item.Name.StartsWith("A")', generated_code)
        self.assertIn("item1.Price > 500m", generated_code)

    def test_generate_from_design_accepts_stripped_sync_external_data_design(self):
        stripped_dir = self.cache_dir / "SyncExternalDataStripped"
        stripped_dir.mkdir(exist_ok=True)
        stripped_design = stripped_dir / "SyncExternalData.design.md"
        inferred_design = stripped_dir / "SyncExternalData.inferred.design.md"
        output_path = stripped_dir / "SyncExternalData.cs"

        strip_command = [
            sys.executable,
            "scripts/strip_design_tags.py",
            "--design",
            "scenarios/SyncExternalData.design.md",
            "--output",
            str(stripped_design),
        ]
        strip_completed = subprocess.run(
            strip_command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            strip_completed.returncode,
            0,
            msg=f"stdout:\n{strip_completed.stdout}\n\nstderr:\n{strip_completed.stderr}",
        )

        command = [
            sys.executable,
            "scripts/generate/generate_from_design.py",
            "--design",
            str(stripped_design),
            "--output",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        self.assertTrue(inferred_design.exists())
        inferred_text = inferred_design.read_text(encoding="utf-8")
        self.assertIn("[data_source|product_api|http]", inferred_text)
        self.assertIn("[data_source|local_db|db]", inferred_text)
        self.assertIn("Product API Endpoint", inferred_text)
        self.assertIn("Local SQL Database", inferred_text)
        self.assertIn('[semantic_roles:{"url":"https://api.example.com/products"}]', inferred_text)
        self.assertIn('[semantic_roles:{"sql":"INSERT INTO Products (Name, Price) VALUES (@Name, @Price)"}]', inferred_text)
        self.assertIn('[semantic_roles:{"return_value":"true"}]', inferred_text)
        generated_code = output_path.read_text(encoding="utf-8")
        self.assertIn('_httpClient.GetStringAsync("https://api.example.com/products")', generated_code)
        self.assertIn("JsonSerializer.Deserialize<List<Product>>(product)", generated_code)
        self.assertIn('_dbConnection.ExecuteAsync("INSERT INTO Products (Name, Price) VALUES (@Name, @Price)", items)', generated_code)
        self.assertIn("return true;", generated_code)

    def test_generate_from_design_accepts_literal_tag_assistance_http_mode(self):
        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                response = {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "suggestions": [
                                            {
                                                "step_number": 1,
                                                "semantic_roles": {"path": "users.json"},
                                            }
                                        ]
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ]
                }
                encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format, *args):
                return

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._register_http_server_cleanup(server, thread)

        stripped_dir = self.cache_dir / "ComplexLinqSearchAssist"
        stripped_dir.mkdir(exist_ok=True)
        stripped_design = stripped_dir / "ComplexLinqSearch.design.md"
        inferred_design = stripped_dir / "ComplexLinqSearch.inferred.design.md"
        output_path = stripped_dir / "ComplexLinqSearch.cs"

        strip_command = [
            sys.executable,
            "scripts/strip_design_tags.py",
            "--design",
            "scenarios/ComplexLinqSearch.design.md",
            "--output",
            str(stripped_design),
        ]
        strip_completed = subprocess.run(
            strip_command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            strip_completed.returncode,
            0,
            msg=f"stdout:\n{strip_completed.stdout}\n\nstderr:\n{strip_completed.stderr}",
        )

        command = [
            sys.executable,
            "scripts/generate/generate_from_design.py",
            "--design",
            str(stripped_design),
            "--output",
            str(output_path),
            "--assist-literal-tags-http",
            "--assist-endpoint-url",
            f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            "--assist-policy",
            "always",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        self.assertTrue(inferred_design.exists())
        inferred_text = inferred_design.read_text(encoding="utf-8")
        self.assertIn("llm_literal_assist: true", inferred_text)
        self.assertIn("llm_literal_assist_model_id: local-assist", inferred_text)
        self.assertIn("llm_literal_assist_applied_steps: 1", inferred_text)
        self.assertEqual(completed.stderr.strip(), "")

    def test_generate_from_design_skips_literal_tag_assistance_when_not_blocked(self):
        hit_counter = {"count": 0}

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                hit_counter["count"] += 1
                response = {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps({"suggestions": []}, ensure_ascii=False)
                            }
                        }
                    ]
                }
                encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format, *args):
                return

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._register_http_server_cleanup(server, thread)

        output_path = self.cache_dir / "StdinToStdoutTransformDirect.cs"
        if output_path.exists():
            output_path.unlink()

        command = [
            sys.executable,
            "scripts/generate/generate_from_design.py",
            "--design",
            "scenarios/StdinToStdoutTransform.design.md",
            "--output",
            str(output_path),
            "--assist-literal-tags-http",
            "--assist-endpoint-url",
            f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        self.assertEqual(hit_counter["count"], 0)
        self.assertTrue(output_path.exists())
        self.assertEqual(completed.stderr.strip(), "")

    def test_probe_design_inference_boundary_reports_literal_loss_boundary(self):
        command = [
            sys.executable,
            "scripts/probe_design_inference_boundary.py",
            "--design",
            "scenarios/ComplexLinqSearch.design.md",
            "--variants",
            "original",
            "strip_tags",
            "strip_tags_drop_literals",
            "--generate-variants",
            "original",
            "strip_tags",
            "--output-dir",
            str(self.cache_dir / "probe_boundary_complex"),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        variants = {entry["variant"]: entry for entry in payload["variants"]}
        self.assertTrue(variants["original"]["clean_generate"])
        self.assertTrue(variants["strip_tags"]["clean_generate"])
        self.assertEqual(variants["strip_tags_drop_literals"]["inference_status"], "blocked")
        self.assertFalse(variants["strip_tags_drop_literals"]["clean_generate"])
        self.assertTrue(variants["strip_tags_drop_literals"]["generation_skipped"])
        self.assertIn("NO_CANDIDATE", json.dumps(variants["strip_tags_drop_literals"]["issues"], ensure_ascii=False))
        self.assertEqual(completed.stderr.strip(), "")

    def test_probe_design_inference_boundary_reports_sync_http_boundary(self):
        command = [
            sys.executable,
            "scripts/probe_design_inference_boundary.py",
            "--design",
            "scenarios/SyncExternalData.design.md",
            "--variants",
            "original",
            "strip_tags",
            "strip_tags_drop_literals",
            "--generate-variants",
            "original",
            "strip_tags",
            "--output-dir",
            str(self.cache_dir / "probe_boundary_sync_http"),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        variants = {entry["variant"]: entry for entry in payload["variants"]}
        self.assertTrue(variants["original"]["clean_generate"])
        self.assertTrue(variants["strip_tags"]["clean_generate"])
        self.assertEqual(variants["strip_tags"]["inference_status"], "updated")
        self.assertFalse(variants["strip_tags_drop_literals"]["clean_generate"])
        self.assertTrue(variants["strip_tags_drop_literals"]["generation_skipped"])
        self.assertEqual(variants["strip_tags_drop_literals"]["inference_status"], "blocked")
        self.assertIn("NO_CANDIDATE", json.dumps(variants["strip_tags_drop_literals"]["issues"], ensure_ascii=False))
        self.assertEqual(completed.stderr.strip(), "")

    def test_audit_literal_tag_assist_coverage_writes_json_result_to_stdout(self):
        scenarios_dir = self.cache_dir / "literal_assist_audit_scenarios"
        scenarios_dir.mkdir(exist_ok=True)
        (scenarios_dir / "BlockedLiteral.design.md").write_text(
            "\n".join(
                [
                    "# BlockedLiteral",
                    "## Purpose",
                    "sql literal candidate without source",
                    "## Structured Specification",
                    "### Input",
                    "- **Description**: none",
                    "- **Type/Format**: void",
                    "### Output",
                    "- **Description**: status",
                    "- **Type/Format**: bool",
                    "### Core Logic",
                    "1. SQL 'SELECT * FROM Users' を実行してユーザー情報を取得する。",
                    "2. ユーザー一覧を表示する。",
                    "### Test Cases",
                    "- **Scenario**: Default",
                    "- **Expected**: true",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (scenarios_dir / "DeterministicOk.design.md").write_text(
            "\n".join(
                [
                    "# DeterministicOk",
                    "## Purpose",
                    "stdin flow",
                    "## Structured Specification",
                    "### Input",
                    "- **Description**: none",
                    "- **Type/Format**: void",
                    "### Output",
                    "- **Description**: status",
                    "- **Type/Format**: bool",
                    "### Core Logic",
                    "- 標準入力",
                    "1. 標準入力から1行取得する",
                    "2. 取得した文字列をトリムし、大文字に変換する",
                    "### Test Cases",
                    "- **Scenario**: Default",
                    "- **Expected**: true",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        command = [
            sys.executable,
            "scripts/audit_literal_tag_assist_coverage.py",
            "--scenarios-dir",
            str(scenarios_dir),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["summary"]["total_designs"], 2)
        self.assertEqual(payload["summary"]["blocked_no_candidate"], 1)
        self.assertEqual(payload["summary"]["assist_recommended"], 1)
        blocked = next(item for item in payload["results"] if item["design"].endswith("BlockedLiteral.design.md"))
        self.assertTrue(blocked["blocked_no_candidate"])
        self.assertTrue(blocked["assist_recommended"])
        self.assertGreaterEqual(blocked["candidate_count"], 1)
        self.assertEqual(completed.stderr.strip(), "")

    def test_readme_pipeline_example_returns_current_directory(self):
        pipeline = self._make_asset_free_pipeline()
        result = pipeline.run("カレントディレクトリを教えて")

        self.assertEqual(result.get("analysis", {}).get("intent"), "GET_CWD")
        response_text = result.get("response", {}).get("text", "")
        self.assertIn("現在の作業ディレクトリ", response_text)
        self.assertIn(str(self.workspace_root), response_text)

    def test_get_cwd_variants_remain_actionable(self):
        phrases = [
            "現在のディレクトリを教えて",
            "今の作業ディレクトリを教えて",
            "作業フォルダを表示して",
            "今いるフォルダを教えて",
        ]
        pipeline = self._make_asset_free_pipeline()

        for phrase in phrases:
            with self.subTest(phrase=phrase):
                result = pipeline.run(phrase)
                self.assertEqual(result.get("analysis", {}).get("intent"), "GET_CWD")
                response_text = result.get("response", {}).get("text", "")
                self.assertIn("現在の作業ディレクトリ", response_text)
                self.assertIn(str(self.workspace_root), response_text)

    def test_list_dir_variants_remain_actionable(self):
        phrases = [
            "ファイル一覧を見せて",
            "作業フォルダの中身を表示して",
            "このフォルダに何がある？",
            "今いるディレクトリの一覧を見せて",
        ]
        pipeline = self._make_asset_free_pipeline()

        for phrase in phrases:
            with self.subTest(phrase=phrase):
                result = pipeline.run(phrase)
                self.assertEqual(result.get("analysis", {}).get("intent"), "LIST_DIR")
                response_text = result.get("response", {}).get("text", "")
                self.assertIn("ディレクトリ", response_text)
                self.assertIn("の内容", response_text)

    def test_readme_run_tdd_example_accepts_test_failure_json(self):
        payload = {
            "test_file": "tests/CalculatorTests.cs",
            "test_method": "Add_ShouldReturnSum_WhenValidInput",
            "error_type": "assertion_failure",
            "error_message": "Expected: 5, Actual: 0",
            "stack_trace": "at Calculator.Add(Int32 a, Int32 b) in Calculator.cs:line 15",
            "line_number": 15,
            "target_code": {
                "file": "src/Calculator.cs",
                "method": "Add",
                "current_implementation": "public int Add(int a, int b) { return 0; }",
            },
        }

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            dir=self.cache_dir,
            delete=False,
        ) as temp_file:
            json.dump(payload, temp_file, ensure_ascii=False)
            temp_path = Path(temp_file.name)

        try:
            command = [
                sys.executable,
                "scripts/validate/run_tdd.py",
                "--test-failure",
                str(temp_path),
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
            )
            result = json.loads(completed.stdout)
            self.assertEqual(result.get("status"), "success")
            self.assertEqual(result.get("analysis", {}).get("status"), "success")
            self.assertTrue(result.get("fix_suggestions"))
        finally:
            temp_path.unlink(missing_ok=True)

    def test_run_tdd_cli_reports_missing_json_to_stderr(self):
        command = [
            sys.executable,
            "scripts/validate/run_tdd.py",
            "--test-failure",
            str(self.cache_dir / "missing_payload.json"),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("入力JSONが見つかりません", completed.stderr)

    def test_run_tdd_cli_reports_invalid_json_to_stderr(self):
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            dir=self.cache_dir,
            delete=False,
        ) as temp_file:
            temp_file.write("{ invalid json")
            temp_path = Path(temp_file.name)

        try:
            command = [
                sys.executable,
                "scripts/validate/run_tdd.py",
                "--test-failure",
                str(temp_path),
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertEqual(completed.stdout.strip(), "")
            self.assertIn("入力JSONの形式が不正です", completed.stderr)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_convert_vectors_reports_missing_input_to_stderr(self):
        command = [
            sys.executable,
            "scripts/data/convert_vectors.py",
            "--input",
            str(self.cache_dir / "missing_vectors.txt"),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("ベクトル入力ファイルが見つかりません", completed.stderr)

    def test_parse_jmdict_reports_missing_xml_to_stderr(self):
        xml_path = self.workspace_root / "resources" / "JMdict_e.xml"
        temp_backup = None
        if xml_path.exists():
            temp_backup = self.cache_dir / "JMdict_e.xml.backup_for_test"
            if temp_backup.exists():
                temp_backup.unlink()
            xml_path.replace(temp_backup)

        try:
            command = [
                sys.executable,
                "scripts/data/parse_jmdict.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertEqual(completed.stdout.strip(), "")
            self.assertIn("JMdict XML が見つかりません", completed.stderr)
        finally:
            if temp_backup and temp_backup.exists():
                temp_backup.replace(xml_path)

    def test_fetch_jmdict_reports_download_failure_to_stderr(self):
        command = [
            sys.executable,
            "scripts/data/fetch_jmdict.py",
        ]
        env = os.environ.copy()
        env["JMDICT_URL_OVERRIDE"] = "file:///definitely/missing/JMdict_e.gz"
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Downloading JMdict from", completed.stdout)
        self.assertIn("JMdict のダウンロードまたは展開に失敗しました", completed.stderr)

    def test_fetch_vectors_reports_download_failure_to_stderr(self):
        command = [
            sys.executable,
            "scripts/data/fetch_vectors.py",
        ]
        env = os.environ.copy()
        env["VECTOR_URL_OVERRIDE"] = "file:///definitely/missing/chive-1.3-mc90.tar.gz"
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Downloading vectors from", completed.stdout)
        self.assertIn("ベクトルのダウンロードまたは展開に失敗しました", completed.stderr)

    def test_build_knowledge_base_warns_to_stderr_when_dictionary_db_is_missing(self):
        db_path = self.workspace_root / "resources" / "dictionary.db"
        kb_path = self.workspace_root / "resources" / "custom_knowledge.json"
        db_backup = None
        kb_backup = None

        if db_path.exists():
            db_backup = self.cache_dir / "dictionary.db.backup_for_test"
            if db_backup.exists():
                db_backup.unlink()
            db_path.replace(db_backup)

        if kb_path.exists():
            kb_backup = self.cache_dir / "custom_knowledge.json.backup_for_test"
            if kb_backup.exists():
                kb_backup.unlink()
            kb_path.replace(kb_backup)

        try:
            command = [
                sys.executable,
                "scripts/data/build_knowledge_base.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0)
            self.assertIn("Custom Knowledge Base Maintenance", completed.stdout)
            self.assertIn("Successfully maintained custom knowledge base", completed.stdout)
            self.assertIn("辞書 DB が見つかりません", completed.stderr)
        finally:
            if kb_backup and kb_backup.exists():
                kb_backup.replace(kb_path)
            if db_backup and db_backup.exists():
                db_backup.replace(db_path)

    def test_sync_project_map_reports_missing_map_to_stderr(self):
        map_path = self.workspace_root / "ai_project_map.json"
        backup_path = self.cache_dir / "ai_project_map.json.backup_for_test"
        if backup_path.exists():
            backup_path.unlink()
        map_path.replace(backup_path)

        try:
            command = [
                sys.executable,
                "scripts/sync_project_map.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("Synchronizing 'ai_project_map.json'...", completed.stdout)
            self.assertIn("ai_project_map.json が見つかりません", completed.stderr)
        finally:
            if backup_path.exists():
                backup_path.replace(map_path)

    def test_validate_project_consistency_success_uses_stdout(self):
        command = [
            sys.executable,
            "scripts/validate_project_consistency.py",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("--- Project Consistency Validation ---", completed.stdout)
        self.assertNotIn("ERRORS (must be fixed):", completed.stderr)

    def test_validate_project_consistency_returns_zero_when_only_warnings_exist(self):
        source_path = self.workspace_root / "src" / "advanced_tdd" / "knowledge_base.py"
        original_text = source_path.read_text(encoding="utf-8")
        try:
            source_path.write_text(original_text + "\n# warning-only regression\n", encoding="utf-8")
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
            )
            self.assertIn("WARNINGS (should be reviewed):", completed.stderr)
            self.assertIn("[module:advanced_tdd]: Source files are newer than design documents.", completed.stderr)
        finally:
            source_path.write_text(original_text, encoding="utf-8")

    def test_validate_project_consistency_reports_missing_map_to_stderr(self):
        map_path = self.workspace_root / "ai_project_map.json"
        backup_path = self.cache_dir / "ai_project_map.validate.backup_for_test"
        if backup_path.exists():
            backup_path.unlink()
        map_path.replace(backup_path)

        try:
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("--- Project Consistency Validation ---", completed.stdout)
            self.assertIn("Error loading", completed.stderr)
            self.assertIn("ERRORS (must be fixed):", completed.stderr)
            self.assertIn("GENERAL:", completed.stderr)
        finally:
            if backup_path.exists():
                backup_path.replace(map_path)

    def test_validate_project_consistency_reports_missing_mapped_design_doc_to_stderr(self):
        map_path = self.workspace_root / "ai_project_map.json"
        original = json.loads(map_path.read_text(encoding="utf-8"))
        mutated = json.loads(map_path.read_text(encoding="utf-8"))

        target_module = next(
            module for module in mutated.get("modules", [])
            if module.get("name") == "action_executor"
        )
        target_module["design_document"]["path"] = "src\\action_executor\\missing_action_executor.design.md"

        try:
            map_path.write_text(json.dumps(mutated, ensure_ascii=False, indent=2), encoding="utf-8")
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("--- Project Consistency Validation ---", completed.stdout)
            self.assertIn("ai_project_map.json の design_document.path が存在しません", completed.stderr)
            self.assertIn("missing_action_executor.design.md", completed.stderr)
        finally:
            map_path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_validate_project_consistency_reports_missing_readme_local_reference_to_stderr(self):
        readme_path = self.workspace_root / "README.md"
        original = readme_path.read_text(encoding="utf-8")
        mutated = (
            original
            + "\n\n<!-- validator regression -->\n"
            + "[broken doc](docs/does_not_exist_for_validator.md)\n"
        )

        try:
            readme_path.write_text(mutated, encoding="utf-8")
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("--- Project Consistency Validation ---", completed.stdout)
            self.assertIn("DOCS (required):", completed.stderr)
            self.assertIn("[doc:README.md][mode:required]: ローカル参照が存在しません", completed.stderr)
            self.assertIn("docs/does_not_exist_for_validator.md", completed.stderr)
        finally:
            readme_path.write_text(original, encoding="utf-8")

    def test_validate_project_consistency_allows_missing_temporary_plan_doc(self):
        plan_path = self.workspace_root / "docs" / "README実装ギャップ段階改善計画.md"
        backup_path = self.cache_dir / "README実装ギャップ段階改善計画.md.backup_for_test"
        if backup_path.exists():
            backup_path.unlink()
        self.assertTrue(plan_path.exists(), msg=f"missing fixture: {plan_path}")
        plan_path.replace(backup_path)

        try:
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
            )
            self.assertNotIn("README実装ギャップ段階改善計画.md", completed.stderr)
        finally:
            if backup_path.exists():
                backup_path.replace(plan_path)

    def test_validate_project_consistency_uses_configured_required_docs(self):
        policy_path = self.workspace_root / "config" / "doc_reference_policy.json"
        original = json.loads(policy_path.read_text(encoding="utf-8"))
        mutated = json.loads(policy_path.read_text(encoding="utf-8"))
        mutated["required_docs"] = ["README.md", "docs/README実装ギャップ段階改善計画.md"]

        plan_path = self.workspace_root / "docs" / "README実装ギャップ段階改善計画.md"
        backup_path = self.cache_dir / "README実装ギャップ段階改善計画.md.policy.backup_for_test"
        if backup_path.exists():
            backup_path.unlink()

        try:
            policy_path.write_text(json.dumps(mutated, ensure_ascii=False, indent=2), encoding="utf-8")
            self.assertTrue(plan_path.exists(), msg=f"missing fixture: {plan_path}")
            plan_path.replace(backup_path)
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("README実装ギャップ段階改善計画.md", completed.stderr)
            self.assertIn("検証対象ドキュメントが存在しません", completed.stderr)
            self.assertIn("[mode:required]", completed.stderr)
        finally:
            if backup_path.exists():
                backup_path.replace(plan_path)
            policy_path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_validate_project_consistency_reports_invalid_doc_reference_policy_to_stderr(self):
        policy_path = self.workspace_root / "config" / "doc_reference_policy.json"
        original = policy_path.read_text(encoding="utf-8")
        mutated = {
            "required_docs": "README.md",
            "optional_reference_docs": ["docs/README実装ギャップ段階改善計画.md"],
        }

        try:
            policy_path.write_text(json.dumps(mutated, ensure_ascii=False, indent=2), encoding="utf-8")
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("--- Project Consistency Validation ---", completed.stdout)
            self.assertIn("Invalid document reference policy", completed.stderr)
            self.assertIn("'required_docs' must be a list of non-empty strings", completed.stderr)
        finally:
            policy_path.write_text(original, encoding="utf-8")

    def test_validate_project_consistency_reports_broken_optional_reference_doc_link(self):
        doc_path = self.workspace_root / "docs" / "README実装ギャップ段階改善計画.md"
        original = doc_path.read_text(encoding="utf-8")
        mutated = (
            original
            + "\n\n<!-- optional doc validator regression -->\n"
            + "[broken optional doc link](docs/not_there_for_optional_doc_check.md)\n"
        )

        try:
            doc_path.write_text(mutated, encoding="utf-8")
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("--- Project Consistency Validation ---", completed.stdout)
            self.assertIn("DOCS (optional-reference):", completed.stderr)
            self.assertIn("[doc:docs/README実装ギャップ段階改善計画.md][mode:optional-reference]: ローカル参照が存在しません", completed.stderr)
            self.assertIn("docs/not_there_for_optional_doc_check.md", completed.stderr)
        finally:
            doc_path.write_text(original, encoding="utf-8")

    def test_validate_project_consistency_reports_missing_required_project_overview_doc(self):
        doc_path = self.workspace_root / "docs" / "project_overview.md"
        backup_path = self.cache_dir / "project_overview.md.backup_for_test"
        if backup_path.exists():
            backup_path.unlink()
        self.assertTrue(doc_path.exists(), msg=f"missing fixture: {doc_path}")
        doc_path.replace(backup_path)

        try:
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("--- Project Consistency Validation ---", completed.stdout)
            self.assertIn("DOCS (required):", completed.stderr)
            self.assertIn("[doc:docs/project_overview.md][mode:required]: 検証対象ドキュメントが存在しません", completed.stderr)
        finally:
            if backup_path.exists():
                backup_path.replace(doc_path)

    def test_validate_project_consistency_reports_missing_required_config_readme_doc(self):
        doc_path = self.workspace_root / "config" / "README.md"
        backup_path = self.cache_dir / "config_README.md.backup_for_test"
        if backup_path.exists():
            backup_path.unlink()
        self.assertTrue(doc_path.exists(), msg=f"missing fixture: {doc_path}")
        doc_path.replace(backup_path)

        try:
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("--- Project Consistency Validation ---", completed.stdout)
            self.assertIn("[doc:config/README.md][mode:required]: 検証対象ドキュメントが存在しません", completed.stderr)
        finally:
            if backup_path.exists():
                backup_path.replace(doc_path)

    def test_validate_project_consistency_reports_missing_existence_only_resources_readme_doc(self):
        doc_path = self.workspace_root / "resources" / "README.md"
        backup_path = self.cache_dir / "resources_README.md.backup_for_test"
        if backup_path.exists():
            backup_path.unlink()
        self.assertTrue(doc_path.exists(), msg=f"missing fixture: {doc_path}")
        doc_path.replace(backup_path)

        try:
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("--- Project Consistency Validation ---", completed.stdout)
            self.assertIn("DOCS (existence-only):", completed.stderr)
            self.assertIn("[doc:resources/README.md][mode:existence-only]: 検証対象ドキュメントが存在しません", completed.stderr)
        finally:
            if backup_path.exists():
                backup_path.replace(doc_path)

    def test_validate_project_consistency_ignores_inventory_entries_in_resources_readme(self):
        doc_path = self.workspace_root / "resources" / "README.md"
        original = doc_path.read_text(encoding="utf-8")
        mutated = original + "\n- `this_file_does_not_exist.anything`\n"

        try:
            doc_path.write_text(mutated, encoding="utf-8")
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
            )
            self.assertNotIn("resources/README.md", completed.stderr)
        finally:
            doc_path.write_text(original, encoding="utf-8")

    def test_validate_project_consistency_reports_unknown_intent_in_intent_corpus(self):
        corpus_path = self.workspace_root / "resources" / "intent_corpus.json"
        original = json.loads(corpus_path.read_text(encoding="utf-8"))
        mutated = json.loads(corpus_path.read_text(encoding="utf-8"))
        mutated["intents"][0]["name"] = "UNKNOWN_VALIDATOR_INTENT"

        try:
            corpus_path.write_text(json.dumps(mutated, ensure_ascii=False, indent=2), encoding="utf-8")
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("intent_corpus.json:intents[0].name", completed.stderr)
            self.assertIn("UNKNOWN_VALIDATOR_INTENT", completed.stderr)
        finally:
            corpus_path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_validate_project_consistency_reports_unknown_subtask_intent_in_task_definitions(self):
        definitions_path = self.workspace_root / "resources" / "task_definitions.json"
        original = json.loads(definitions_path.read_text(encoding="utf-8"))
        mutated = json.loads(definitions_path.read_text(encoding="utf-8"))
        mutated["BACKUP_AND_DELETE"]["subtasks"][0]["name"] = "UNKNOWN_SUBTASK_INTENT"

        try:
            definitions_path.write_text(json.dumps(mutated, ensure_ascii=False, indent=2), encoding="utf-8")
            command = [
                sys.executable,
                "scripts/validate_project_consistency.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("task_definitions.json:BACKUP_AND_DELETE.subtasks[0].name", completed.stderr)
            self.assertIn("UNKNOWN_SUBTASK_INTENT", completed.stderr)
        finally:
            definitions_path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_sync_project_dependencies_warns_to_stderr_for_invalid_csproj(self):
        with tempfile.TemporaryDirectory(dir=self.cache_dir) as temp_root_str:
            temp_root = Path(temp_root_str)
            project_dir = temp_root / "src"
            project_dir.mkdir(parents=True, exist_ok=True)
            invalid_csproj = project_dir / "Broken.csproj"
            invalid_csproj.write_text("<Project><ItemGroup><PackageReference", encoding="utf-8")

            command = [
                sys.executable,
                "scripts/sync/sync_project_dependencies.py",
                "--root",
                str(temp_root),
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            output_path = temp_root / "config" / "current_project_context.json"
            self.assertEqual(completed.returncode, 0)
            self.assertTrue(output_path.exists())
            self.assertIn("Project context synced to", completed.stdout)
            self.assertIn("csproj の解析に失敗しました", completed.stderr)

    def test_validate_method_store_reports_missing_store_to_stderr(self):
        store_path = self.workspace_root / "resources" / "method_store.json"
        backup_path = self.cache_dir / "method_store.json.backup_for_test"
        if backup_path.exists():
            backup_path.unlink()
        store_path.replace(backup_path)

        try:
            command = [
                sys.executable,
                "scripts/validate/validate_method_store.py",
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertEqual(completed.stdout.strip(), "")
            self.assertIn("Method store validation failed:", completed.stderr)
            self.assertIn("Missing file", completed.stderr)
        finally:
            if backup_path.exists():
                backup_path.replace(store_path)

    def test_prune_backups_reports_missing_backup_dir_to_stderr(self):
        with tempfile.TemporaryDirectory(dir=self.cache_dir) as temp_root_str:
            temp_root = Path(temp_root_str)
            command = [
                sys.executable,
                "scripts/tools/prune_backups.py",
                "--root",
                str(temp_root),
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertEqual(completed.stdout.strip(), "")
            self.assertIn("backup ディレクトリが見つかりません", completed.stderr)

    def test_run_unit_smoke_reports_failed_suite_to_stderr(self):
        command = [
            sys.executable,
            "scripts/validate/run_unit_smoke.py",
            "--test-target",
            "tests.unit.this_module_does_not_exist",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("FAILED", completed.stderr)

    def test_run_unit_smoke_default_suite_writes_success_to_stdout(self):
        command = [
            sys.executable,
            "scripts/validate/run_unit_smoke.py",
            "--verbosity",
            "2",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        self.assertIn("tests.unit.test_config_manager.TestConfigManager.test_load_valid_config", completed.stdout)
        self.assertIn("tests.unit.test_code_synthesizer_integration", completed.stdout)
        self.assertNotIn("tests.unit.test_vector_cache_required", completed.stdout)
        self.assertIn("OK", completed.stdout)
        self.assertEqual(completed.stderr.strip(), "")

    def test_run_unit_smoke_parser_profile_writes_success_to_stdout(self):
        command = [
            sys.executable,
            "scripts/validate/run_unit_smoke.py",
            "--profile",
            "parser",
            "--verbosity",
            "2",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        self.assertIn("tests.unit.test_design_doc_parser.TestDesignDocParser.test_parse_content_basic", completed.stdout)
        self.assertIn("tests.unit.test_json_deserialize_guard.TestJsonDeserializeGuard.test_json_deserialize_is_wrapped_with_try_catch", completed.stdout)
        self.assertNotIn("tests.unit.test_code_synthesizer_integration", completed.stdout)
        self.assertIn("OK", completed.stdout)
        self.assertEqual(completed.stderr.strip(), "")

    def test_validate_ir_regression_reports_validation_issues_to_stderr(self):
        command = [
            sys.executable,
            "scripts/validate/validate_ir_meaning_preservation_regression.py",
            "--run-file",
            "research/ir_meaning_preservation/results/regression_run_2026_05_07_metadata_baseline.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("--- IR Meaning Preservation Regression Validation ---", completed.stdout)
        self.assertIn("ERRORS (must be fixed):", completed.stderr)
        self.assertIn("Required asset is missing", completed.stderr)

    def test_validate_ir_regression_reports_missing_run_file_to_stderr(self):
        command = [
            sys.executable,
            "scripts/validate/validate_ir_meaning_preservation_regression.py",
            "--run-file",
            "research/ir_meaning_preservation/results/does_not_exist.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("Run file not found", completed.stderr)

    def test_run_ir_regression_reports_missing_run_file_to_stderr(self):
        command = [
            sys.executable,
            "scripts/validate/run_ir_meaning_preservation_regression.py",
            "--run-file",
            "research/ir_meaning_preservation/results/does_not_exist.md",
            "--test-suite",
            "none",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("Run file not found", completed.stderr)

    def test_generate_ir_case_summary_reports_missing_cases_dir_to_stderr(self):
        missing_dir = self.cache_dir / "missing_case_dir"
        output_path = self.cache_dir / "case_summary_table.md"
        command = [
            sys.executable,
            "scripts/generate_ir_case_summary.py",
            "--cases-dir",
            str(missing_dir),
            "--output",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("ケースディレクトリが見つかりません", completed.stderr)

    def test_generate_ir_case_summary_writes_summary_to_stdout_on_success(self):
        with tempfile.TemporaryDirectory(dir=self.cache_dir) as temp_root_str:
            temp_root = Path(temp_root_str)
            cases_dir = temp_root / "cases"
            cases_dir.mkdir(parents=True, exist_ok=True)
            (cases_dir / "case_01.md").write_text(
                "# Case 01: Demo\n\n- Benchmark role: role-a\n- Primary: fail-a\n- Secondary: fail-b\n",
                encoding="utf-8",
            )
            output_path = temp_root / "out" / "summary.md"
            command = [
                sys.executable,
                "scripts/generate_ir_case_summary.py",
                "--cases-dir",
                str(cases_dir),
                "--output",
                str(output_path),
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0)
            self.assertIn("Summary generated at:", completed.stdout)
            self.assertEqual(completed.stderr.strip(), "")
            self.assertTrue(output_path.exists())

    def test_suggest_method_capabilities_reports_missing_store_to_stderr(self):
        with tempfile.TemporaryDirectory(dir=self.cache_dir) as temp_root_str:
            temp_root = Path(temp_root_str)
            command = [
                sys.executable,
                "scripts/tools/suggest_method_capabilities.py",
                "--root",
                str(temp_root),
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertEqual(completed.stdout.strip(), "")
            self.assertIn("method_store.json が見つかりません", completed.stderr)

    def test_manage_vector_db_reports_missing_analysis_path_to_stderr(self):
        with tempfile.TemporaryDirectory(dir=self.cache_dir) as temp_root_str:
            temp_root = Path(temp_root_str)
            command = [
                sys.executable,
                "scripts/tools/manage_vector_db.py",
                "harvest",
                "--root",
                str(temp_root),
            ]
            env = os.environ.copy()
            env["SKIP_VECTOR_MODEL"] = "1"
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("--- Harvesting from Analysis ---", completed.stdout)
            self.assertIn("analysis_output が見つかりません", completed.stderr)

    def test_manage_vector_db_seed_writes_status_to_stdout(self):
        with tempfile.TemporaryDirectory(dir=self.cache_dir) as temp_root_str:
            temp_root = Path(temp_root_str)
            command = [
                sys.executable,
                "scripts/tools/manage_vector_db.py",
                "seed",
                "--root",
                str(temp_root),
            ]
            env = os.environ.copy()
            env["SKIP_VECTOR_MODEL"] = "1"
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            store_path = temp_root / "resources" / "method_store.json"
            self.assertEqual(
                completed.returncode,
                0,
                msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
            )
            self.assertIn("--- Seeding System Methods ---", completed.stdout)
            self.assertIn("Seeded", completed.stdout)
            self.assertIn("Current Store Status:", completed.stdout)
            self.assertEqual(completed.stderr.strip(), "")
            self.assertTrue(store_path.exists())

    def test_benchmark_response_rewriter_reports_missing_payload_file_to_stderr(self):
        command = [
            sys.executable,
            "scripts/benchmark_response_rewriter.py",
            "--payload-file",
            str(self.cache_dir / "missing_payload.json"),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("payload file not found", completed.stderr)

    def test_benchmark_response_rewriter_writes_json_result_to_stdout(self):
        command = [
            sys.executable,
            "scripts/benchmark_response_rewriter.py",
            "--mode",
            "persistent",
            "--iterations",
            "2",
            "--command",
            sys.executable,
            "scripts/response_rewriter_stub_backend.py",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["iterations"], 2)
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["mode"], "persistent")
        self.assertEqual(payload["results"][0]["iterations"], 2)
        self.assertIn("自然化", payload["results"][0]["last_output"])
        self.assertEqual(completed.stderr.strip(), "")

    def test_benchmark_response_rewriter_http_mode_writes_json_result_to_stdout(self):
        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body_length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(body_length).decode("utf-8"))
                response = {
                    "choices": [
                        {
                            "message": {
                                "content": payload["messages"][-1]["content"].split("response_text:\n", 1)[-1] + "（http自然化）。"
                            }
                        }
                    ]
                }
                encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format, *args):
                return

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._register_http_server_cleanup(server, thread)

        command = [
            sys.executable,
            "scripts/benchmark_response_rewriter.py",
            "--mode",
            "http",
            "--iterations",
            "2",
            "--endpoint-url",
            f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            "--model-id",
            "local-llama",
            "--max-new-tokens",
            "24",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["iterations"], 2)
        self.assertEqual(payload["model_id"], "local-llama")
        self.assertEqual(payload["max_new_tokens"], 24)
        self.assertEqual(payload["results"][0]["mode"], "http")
        self.assertIn("http自然化", payload["results"][0]["last_output"])
        self.assertEqual(completed.stderr.strip(), "")

    def test_inspect_response_rewriter_quality_http_mode_writes_json_result_to_stdout(self):
        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body_length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(body_length).decode("utf-8"))
                response_text = payload["messages"][-1]["content"].split("response_text:\n", 1)[-1]
                response = {
                    "choices": [
                        {
                            "message": {
                                "content": response_text + "（品質確認自然化）。"
                            }
                        }
                    ]
                }
                encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format, *args):
                return

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._register_http_server_cleanup(server, thread)

        command = [
            sys.executable,
            "scripts/inspect_response_rewriter_quality.py",
            "--provider",
            "openai_compatible_http",
            "--endpoint-url",
            f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            "--model-id",
            "local-llama",
            "--max-new-tokens",
            "24",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["provider"], "openai_compatible_http")
        self.assertEqual(payload["model_id"], "local-llama")
        self.assertGreaterEqual(payload["summary"]["total_cases"], 5)
        self.assertIn("deterministic_progress", payload["family_summary"])
        self.assertIn("excluded_conversational", payload["family_summary"])
        self.assertEqual(payload["summary"]["semantic_regression"], 0)
        self.assertEqual(payload["summary"]["unexpected_rewrite"], 0)
        self.assertEqual(payload["summary"]["rewritten"], 0)
        self.assertEqual(payload["summary"]["no_effect"], 0)
        self.assertEqual(payload["summary"]["preserved_as_expected"], payload["summary"]["total_cases"])
        self.assertTrue(all(not item["changed"] for item in payload["results"]))
        self.assertEqual(completed.stderr.strip(), "")

    def test_run_response_rewriter_conversation_probe_http_mode_writes_json_result_to_stdout(self):
        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body_length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(body_length).decode("utf-8"))
                response_text = payload["messages"][-1]["content"].split("response_text:\n", 1)[-1]
                response = {
                    "choices": [
                        {
                            "message": {
                                "content": response_text + "（会話自然化）。"
                            }
                        }
                    ]
                }
                encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format, *args):
                return

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._register_http_server_cleanup(server, thread)

        turns = [
            "雑談しよう",
            "ファイルを作って",
            "sample.txt",
        ]
        turns_path = self.cache_dir / "conversation_probe_turns.json"
        turns_path.write_text(json.dumps(turns, ensure_ascii=False, indent=2), encoding="utf-8")
        self.addCleanup(turns_path.unlink, missing_ok=True)

        command = [
            sys.executable,
            "scripts/run_response_rewriter_conversation_probe.py",
            "--turns-file",
            str(turns_path),
            "--provider",
            "openai_compatible_http",
            "--endpoint-url",
            f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            "--model-id",
            "local-llama",
            "--max-new-tokens",
            "24",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["provider"], "openai_compatible_http")
        self.assertEqual(payload["probe"]["turn_count"], 3)
        self.assertEqual(payload["probe"]["results"][0]["intent"], "SMALLTALK")
        self.assertIsNotNone(payload["probe"]["results"][0]["pre_rewrite_text"])
        self.assertTrue(payload["probe"]["results"][0]["rewrite_applied"])
        self.assertIn("（会話自然化）", payload["probe"]["results"][0]["response_text"])
        self.assertTrue(payload["probe"]["results"][1]["clarification_needed"])
        self.assertIsNone(payload["probe"]["results"][1]["pre_rewrite_text"])
        self.assertFalse(payload["probe"]["results"][1]["rewrite_applied"])
        self.assertNotIn("（会話自然化）", payload["probe"]["results"][1]["response_text"])
        self.assertEqual(completed.stderr.strip(), "")

    def test_suggest_design_tags_http_mode_writes_json_result_to_stdout(self):
        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                response = {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "suggestions": [
                                            {
                                                "step_number": 1,
                                                "semantic_roles": {"path": "users.json"},
                                                "notes": "quoted path is explicit"
                                            },
                                            {
                                                "step_number": 3,
                                                "semantic_roles": {"sql": "SELECT * FROM Users"},
                                                "notes": "this should be rejected"
                                            }
                                        ]
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ]
                }
                encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format, *args):
                return

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._register_http_server_cleanup(server, thread)

        stripped_design = self.cache_dir / "ComplexLinqSearch.suggest.design.md"
        strip_command = [
            sys.executable,
            "scripts/strip_design_tags.py",
            "--design",
            "scenarios/ComplexLinqSearch.design.md",
            "--output",
            str(stripped_design),
        ]
        strip_completed = subprocess.run(
            strip_command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            strip_completed.returncode,
            0,
            msg=f"stdout:\n{strip_completed.stdout}\n\nstderr:\n{strip_completed.stderr}",
        )

        command = [
            sys.executable,
            "scripts/suggest_design_tags.py",
            "--design",
            str(stripped_design),
            "--provider",
            "openai_compatible_http",
            "--endpoint-url",
            f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            "--model-id",
            "local-llama",
            "--mode",
            "literal_roles_only",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["provider"], "openai_compatible_http")
        self.assertEqual(payload["model_id"], "local-llama")
        self.assertEqual(payload["mode"], "literal_roles_only")
        self.assertEqual(payload["result"]["mode"], "literal_roles_only")
        self.assertGreaterEqual(payload["result"]["candidate_count"], 1)
        accepted = payload["result"]["accepted_suggestions"]
        rejected = payload["result"]["rejected_suggestions"]
        self.assertEqual(accepted[0]["step_number"], 1)
        self.assertEqual(accepted[0]["semantic_roles"]["path"], "users.json")
        self.assertGreaterEqual(len(rejected), 1)
        self.assertEqual(completed.stderr.strip(), "")

    def test_probe_design_authoring_reduction_writes_json_result_to_stdout(self):
        command = [
            sys.executable,
            "scripts/probe_design_authoring_reduction.py",
            "--design",
            "scenarios/ComplexLinqSearch.design.md",
            "--skip-generate",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/ComplexLinqSearch.design.md"))
        self.assertTrue(payload["skip_generate"])
        self.assertFalse(payload["assist_configured"])
        variant_names = [item["variant"] for item in payload["variants"]]
        self.assertEqual(
            variant_names,
            [
                "original",
                "drop_step_meta",
                "drop_step_meta_refs",
                "drop_step_meta_refs_ops",
                "strip_tags_keep_literals",
                "strip_tags_drop_literals",
            ],
        )
        blocked_variant = next(item for item in payload["variants"] if item["variant"] == "strip_tags_drop_literals")
        inference = blocked_variant["deterministic"]["inference"]
        self.assertEqual(inference["status"], "blocked")
        self.assertEqual(completed.stderr.strip(), "")

    def test_validate_design_authoring_writes_json_result_to_stdout(self):
        command = [
            sys.executable,
            "scripts/validate_design_authoring.py",
            "--design",
            "scenarios/ComplexLinqSearch.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/ComplexLinqSearch.design.md"))
        self.assertFalse(payload["assist_configured"])
        self.assertTrue(payload["validation"]["ok"])
        self.assertEqual(payload["validation"]["failures"], [])
        variant_names = [item["variant"] for item in payload["variants"]]
        self.assertIn("drop_step_meta_refs_ops", variant_names)
        self.assertIn("strip_tags_drop_literals", variant_names)
        self.assertEqual(completed.stderr.strip(), "")

    def test_review_design_generation_snapshot_accepts_complex_linq_search(self):
        command = [
            sys.executable,
            "scripts/review_design_generation_snapshot.py",
            "--design",
            "scenarios/ComplexLinqSearch.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/ComplexLinqSearch.design.md"))
        self.assertEqual(payload["module_name"], "ComplexLinqSearch")
        self.assertIn('[semantic_roles:{"path":"users.json"}]', payload["inferred_design_text"])
        self.assertIn('File.ReadAllText("users.json")', payload["generated_code"])
        self.assertIn("JsonSerializer.Deserialize<List<User>>", payload["generated_code"])
        self.assertIn('item.Name.StartsWith("A")', payload["generated_code"])
        self.assertIn("Price > 500", payload["generated_code"])
        self.assertEqual(payload["spec_issues"], [])
        self.assertTrue(payload["verification"]["valid"])
        self.assertEqual(completed.stderr.strip(), "")

    def test_validate_design_authoring_accepts_new_minimal_template_scenario(self):
        command = [
            sys.executable,
            "scripts/validate_design_authoring.py",
            "--design",
            "scenarios/UserNamePrefixSearch.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/UserNamePrefixSearch.design.md"))
        self.assertTrue(payload["validation"]["ok"])
        self.assertEqual(completed.stderr.strip(), "")

    def test_generate_from_design_accepts_new_minimal_template_scenario(self):
        output_path = self.cache_dir / "UserNamePrefixSearch.cs"
        if output_path.exists():
            output_path.unlink()

        command = [
            sys.executable,
            "scripts/generate/generate_from_design.py",
            "--design",
            "scenarios/UserNamePrefixSearch.design.md",
            "--output",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        generated_code = output_path.read_text(encoding="utf-8")
        self.assertIn('File.ReadAllText("users.json")', generated_code)
        self.assertIn("JsonSerializer.Deserialize<List<User>>(content)", generated_code)
        self.assertIn('item.Name.StartsWith("A")', generated_code)
        self.assertIn("Console.WriteLine", generated_code)

    def test_validate_design_authoring_accepts_new_db_minimal_scenario(self):
        command = [
            sys.executable,
            "scripts/validate_design_authoring.py",
            "--design",
            "scenarios/InventoryLookupMinimal.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/InventoryLookupMinimal.design.md"))
        self.assertTrue(payload["validation"]["ok"])
        self.assertEqual(completed.stderr.strip(), "")

    def test_review_design_generation_snapshot_accepts_new_db_minimal_scenario(self):
        command = [
            sys.executable,
            "scripts/review_design_generation_snapshot.py",
            "--design",
            "scenarios/InventoryLookupMinimal.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/InventoryLookupMinimal.design.md"))
        self.assertEqual(payload["module_name"], "InventoryLookupMinimal")
        self.assertIn("Inventory Database", payload["inferred_design_text"])
        self.assertIn('[semantic_roles:{"sql":"SELECT * FROM Inventory"}]', payload["inferred_design_text"])
        self.assertIn('QueryAsync<Inventory>("SELECT * FROM Inventory"', payload["generated_code"])
        self.assertEqual(payload["spec_issues"], [])
        self.assertTrue(payload["verification"]["valid"])
        self.assertEqual(completed.stderr.strip(), "")

    def test_validate_design_authoring_accepts_new_http_minimal_scenario(self):
        command = [
            sys.executable,
            "scripts/validate_design_authoring.py",
            "--design",
            "scenarios/ProductApiLookupMinimal.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/ProductApiLookupMinimal.design.md"))
        self.assertTrue(payload["validation"]["ok"])
        self.assertEqual(completed.stderr.strip(), "")

    def test_review_design_generation_snapshot_accepts_new_http_minimal_scenario(self):
        command = [
            sys.executable,
            "scripts/review_design_generation_snapshot.py",
            "--design",
            "scenarios/ProductApiLookupMinimal.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/ProductApiLookupMinimal.design.md"))
        self.assertEqual(payload["module_name"], "ProductApiLookupMinimal")
        self.assertIn("Product API Endpoint", payload["inferred_design_text"])
        self.assertIn('[semantic_roles:{"url":"https://api.example.com/products"}]', payload["inferred_design_text"])
        self.assertIn('GetStringAsync("https://api.example.com/products")', payload["generated_code"])
        self.assertIn("JsonSerializer.Deserialize<List<Product>>", payload["generated_code"])
        self.assertEqual(payload["spec_issues"], [])
        self.assertTrue(payload["verification"]["valid"])
        self.assertEqual(completed.stderr.strip(), "")

    def test_review_design_generation_snapshot_accepts_csv_sales_aggregation_without_nullable_warning(self):
        command = [
            sys.executable,
            "scripts/review_design_generation_snapshot.py",
            "--design",
            "scenarios/CsvSalesAggregation.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/CsvSalesAggregation.design.md"))
        self.assertEqual(payload["module_name"], "CsvSalesAggregation")
        self.assertIn("File.ReadAllText(input_path)", payload["generated_code"])
        self.assertIn("File.WriteAllText(output_path, csv)", payload["generated_code"])
        self.assertEqual(payload["spec_issues"], [])
        self.assertTrue(payload["verification"]["valid"])
        self.assertNotIn("CS8632", payload["verification"].get("stdout", ""))
        self.assertEqual(completed.stderr.strip(), "")

    def test_review_design_generation_snapshot_accepts_sync_external_data_without_poco_nullable_warning(self):
        command = [
            sys.executable,
            "scripts/review_design_generation_snapshot.py",
            "--design",
            "scenarios/SyncExternalData.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/SyncExternalData.design.md"))
        self.assertEqual(payload["module_name"], "SyncExternalData")
        self.assertIn('GetStringAsync("https://api.example.com/products")', payload["generated_code"])
        self.assertIn('ExecuteAsync("INSERT INTO Products (Name, Price) VALUES (@Name, @Price)", items)', payload["generated_code"])
        self.assertIn("public string? Name", payload["generated_code"])
        self.assertIn("public string? Category", payload["generated_code"])
        self.assertEqual(payload["spec_issues"], [])
        self.assertTrue(payload["verification"]["valid"])
        self.assertNotIn("CS8618", payload["verification"].get("stdout", ""))
        self.assertEqual(completed.stderr.strip(), "")

    def test_review_design_generation_snapshot_accepts_daily_inventory_sync(self):
        command = [
            sys.executable,
            "scripts/review_design_generation_snapshot.py",
            "--design",
            "scenarios/DailyInventorySync.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/DailyInventorySync.design.md"))
        self.assertEqual(payload["module_name"], "DailyInventorySync")
        self.assertIn("Inventory API Endpoint", payload["inferred_design_text"])
        self.assertIn("[ACTION|JSON_DESERIALIZE|Inventory|List<Inventory>|NONE]", payload["inferred_design_text"])
        self.assertIn('GetStringAsync("https://inventory.example.com/api/current")', payload["generated_code"])
        self.assertIn('JsonSerializer.Deserialize<List<Inventory>>(inventory)', payload["generated_code"])
        self.assertIn('ExecuteAsync("UPDATE Inventory SET Stock = @Stock WHERE Id = @Id", items)', payload["generated_code"])
        self.assertEqual(payload["spec_issues"], [])
        self.assertTrue(payload["verification"]["valid"])
        self.assertEqual(completed.stderr.strip(), "")

    def test_review_design_generation_snapshot_accepts_secure_order_processing_with_http_payload_context(self):
        command = [
            sys.executable,
            "scripts/review_design_generation_snapshot.py",
            "--design",
            "scenarios/SecureOrderProcessing.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/SecureOrderProcessing.design.md"))
        self.assertEqual(payload["module_name"], "SecureOrderProcessing")
        self.assertIn('QueryAsync<Order>(@"SELECT * FROM Orders WHERE Status = ""Pending"""', payload["generated_code"])
        self.assertIn("item.Total > 0m", payload["generated_code"])
        self.assertIn('PostAsync("https://shipping.example.com/api", new StringContent(JsonSerializer.Serialize(item1)))', payload["generated_code"])
        self.assertIn("HttpResponseMessage? order2 = null;", payload["generated_code"])
        self.assertEqual(payload["spec_issues"], [])
        self.assertTrue(payload["verification"]["valid"])
        self.assertNotIn("CS8600", payload["verification"].get("stdout", ""))
        self.assertEqual(completed.stderr.strip(), "")

    def test_validate_design_authoring_accepts_new_env_minimal_scenario(self):
        command = [
            sys.executable,
            "scripts/validate_design_authoring.py",
            "--design",
            "scenarios/AppModeEchoMinimal.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/AppModeEchoMinimal.design.md"))
        self.assertTrue(payload["validation"]["ok"])
        self.assertEqual(completed.stderr.strip(), "")

    def test_review_design_generation_snapshot_accepts_new_env_minimal_scenario(self):
        command = [
            sys.executable,
            "scripts/review_design_generation_snapshot.py",
            "--design",
            "scenarios/AppModeEchoMinimal.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/AppModeEchoMinimal.design.md"))
        self.assertEqual(payload["module_name"], "AppModeEchoMinimal")
        self.assertIn("環境変数 APP_MODE", payload["inferred_design_text"])
        self.assertIn("[ACTION|FETCH|string|string|IO|APP_MODE|env]", payload["inferred_design_text"])
        self.assertIn('Environment.GetEnvironmentVariable("APP_MODE")', payload["generated_code"])
        self.assertIn("Console.WriteLine", payload["generated_code"])
        self.assertEqual(payload["spec_issues"], [])
        self.assertTrue(payload["verification"]["valid"])
        self.assertEqual(completed.stderr.strip(), "")

    def test_review_design_generation_snapshot_writes_json_result_to_stdout(self):
        command = [
            sys.executable,
            "scripts/review_design_generation_snapshot.py",
            "--design",
            "scenarios/UserNamePrefixSearch.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["design"]), Path("scenarios/UserNamePrefixSearch.design.md"))
        self.assertEqual(payload["module_name"], "UserNamePrefixSearch")
        self.assertIn("'users.json' を読み込む", payload["original_design_text"])
        self.assertIn('[semantic_roles:{"path":"users.json"}]', payload["inferred_design_text"])
        self.assertIn('File.ReadAllText("users.json")', payload["generated_code"])
        self.assertIn('item.Name.StartsWith("A")', payload["generated_code"])
        self.assertTrue(Path(payload["inferred_design_path"]).exists())
        self.assertTrue(Path(payload["generated_code_path"]).exists())
        self.assertEqual(payload["spec_issues"], [])
        self.assertTrue(payload["verification"]["valid"])
        self.assertEqual(completed.stderr.strip(), "")

    def test_run_design_generation_regression_reports_missing_design_to_stderr(self):
        command = [
            sys.executable,
            "scripts/run_design_generation_regression.py",
            "--design",
            "scenarios/DoesNotExist.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("design file not found", completed.stderr)

    def test_run_design_generation_regression_writes_json_result_to_stdout(self):
        with tempfile.TemporaryDirectory(dir=self.cache_dir) as temp_root_str:
            output_dir = Path(temp_root_str) / "snapshots"
            command = [
                sys.executable,
                "scripts/run_design_generation_regression.py",
                "--design",
                "scenarios/DailyInventorySync.design.md",
                "--design",
                "scenarios/SecureOrderProcessing.design.md",
                "--output-dir",
                str(output_dir),
            ]
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["scenario_count"], 2)
            self.assertEqual(payload["passed"], 2)
            self.assertEqual(payload["failed"], 0)
            self.assertEqual(len(payload["results"]), 2)
            self.assertEqual(payload["results"][0]["module_name"], "DailyInventorySync")
            self.assertTrue(payload["results"][0]["verification_valid"])
            self.assertEqual(payload["results"][0]["spec_issue_count"], 0)
            self.assertTrue(Path(payload["results"][0]["generated_code_path"]).exists())
            self.assertEqual(payload["results"][1]["module_name"], "SecureOrderProcessing")
            self.assertTrue(payload["results"][1]["verification_valid"])
            self.assertEqual(payload["results"][1]["spec_issue_count"], 0)
            self.assertTrue(Path(payload["results"][1]["generated_code_path"]).exists())
            self.assertEqual(completed.stderr.strip(), "")

    def test_run_design_generation_regression_default_set_includes_curated_scenarios(self):
        command = [
            sys.executable,
            "scripts/run_design_generation_regression.py",
            "--design",
            "scenarios/ComplexLinqSearch.design.md",
            "--design",
            "scenarios/CsvSalesAggregation.design.md",
            "--design",
            "scenarios/DailyInventorySync.design.md",
            "--design",
            "scenarios/SecureOrderProcessing.design.md",
            "--design",
            "scenarios/AppModeEchoMinimal.design.md",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["scenario_count"], 5)
        self.assertEqual(payload["passed"], 5)
        self.assertEqual(payload["failed"], 0)
        self.assertEqual(
            [item["module_name"] for item in payload["results"]],
            [
                "ComplexLinqSearch",
                "CsvSalesAggregation",
                "DailyInventorySync",
                "SecureOrderProcessing",
                "AppModeEchoMinimal",
            ],
        )
        self.assertTrue(all(item["verification_valid"] for item in payload["results"]))
        self.assertTrue(all(item["spec_issue_count"] == 0 for item in payload["results"]))
        self.assertEqual(completed.stderr.strip(), "")

    def test_inspect_design_tag_suggestion_quality_http_mode_writes_json_result_to_stdout(self):
        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body_length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(body_length).decode("utf-8"))
                user_payload = json.loads(payload["messages"][-1]["content"])
                module_name = user_payload.get("module_name")
                suggestions = []
                if module_name == "ComplexLinqSearch":
                    suggestions = [
                        {
                            "step_number": 1,
                            "semantic_roles": {"path": "users.json"},
                        }
                    ]
                elif module_name == "SyncExternalData":
                    suggestions = [
                        {
                            "step_number": 1,
                            "semantic_roles": {"url": "https://api.example.com/products"},
                        },
                        {
                            "step_number": 3,
                            "semantic_roles": {"sql": "INSERT INTO Products (Name, Price) VALUES (@Name, @Price)"},
                        },
                    ]
                elif module_name == "DailyInventorySync":
                    suggestions = [
                        {
                            "step_number": 3,
                            "semantic_roles": {"url": "https://inventory.example.com/api/current"},
                        },
                        {
                            "step_number": 5,
                            "semantic_roles": {"sql": "UPDATE Inventory SET Stock = @Stock WHERE Id = @Id"},
                        },
                    ]
                elif module_name == "UserReportGenerator":
                    suggestions = [
                        {
                            "step_number": 3,
                            "semantic_roles": {"sql": "SELECT * FROM Users"},
                        },
                        {
                            "step_number": 6,
                            "semantic_roles": {"path": "report.txt"},
                        },
                    ]
                elif module_name == "FetchProductInventory":
                    suggestions = [
                        {
                            "step_number": 2,
                            "semantic_roles": {"sql": "SELECT * FROM Inventory"},
                        }
                    ]
                response = {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps({"suggestions": suggestions}, ensure_ascii=False)
                            }
                        }
                    ]
                }
                encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format, *args):
                return

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._register_http_server_cleanup(server, thread)

        command = [
            sys.executable,
            "scripts/inspect_design_tag_suggestion_quality.py",
            "--provider",
            "openai_compatible_http",
            "--endpoint-url",
            f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            "--model-id",
            "local-llama",
        ]
        completed = subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["provider"], "openai_compatible_http")
        self.assertEqual(payload["model_id"], "local-llama")
        self.assertEqual(payload["mode"], "literal_roles_only")
        self.assertEqual(payload["summary"]["total_cases"], 5)
        self.assertEqual(payload["summary"]["all_expected_found"], 5)
        self.assertEqual(payload["summary"]["cases_with_missing_expected"], 0)
        self.assertGreaterEqual(payload["summary"]["total_accepted_suggestions"], 8)
        self.assertEqual(payload["summary"]["total_rejected_suggestions"], 0)
        self.assertEqual(payload["summary"]["expected_role_totals"]["path"], 2)
        self.assertEqual(payload["summary"]["expected_role_totals"]["url"], 2)
        self.assertEqual(payload["summary"]["expected_role_totals"]["sql"], 4)
        self.assertEqual(payload["summary"]["matched_role_totals"], payload["summary"]["expected_role_totals"])
        self.assertEqual(completed.stderr.strip(), "")
