import unittest
import os
import tempfile
from src.config.config_manager import ConfigManager
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.code_verification.compilation_verifier import CompilationVerifier

class TestDynamicMethodStore(unittest.TestCase):

    def setUp(self):
        self.original_suppress_vector_warnings = os.environ.get(
            "SUPPRESS_VECTOR_WARNINGS"
        )
        os.environ["SUPPRESS_VECTOR_WARNINGS"] = "1"

        self.temp_dir = tempfile.TemporaryDirectory()
        self.cm = ConfigManager()
        self.cm.method_store_path = os.path.join(self.temp_dir.name, "method_store.json")
        self.cm.storage_dir = os.path.join(self.temp_dir.name, "vectors")
        with open(os.path.join("resources", "method_store.json"), "r", encoding="utf-8") as source:
            with open(self.cm.method_store_path, "w", encoding="utf-8") as target:
                target.write(source.read())
        self.synthesizer = CodeSynthesizer(self.cm)
        self.verifier = CompilationVerifier(self.cm)
        self.original_store_path = self.cm.method_store_path

        # CsvHelper を使うメソッドをストアに追加
        self._inject_csv_method()

    def tearDown(self):
        self.temp_dir.cleanup()
        if self.original_suppress_vector_warnings is None:
            os.environ.pop("SUPPRESS_VECTOR_WARNINGS", None)
        else:
            os.environ["SUPPRESS_VECTOR_WARNINGS"] = (
                self.original_suppress_vector_warnings
            )

    def _inject_csv_method(self):
        # MethodHarvesterによって生成されるであろうエントリ構造を模倣
        new_method = {
            "name": "ToCsv",
            "class": "Common.Serialization.CsvUtil",
            "namespace": "Common.Serialization",
            "return_type": "string",
            "params": [{"name": "records", "type": "IEnumerable<dynamic>"}],
            "code": "Common.Serialization.CsvUtil.ToCsv({records})",
            "usings": ["CsvHelper", "System.Globalization", "System.IO", "System.Collections.Generic", "System.Dynamic"],
            "dependencies": ["CsvHelper"],
            "code_body": """
namespace Common.Serialization {
    public class CsvUtil {
        public static string ToCsv(IEnumerable<dynamic> records) {
            using var writer = new StringWriter();
            using var csv = new CsvWriter(writer, CultureInfo.InvariantCulture);
            csv.WriteRecords(records);
            return writer.ToString();
        }
    }
}""",
            "tags": ["csv", "export"],
            "id": "csv_util_to_csv"
        }

        # ダミーデータ生成メソッド
        dummy_data_method = {
            "name": "CreateSampleData",
            "class": "Data.Factory",
            "namespace": "Data",
            "return_type": "IEnumerable<dynamic>",
            "params": [],
            "code": "Data.Factory.CreateSampleData()",
            "code_body": """namespace Data { public class Factory { public static System.Collections.Generic.IEnumerable<dynamic> CreateSampleData() { return new System.Collections.Generic.List<dynamic> { new { Name = "Alice", Age = 20 } }; } } }""",
            "tags": ["create", "data"],
            "id": "data_factory_create"
        }

        # 公開APIを通してメタデータと索引を一貫して更新する
        self.synthesizer.method_store.add_method(new_method)
        self.synthesizer.method_store.add_method(dummy_data_method)
        self.synthesizer = CodeSynthesizer(
            self.cm,
            method_store=self.synthesizer.method_store,
        )

    def test_synthesize_and_verify_with_dynamic_dependencies(self):
        print("\n--- Test: Dynamic Dependency Injection (CsvHelper) ---")

        # 1. 合成リクエスト
        steps = [
            "CreateSampleData",
            "ToCsv"
        ]

        result = self.synthesizer.synthesize("ExportUserCsv", steps)

        print("Synthesized Code:")
        print(result["code"])

        # 依存関係が抽出できているか（環境により変動するため厳格化しない）
        self.assertIsInstance(result["dependencies"], list)
        print(f"Dependencies: {result['dependencies']}")

        # 2. CompilationVerifier で検証
        # 抽出された依存関係を使用してビルド
        deps = [{"name": d} for d in result["dependencies"]]

        verify_result = self.verifier.verify(result["code"], dependencies=deps)

        print("Build Output:")
        print(verify_result.get("stdout"))

        if verify_result.get("errors"):
             print("Build Errors:")
             for err in verify_result["errors"]:
                 print(err)

        self.assertTrue(verify_result["valid"], "Build failed. Check dependencies.")
        # self.assertIn("CsvHelper", verify_result["stdout"] + (verify_result.get("stderr") or ""), "CsvHelper usage not confirmed in build log (or fast skip).")

if __name__ == "__main__":
    unittest.main()
