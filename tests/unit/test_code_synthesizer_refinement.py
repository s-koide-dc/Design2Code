# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.config.config_manager import ConfigManager

class TestCodeSynthesizerRefinement(unittest.TestCase):
    def setUp(self):
        from src.morph_analyzer.morph_analyzer import MorphAnalyzer
        from src.code_synthesis.code_synthesizer import CodeSynthesizer
        from unittest.mock import MagicMock
        
        self.cm = MagicMock()
        self.cm.storage_dir = "cache"
        self.cm.workspace_root = "."
        
        # Use real MorphAnalyzer for better testing of logic
        self.morph = MorphAnalyzer(config_manager=self.cm)
        self.synthesizer = CodeSynthesizer(self.cm, morph_analyzer=self.morph)
        
        # Mock builder_client to avoid external process calls
        def mock_build_code(blueprint):
            methods = blueprint.get("methods", [])
            method = methods[0] if methods else {}
            code = f"public void {method.get('name')}() {{\n"
            for s in method.get("body", []):
                if s["type"] == "call":
                    prefix = ""
                    if s.get("out_var") and s.get("var_type"):
                        prefix = f"{s['var_type']} {s['out_var']} = "
                    elif s.get("out_var"):
                        prefix = f"var {s['out_var']} = "
                    code += f"  {prefix}{s['method']}({', '.join(s['args'])});\n"
                elif s["type"] == "assign": code += f"  {s['var_type']} {s['var_name']} = {s['value']};\n"
                elif s["type"] == "comment": code += f"  // {s['text']}\n"
            code += "}\n"
            for field in blueprint.get("fields", []):
                code = f"private readonly {field['type']} {field['name']};\n" + code
            for cls in blueprint.get("extra_classes", []):
                code += f"public class {cls['name']} {{\n"
                for p in cls.get("properties", []): code += f"  public {p['type']} {p['name']} {{ get; set; }}\n"
                code += "}\n"
            return {"status": "success", "code": code}
        self.synthesizer.builder_client.build_code = MagicMock(side_effect=mock_build_code)

        # Mock UKB search instead of harvester
        self.synthesizer.ukb = MagicMock()
        self.synthesizer.ukb.search = self.mock_search
        
        self.mock_methods = [
            {
                "id": "m1",
                "name": "ProcessLong",
                "class": "Processor",
                "return_type": "void",
                "params": [{"name": "val", "type": "long"}],
                "code": "Processor.ProcessLong({val})",
                "tags": ["test", "long"]
            },
            {
                "id": "m2",
                "name": "GetCount",
                "class": "Counter",
                "return_type": "int",
                "params": [],
                "code": "Counter.GetCount()",
                "tags": ["test", "count"]
            },
            {
                "id": "m3",
                "name": "Query",
                "class": "Db",
                "return_type": "IEnumerable<T>",
                "params": [{"name": "sql", "type": "string"}],
                "code": "Db.Query<T>({sql})",
                "tags": ["sql", "query"]
            }
        ]

    def mock_search(self, query, limit=5, intent=None, **kwargs):
        query = query.lower()
        results = []
        for m in self.mock_methods:
            score = 0.0
            if m["name"].lower() in query: score += 1.0
            if any(t in query for t in m.get("tags", [])): score += 0.5
            if "int" in query and m["name"] == "GetCount": score += 0.8
            if "sql" in query and m["name"] == "Query": score += 0.9
            if score > 0.5:
                m_copy = m.copy()
                m_copy["score"] = score
                results.append(m_copy)
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def test_int_to_long_conversion(self):
        """Test if int can be passed to a long parameter"""
        design_steps = [
            "数（int）を取得する",
            "その数を使って ProcessLong を呼び出す"
        ]
        # Inject an int variable
        result = self.synthesizer.synthesize("Test", design_steps)
        code = result["code"]
        # It should ideally use the int result in ProcessLong
        # Even if it's dynamic, we want to see if it links them.
        self.assertIn("ProcessLong", code)
        self.assertIn("var result0 = Counter.GetCount()", code)
        # Check if result0 is passed to ProcessLong
        self.assertIn("ProcessLong(result0)", code)

    def test_generic_inference_poco(self):
        """Test if T in Query<T> is inferred as Product when '商品' is in context"""
        design_steps = [
            "商品の一覧を SQL 'SELECT * FROM Products' で取得する。各商品の価格を表示する。"
        ]
        result = self.synthesizer.synthesize("GetProducts", design_steps)
        code = result["code"]
        self.assertIn("Query<Product>", code)
        self.assertIn("public class Product", code)
        self.assertIn("public int Price { get; set; }", code)

if __name__ == "__main__":
    unittest.main()
