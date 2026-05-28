import json
import os
import subprocess
import sys
import tempfile
import unittest
import hashlib
from pathlib import Path

import numpy as np

from src.pipeline_core.pipeline_core import Pipeline


class TestDocumentedEntrypoints(unittest.TestCase):
    def setUp(self):
        self.workspace_root = Path(os.getcwd())
        self.cache_dir = self.workspace_root / "cache"
        self.cache_dir.mkdir(exist_ok=True)

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
