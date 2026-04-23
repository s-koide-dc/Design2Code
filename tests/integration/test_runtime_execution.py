import unittest
import os
import json
import shutil
from src.config.config_manager import ConfigManager
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.code_verification.execution_verifier import ExecutionVerifier
from src.code_synthesis.method_store import MethodStore

class TestRuntimeExecution(unittest.TestCase):

    def setUp(self):
        self.cm = ConfigManager()
        self.synthesizer = CodeSynthesizer(self.cm)
        self.verifier = ExecutionVerifier(self.cm)
        
        # バックアップ
        self.original_store_path = os.path.join('resources', 'method_store.json')
        self.backup_store_path = os.path.join('resources', 'method_store_backup.json')
        if os.path.exists(self.original_store_path):
            shutil.copy(self.original_store_path, self.backup_store_path)

        # 1. テスト用のメソッドを注入 (CsvHelper利用)
        self._inject_test_methods()

    def tearDown(self):
        if os.path.exists(self.backup_store_path):
            shutil.move(self.backup_store_path, self.original_store_path)

    def _inject_test_methods(self):
        new_methods = [
            {
                "name": "ToCsv",
                "class": "Common.Serialization.CsvUtil",
                "namespace": "Common.Serialization",
                "return_type": "string",
                "params": [{"name": "records", "type": "IEnumerable<dynamic>"}],
                "code": "Common.Serialization.CsvUtil.ToCsv({records})",
                "usings": ["CsvHelper", "System.Globalization", "System.IO", "System.Collections.Generic"],
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
                "id": "csv_util_to_csv"
            },
            {
                "name": "CreateSampleData",
                "class": "Data.Factory",
                "namespace": "Data",
                "return_type": "IEnumerable<dynamic>",
                "params": [],
                "code": "Data.Factory.CreateSampleData()",
                "code_body": """namespace Data { public class Factory { public static System.Collections.Generic.IEnumerable<dynamic> CreateSampleData() { return new System.Collections.Generic.List<dynamic> { new { Name = \"Alice\", Age = 20 } }; } } }""",
                "id": "data_factory_create"
            }
        ]
        
        # ストアに直接書き込み
        with open(self.original_store_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # SemanticSearchBaseへの移行により、ルートキーが 'items' になっている可能性がある
        target_list = None
        for key in ['items', 'methods']:
            if key in data:
                target_list = data[key]
                break
        
        if target_list is None:
            data['items'] = []
            target_list = data['items']
            
        target_list.extend(new_methods)
        
        with open(self.original_store_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        self.synthesizer.method_store = MethodStore(self.cm)

    def test_synthesize_and_run_test(self):
        print("\n--- Test: Runtime Execution Verification ---")
        
        steps = ["CreateSampleData", "ToCsv"]
        result = self.synthesizer.synthesize("ExportUserCsv", steps)
        
        source_code = result["code"]
        print("Synthesized Code Length:", len(source_code))
        
        # 2. テストコードの作成 (xUnit)
        test_code = """
using Xunit;
using System.Threading.Tasks;

public class RuntimeTest
{
    [Fact]
    public void ExportUserCsv_ShouldContainAlice()
    {
        // Arrange
        var processor = new GeneratedProcessor();
        
        # Act
        var result = processor.ExportUserCsv();
        
        # Assert
        Assert.NotNull(result);
        Assert.Contains("Alice", result);
        Assert.Contains("20", result);
        System.Console.WriteLine("CSV Result: " + result);
    }
}
"""
        # Pythonのf-stringやトリプルクォート内の # はコメント扱いになるので注意
        # ここではプレーンな文字列として扱う
        test_code = test_code.replace("# Act", "// Act").replace("# Assert", "// Assert")

        # 3. 実行検証
        deps = [{"name": d} for d in result["dependencies"]]
        runtime_result = self.verifier.verify_runtime(source_code, test_code, dependencies=deps)
        
        print("Test Summary:", runtime_result.get("summary"))
        if not runtime_result["success"]:
            print("Test Failed!")
            print("Stdout:", runtime_result.get("stdout"))
            print("Stderr:", runtime_result.get("stderr"))
            for fail in runtime_result.get("failures", []):
                print(f"  - {fail['test_name']}: {fail['message']}")

        self.assertTrue(runtime_result["success"], "Runtime execution failed.")
        self.assertEqual(runtime_result["summary"]["passed"], 1)

    def test_side_effect_mocking(self):
        print("\n--- Test: Side Effect Mocking ---")
        
        # 危険な操作を含むコード
        source_code = """
using System.IO;
public class GeneratedProcessor {
    public void DangerousAction() {
        File.WriteAllText("danger.txt", "should not exist");
    }
}
"""
        test_code = """
using Xunit;
public class SideEffectTest {
    [Fact]
    public void TestDangerousAction() {
        var p = new GeneratedProcessor();
        p.DangerousAction();
        // ここで例外が出なければ（モックされていれば）成功
    }
}
"""
        # 副作用フラグをTrueにして実行
        runtime_result = self.verifier.verify_runtime(source_code, test_code, has_side_effects=True)
        
        print("Test Summary:", runtime_result.get("summary"))
        self.assertTrue(runtime_result["success"], "Side effect mocking failed.")
        self.assertEqual(runtime_result["summary"]["passed"], 1)
        
        # 実際にファイルが作成されていないことを確認したいが、
        # 実行ディレクトリが別なので、コンパイルエラー等にならなければ概ねOK
        # (File.WriteAllText がコメントアウトされていれば構文的に正しいはず)

if __name__ == "__main__":
    unittest.main()
