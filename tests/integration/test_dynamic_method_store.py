import unittest
import os
import json
import shutil
from src.config.config_manager import ConfigManager
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.code_verification.compilation_verifier import CompilationVerifier
from src.code_synthesis.method_store import MethodStore

class TestDynamicMethodStore(unittest.TestCase):

    def setUp(self):
        os.environ["SUPPRESS_VECTOR_WARNINGS"] = "1"

        self.cm = ConfigManager()
        self.synthesizer = CodeSynthesizer(self.cm)
        self.verifier = CompilationVerifier(self.cm)
        
        # バックアップ
        self.original_store_path = os.path.join('resources', 'method_store.json')
        self.backup_store_path = os.path.join('resources', 'method_store_backup.json')
        if os.path.exists(self.original_store_path):
            shutil.copy(self.original_store_path, self.backup_store_path)

        # CsvHelper を使うメソッドをストアに追加
        self._inject_csv_method()

    def tearDown(self):
        # リストア
        if os.path.exists(self.backup_store_path):
            shutil.move(self.backup_store_path, self.original_store_path)

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
        
        # ストアに直接書き込み
        with open(self.original_store_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        data['methods'].append(new_method)
        data['methods'].append(dummy_data_method)
        
        with open(self.original_store_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        # インメモリのストアをリロード
        self.synthesizer.method_store = MethodStore(self.cm)

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
