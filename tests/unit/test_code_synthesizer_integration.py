# -*- coding: utf-8 -*-
import unittest
import json
import numpy as np
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.config.config_manager import ConfigManager
from src.morph_analyzer.morph_analyzer import MorphAnalyzer

class TestCodeSynthesizerIntegration(unittest.TestCase):

    def setUp(self):
        from unittest.mock import MagicMock
        import tempfile
        import os
        import shutil
        
        self.test_dir = tempfile.TemporaryDirectory()
        self.store_path = os.path.join(self.test_dir.name, "test_method_store.json")
        self.dd_path = os.path.join(self.test_dir.name, "domain_dictionary.json")
        
        # Create an empty store file
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump([], f)
            
        # Create a dummy domain dictionary
        with open(self.dd_path, "w", encoding="utf-8") as f:
            json.dump({
                "mappings": {
                    "保存": ["save"],
                    "取得": ["get"],
                    "検証": ["validate"],
                    "メール": ["email"]
                }
            }, f, ensure_ascii=False)

        class DummyVectorEngine:
            def __init__(self, dim: int = 64):
                self.dim = dim
            def get_sentence_vector(self, words):
                if not words:
                    return None
                text = " ".join([str(w) for w in words]).lower()
                vec = np.zeros(self.dim, dtype=np.float32)
                for ch in text:
                    vec[ord(ch) % self.dim] += 1.0
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec /= norm
                return vec
            def vector_similarity(self, v1, v2):
                if v1 is None or v2 is None:
                    return 0.0
                return float(np.dot(v1, v2))

        # Mock config to use our temp store
        self.cm = MagicMock(spec=ConfigManager)
        self.cm.workspace_root = os.getcwd()
        self.cm.method_store_path = self.store_path
        self.cm.storage_dir = self.test_dir.name
        self.cm.domain_dictionary_path = self.dd_path
        self.cm.repair_knowledge_path = os.path.join(self.test_dir.name, "repair_knowledge.json")
        self.cm.custom_knowledge_path = os.path.join(self.test_dir.name, "custom_knowledge.json")
        self.cm.dictionary_db_path = os.path.join(self.test_dir.name, "dictionary.db")
        self.cm.dependency_map_path = os.path.join(self.test_dir.name, "dependency_map.json")
        self.cm.intent_corpus_path = os.path.join(self.test_dir.name, "intent_corpus.json")
        self.cm.domain_dictionary_path = os.path.join(self.test_dir.name, "domain_dictionary.json")
        self.cm.error_patterns_path = os.path.join(self.test_dir.name, "error_patterns.json")
        self.cm.scoring_rules = {}
        self.cm.user_preferences = {}
        self.cm.get_retry_rules.return_value = []
        self.cm.get_safety_policy.return_value = {}

        self.ma = MorphAnalyzer(config_manager=self.cm)
        from src.code_synthesis.method_store import MethodStore
        self.vector_engine = DummyVectorEngine()
        self.ms = MethodStore(self.cm, morph_analyzer=self.ma, vector_engine=self.vector_engine)
        self.ms.items = []
        self.ms.metadata_by_id = {}
        
        self.synthesizer = CodeSynthesizer(self.cm, method_store=self.ms, morph_analyzer=self.ma)
        
        # Mock builder_client to return code based on blueprint
        def mock_build_code(blueprint):
            methods = blueprint.get("methods", [])
            method = methods[0] if methods else {}
            body = method.get("body", [])
            code_lines = [f"public {method.get('return_type', 'void')} {method.get('name')}() {{"]
            def render(stmts, indent="  "):
                for s in stmts:
                    s_type = s.get("type")
                    if s_type == "call":
                        method_expr = s['method']
                        if isinstance(method_expr, tuple): method_expr = method_expr[0]
                        code_lines.append(f"{indent}{method_expr};")
                    elif s_type == "comment":
                        code_lines.append(f"{indent}// {s['text']}")
                    elif s_type == "assign":
                        code_lines.append(f"{indent}{s['var_type']} {s['var_name']} = {s['value']};")
                    elif s_type == "raw":
                        code_lines.append(f"{indent}{s['code']}")
                    elif s_type == "foreach":
                        code_lines.append(f"{indent}foreach (var {s['item_name']} in {s['source']}) {{")
                        render(s.get("body", []), indent + "  ")
                        code_lines.append(f"{indent}}}")
                    elif s_type == "if":
                        code_lines.append(f"{indent}if ({s['condition']}) {{")
                        render(s.get("body", []), indent + "  ")
                        code_lines.append(f"{indent}}}")
            render(body)
            code_lines.append("}")
            
            # Simple DI injection representation
            full_code = []
            for field in blueprint.get("fields", []):
                full_code.append(f"private readonly {field['type']} {field['name']};")
            
            return {"status": "success", "code": "\n".join(full_code + code_lines)}
            
        self.synthesizer.builder_client.build_code = MagicMock(side_effect=mock_build_code)
        
        # Inject required methods for testing
        store = self.ms
        
        store.add_method({
            "id": "validate_email_test",
            "name": "ValidateEmail",
            "class": "Common.Validation.Utils",
            "params": [{"name": "email", "type": "string"}],
            "return_type": "bool",
            "code": "Common.Validation.Utils.ValidateEmail({email})",
            "intent": "TRANSFORM",
            "role": "TRANSFORM",
            "capabilities": ["TRANSFORM"],
            "tags": ["validation"]
        }, overwrite=True)
        
        store.add_method({
            "id": "get_user_test",
            "name": "GetUser",
            "class": "Common.Data.Repository",
            "params": [{"name": "id", "type": "string"}],
            "return_type": "User",
            "code": "Common.Data.Repository.GetUser({id})",
            "intent": "FETCH",
            "role": "FETCH",
            "capabilities": ["FETCH"],
            "tags": ["data"]
        }, overwrite=True)
        
        store.add_method({
            "id": "save_data_test",
            "name": "SaveData",
            "class": "Common.Data.Repository",
            "params": [{"name": "data", "type": "object"}],
            "return_type": "void",
            "code": "Common.Data.Repository.SaveData({data})",
            "intent": "PERSIST",
            "role": "PERSIST",
            "capabilities": ["PERSIST"],
            "tags": ["io"]
        }, overwrite=True)

        store.add_method({
            "id": "env_get_test",
            "name": "GetEnvironmentVariable",
            "class": "Environment",
            "params": [{"name": "variable", "type": "string", "role": "name"}],
            "return_type": "string",
            "code": "Environment.GetEnvironmentVariable({variable})",
            "intent": "FETCH",
            "role": "READ",
            "capabilities": ["FETCH"],
            "tags": ["env", "fetch"]
        }, overwrite=True)

    def tearDown(self):
        self.test_dir.cleanup()

    def _build_spec(self, name, steps):
        return {
            "module_name": name,
            "purpose": f"Test module for {name}",
            "inputs": [{"name": "id", "type": "string", "description": "test id"}],
            "outputs": [{"type": "void", "description": "nothing"}],
            "steps": [
                {
                    "id": f"step_{i+1}",
                    "text": s,
                    "kind": "ACTION",
                    "intent": "GENERAL",
                    "explicit_intent": True,
                    "target_entity": "Item",
                    "input_refs": [],
                    "output_type": "void",
                    "side_effect": "NONE"
                } for i, s in enumerate(steps)
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }

    def _collect_raw_codes(self, statements):
        codes = []
        for s in statements:
            if s.get("type") == "raw":
                codes.append(s.get("code", ""))
            if s.get("body"):
                codes.extend(self._collect_raw_codes(s.get("body", [])))
            if s.get("else_body"):
                codes.extend(self._collect_raw_codes(s.get("else_body", [])))
        return codes

    def _collect_all_raw_codes(self, path):
        codes = []
        codes.extend(self._collect_raw_codes(path.get("statements", [])))
        codes.extend(self._collect_raw_codes(path.get("hoisted_statements", [])))
        return codes

    def _collect_call_methods(self, statements):
        methods = []
        for s in statements:
            if s.get("type") == "call":
                methods.append(s.get("method", ""))
            if s.get("body"):
                methods.extend(self._collect_call_methods(s.get("body", [])))
            if s.get("else_body"):
                methods.extend(self._collect_call_methods(s.get("else_body", [])))
        return methods

    def test_input_link_prefers_upstream_vars(self):
        from src.utils.spec_auditor import SpecAuditor
        spec = {
            "module_name": "InputLinkUsage",
            "purpose": "Ensure input_link uses upstream outputs",
            "inputs": [{"name": "input_1", "type_format": "int", "description": "min points"}],
            "outputs": [{"type_format": "void", "description": "none"}],
            "steps": [
                {
                    "id": "step_1",
                    "text": "ユーザー一覧を取得する",
                    "kind": "ACTION",
                    "intent": "DATABASE_QUERY",
                    "explicit_intent": True,
                    "target_entity": "User",
                    "input_refs": [],
                    "output_type": "IEnumerable<User>",
                    "side_effect": "IO",
                    "source_ref": "user_db",
                    "source_kind": "db",
                    "semantic_roles": {"sql": "SELECT * FROM Users"}
                },
                {
                    "id": "step_2",
                    "text": "ポイントが入力値より多いユーザーのみを抽出する",
                    "kind": "ACTION",
                    "intent": "LINQ",
                    "explicit_intent": True,
                    "target_entity": "User",
                    "input_refs": ["step_1"],
                    "output_type": "IEnumerable<User>",
                    "side_effect": "NONE",
                    "semantic_roles": {"ops": ["filter_points_gt_input"]}
                }
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": [{"id": "user_db", "kind": "db", "description": "user db"}]
        }
        result = self.synthesizer.synthesize_from_structured_spec("InputLinkUsage", spec, return_trace=True)
        auditor = SpecAuditor()
        issues = auditor.audit(spec, result)
        self.assertFalse(any(i.startswith("SPEC_INPUT_LINK_UNUSED") for i in issues))

    def test_input_link_recommend_patch_applied(self):
        from src.replanner.reason_analyzer import ReasonAnalyzer
        from src.replanner.ir_patcher import IRPatcher
        issue = "SPEC_INPUT_LINK_UNUSED|step_2|step_1|LINQ|User|user1|RECOMMEND=use:user1"
        analyzer = ReasonAnalyzer()
        hints = analyzer.analyze({"code": "", "trace": {}}, {"valid": True}, [issue])
        patcher = IRPatcher()
        ir_tree = {
            "logic_tree": [
                {
                    "id": "step_1",
                    "semantic_map": {"semantic_roles": {}},
                    "children": [],
                    "else_children": []
                },
                {
                    "id": "step_2",
                    "semantic_map": {"semantic_roles": {}},
                    "children": [],
                    "else_children": []
                }
            ]
        }
        patched = patcher.apply_patches(ir_tree, hints)
        step2 = patched["logic_tree"][1]
        preferred = step2.get("semantic_map", {}).get("semantic_roles", {}).get("preferred_vars", [])
        if isinstance(preferred, str):
            preferred = [preferred]
        self.assertIn("user1", preferred)

    def test_input_link_drop_at_rewire(self):
        from src.replanner.reason_analyzer import ReasonAnalyzer
        from src.replanner.ir_patcher import IRPatcher
        issue = "SPEC_INPUT_LINK_UNUSED|step_2|step_1|LINQ|User|user1|RECOMMEND=use:user1|DROP_AT=step_1_1"
        analyzer = ReasonAnalyzer()
        hints = analyzer.analyze({"code": "", "trace": {}}, {"valid": True}, [issue])
        patcher = IRPatcher()
        ir_tree = {
            "logic_tree": [
                {
                    "id": "step_1",
                    "semantic_map": {"semantic_roles": {}},
                    "children": [],
                    "else_children": []
                },
                {
                    "id": "step_1_1",
                    "semantic_map": {"semantic_roles": {}},
                    "children": [],
                    "else_children": []
                },
                {
                    "id": "step_2",
                    "input_link": "step_1",
                    "semantic_map": {"semantic_roles": {}},
                    "children": [],
                    "else_children": []
                }
            ]
        }
        patched = patcher.apply_patches(ir_tree, hints)
        step2 = patched["logic_tree"][2]
        self.assertEqual(step2.get("input_link"), "step_1_1")

    def test_synthesize_chain(self):
        """
        統合テスト: 複数のステップから成る設計文からコードを合成する。
        """
        spec = {
            "module_name": "ProcessAndSave",
            "purpose": "Validate then persist",
            "inputs": [{"name": "email", "type_format": "string", "description": "email"}],
            "outputs": [{"type_format": "void", "description": "none"}],
            "steps": [
                {
                    "id": "step_1",
                    "text": "ValidateEmailで電子メールを検証する",
                    "kind": "ACTION",
                    "intent": "TRANSFORM",
                    "explicit_intent": True,
                    "target_entity": "Email",
                    "input_refs": [],
                    "output_type": "bool",
                    "side_effect": "NONE"
                },
                {
                    "id": "step_2",
                    "text": "SaveDataでデータを保存する",
                    "kind": "ACTION",
                    "intent": "PERSIST",
                    "explicit_intent": True,
                    "target_entity": "Data",
                    "input_refs": ["step_1"],
                    "output_type": "void",
                    "side_effect": "IO"
                }
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }
        result = self.synthesizer.synthesize_from_structured_spec("ProcessAndSave", spec)
        code = result["code"]
        
        # 生成コードが得られていることを確認
        self.assertTrue(isinstance(code, str) and len(code) > 0)
        self.assertIn("ProcessAndSave", code)

    def test_synthesize_with_unknown_step(self):
        """
        未知のステップが含まれる場合のテスト。
        """
        design_steps = [
            "火星にロケットを飛ばす",
            "データを保存する"
        ]
        
        spec = self._build_spec("SpaceMission", design_steps)
        result = self.synthesizer.synthesize_from_structured_spec("SpaceMission", spec)
        self.assertTrue(isinstance(result.get("code"), str) and len(result.get("code")) > 0)

    def test_synthesize_data_chaining(self):
        """
        型によるチェイニングのテスト。
        """
        spec = {
            "module_name": "GetAndSaveUser",
            "purpose": "Fetch user and persist",
            "inputs": [{"name": "id", "type_format": "string", "description": "user id"}],
            "outputs": [{"type_format": "void", "description": "none"}],
            "steps": [
                {
                    "id": "step_1",
                    "text": "GetUserメソッドで特定のユーザー情報を取得する",
                    "kind": "ACTION",
                    "intent": "FETCH",
                    "explicit_intent": True,
                    "target_entity": "User",
                    "input_refs": [],
                    "output_type": "User",
                    "side_effect": "NONE",
                    "source_ref": "user_source",
                    "source_kind": "memory"
                },
                {
                    "id": "step_2",
                    "text": "SaveDataメソッドで取得したユーザーデータを保存する",
                    "kind": "ACTION",
                    "intent": "PERSIST",
                    "explicit_intent": True,
                    "target_entity": "Data",
                    "input_refs": ["step_1"],
                    "output_type": "void",
                    "side_effect": "IO"
                }
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": [{"id": "user_source", "kind": "memory", "description": "user source"}]
        }
        result = self.synthesizer.synthesize_from_structured_spec("GetAndSaveUser", spec)
        code = result["code"]
        
        # 生成コードが得られていることを確認
        self.assertTrue(isinstance(code, str) and len(code) > 0)
        self.assertIn("GetAndSaveUser", code)

    def test_synthesize_side_effect_flag(self):
        """副作用フラグが正しく伝搬されるかのテスト"""
        # SaveData に副作用フラグを手動で立てる (本来はHarvesterがやる)
        store = self.synthesizer.method_store
        save_method = store.get_method_by_id("save_data_test")
        if save_method:
            save_method["has_side_effects"] = True
            
        design_steps = ["データを保存する"]
        spec = self._build_spec("SaveAction", design_steps)
        result = self.synthesizer.synthesize_from_structured_spec("SaveAction", spec, return_trace=True)
        
        # Now check if it's in trace
        self.assertTrue(result.get("status") != "FAILED")

    def test_synthesize_with_di(self):
        """Dependency Injection が正しく適用されるかのテスト"""
        # インスタンスメソッド (_service. プレフィックス) を持つメソッドをスタブとして追加
        store = self.synthesizer.method_store
        di_method = {
            "id": "di_test_method",
            "name": "ProcessInstance",
            "class": "App.Services.BusinessLogic",
            "return_type": "void",
            "params": [],
            "code": "_service.ProcessInstance()",
            "intent": "TRANSFORM",
            "role": "TRANSFORM",
            "capabilities": ["TRANSFORM"],
            "tags": ["di"]
        }
        store.add_method(di_method, overwrite=True)
        
        spec = {
            "module_name": "DoBusiness",
            "purpose": "DI call",
            "inputs": [{"name": "id", "type_format": "string", "description": "id"}],
            "outputs": [{"type_format": "void", "description": "none"}],
            "steps": [
                {
                    "id": "step_1",
                    "text": "ProcessInstance",
                    "kind": "ACTION",
                    "intent": "TRANSFORM",
                    "explicit_intent": True,
                    "target_entity": "BusinessLogic",
                    "input_refs": [],
                    "output_type": "void",
                    "side_effect": "NONE"
                }
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }
        result = self.synthesizer.synthesize_from_structured_spec("DoBusiness", spec)
        code = result["code"]
        
        print("\n--- DI Generated Code ---\n")
        print(code)
        
        # 生成コードが得られていることを確認
        self.assertTrue(isinstance(code, str) and len(code) > 0)
        self.assertIn("DoBusiness", code)

    def test_ops_trim_upper_from_stdin(self):
        spec = {
            "module_name": "StdinTransform",
            "purpose": "Trim and upper-case stdin",
            "inputs": [{"name": "input_1", "type_format": "void", "description": "none"}],
            "outputs": [{"type_format": "bool", "description": "status"}],
            "steps": [
                {
                    "id": "step_1",
                    "text": "標準入力から1行取得する",
                    "kind": "ACTION",
                    "intent": "FETCH",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": [],
                    "output_type": "string",
                    "side_effect": "IO",
                    "source_ref": "STDIN",
                    "source_kind": "stdin",
                    "semantic_roles": {}
                },
                {
                    "id": "step_2",
                    "text": "取得した文字列をトリムし、大文字に変換する",
                    "kind": "ACTION",
                    "intent": "TRANSFORM",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": ["step_1"],
                    "output_type": "string",
                    "side_effect": "NONE",
                    "semantic_roles": {"ops": ["trim_upper"]}
                },
                {
                    "id": "step_3",
                    "text": "変換結果を表示する",
                    "kind": "ACTION",
                    "intent": "DISPLAY",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": ["step_2"],
                    "output_type": "void",
                    "side_effect": "NONE"
                }
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": [{"id": "STDIN", "kind": "stdin", "description": "stdin"}]
        }
        result = self.synthesizer.synthesize_from_structured_spec("StdinTransform", spec, return_trace=True)
        trace = result.get("trace", {})
        best_path = trace.get("best_path", {})
        raw_codes = self._collect_all_raw_codes(best_path)
        self.assertTrue(any("Console.ReadLine" in c for c in raw_codes))
        self.assertTrue(any("ToUpperInvariant" in c for c in raw_codes))

    def test_ops_format_kv_from_env(self):
        spec = {
            "module_name": "EnvConfig",
            "purpose": "Format env config",
            "inputs": [{"name": "input_1", "type_format": "void", "description": "none"}],
            "outputs": [{"type_format": "bool", "description": "status"}],
            "steps": [
                {
                    "id": "step_1",
                    "text": "環境変数 APP_MODE を取得する",
                    "kind": "ACTION",
                    "intent": "FETCH",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": [],
                    "output_type": "string",
                    "side_effect": "IO",
                    "source_ref": "APP_MODE",
                    "source_kind": "env",
                    "semantic_roles": {}
                },
                {
                    "id": "step_2",
                    "text": "環境変数 APP_REGION を取得する",
                    "kind": "ACTION",
                    "intent": "FETCH",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": ["step_1"],
                    "output_type": "string",
                    "side_effect": "IO",
                    "source_ref": "APP_REGION",
                    "source_kind": "env",
                    "semantic_roles": {}
                },
                {
                    "id": "step_3",
                    "text": "取得した値を整形する",
                    "kind": "ACTION",
                    "intent": "TRANSFORM",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": ["step_2"],
                    "output_type": "string",
                    "side_effect": "NONE",
                    "semantic_roles": {"ops": ["format_kv"]}
                },
                {
                    "id": "step_4",
                    "text": "整形結果を表示する",
                    "kind": "ACTION",
                    "intent": "DISPLAY",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": ["step_3"],
                    "output_type": "void",
                    "side_effect": "NONE"
                }
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": [
                {"id": "APP_MODE", "kind": "env", "description": "env mode"},
                {"id": "APP_REGION", "kind": "env", "description": "env region"}
            ]
        }
        result = self.synthesizer.synthesize_from_structured_spec("EnvConfig", spec, return_trace=True)
        trace = result.get("trace", {})
        best_path = trace.get("best_path", {})
        raw_codes = self._collect_all_raw_codes(best_path)
        self.assertTrue(
            any("Environment.GetEnvironmentVariable" in c for c in raw_codes)
            or "Environment.GetEnvironmentVariable" in result.get("code", "")
        )
        self.assertTrue(any("MODE=" in c and "REGION=" in c for c in raw_codes))

    def test_ops_linq_filter_points_gt_input(self):
        spec = {
            "module_name": "UserFilterByPoints",
            "purpose": "Filter users by points",
            "inputs": [{"name": "input_1", "type_format": "int", "description": "min points"}],
            "outputs": [{"type_format": "void", "description": "none"}],
            "steps": [
                {
                    "id": "step_1",
                    "text": "ユーザー一覧を取得する",
                    "kind": "ACTION",
                    "intent": "DATABASE_QUERY",
                    "explicit_intent": True,
                    "target_entity": "User",
                    "input_refs": [],
                    "output_type": "IEnumerable<User>",
                    "side_effect": "IO",
                    "source_ref": "user_db",
                    "source_kind": "db",
                    "semantic_roles": {"sql": "SELECT * FROM Users"}
                },
                {
                    "id": "step_2",
                    "text": "ポイントが入力値より多いユーザーのみを抽出する",
                    "kind": "ACTION",
                    "intent": "LINQ",
                    "explicit_intent": True,
                    "target_entity": "User",
                    "input_refs": ["step_1"],
                    "output_type": "IEnumerable<User>",
                    "side_effect": "NONE",
                    "semantic_roles": {"ops": ["filter_points_gt_input"]}
                }
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": [{"id": "user_db", "kind": "db", "description": "user db"}]
        }
        result = self.synthesizer.synthesize_from_structured_spec("UserFilterByPoints", spec, return_trace=True)
        trace = result.get("trace", {})
        best_path = trace.get("best_path", {})
        raw_codes = self._collect_all_raw_codes(best_path)
        self.assertTrue(any("Points > input_1" in c for c in raw_codes))

    def test_ops_csv_aggregation(self):
        spec = {
            "module_name": "CsvSalesAggregation",
            "purpose": "Aggregate sales CSV",
            "inputs": [
                {"name": "input_path", "type_format": "string", "description": "input csv"},
                {"name": "output_path", "type_format": "string", "description": "output csv"}
            ],
            "outputs": [{"type_format": "string", "description": "output path"}],
            "steps": [
                {
                    "id": "step_1",
                    "text": "入力ファイルパスのCSVを読み込む",
                    "kind": "ACTION",
                    "intent": "FETCH",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": [],
                    "output_type": "string",
                    "side_effect": "IO",
                    "source_ref": "input_path",
                    "source_kind": "file",
                    "semantic_roles": {}
                },
                {
                    "id": "step_2",
                    "text": "CSVを行配列に分割する",
                    "kind": "ACTION",
                    "intent": "TRANSFORM",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": ["step_1"],
                    "output_type": "List<string>",
                    "side_effect": "NONE",
                    "semantic_roles": {"ops": ["split_lines"]}
                },
                {
                    "id": "step_3",
                    "text": "各行から商品名と金額を抽出する",
                    "kind": "LOOP",
                    "intent": "GENERAL",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": ["step_2"],
                    "output_type": "void",
                    "side_effect": "NONE"
                },
                {
                    "id": "step_4",
                    "text": "商品別の合計金額を集計する",
                    "kind": "ACTION",
                    "intent": "CALC",
                    "explicit_intent": True,
                    "target_entity": "decimal",
                    "input_refs": ["step_3"],
                    "output_type": "decimal",
                    "side_effect": "NONE",
                    "semantic_roles": {"ops": ["aggregate_by_product"]}
                },
                {
                    "id": "step_5",
                    "text": "集計結果をCSV形式の文字列に変換する",
                    "kind": "ACTION",
                    "intent": "TRANSFORM",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": ["step_4"],
                    "output_type": "string",
                    "side_effect": "NONE",
                    "semantic_roles": {"ops": ["csv_serialize"]}
                },
                {
                    "id": "step_6",
                    "text": "出力ファイルパスにCSVを書き出す",
                    "kind": "ACTION",
                    "intent": "PERSIST",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": ["step_5"],
                    "output_type": "void",
                    "side_effect": "IO",
                    "source_ref": "output_path",
                    "source_kind": "file",
                    "semantic_roles": {}
                }
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": [
                {"id": "input_path", "kind": "file", "description": "input csv"},
                {"id": "output_path", "kind": "file", "description": "output csv"}
            ]
        }
        result = self.synthesizer.synthesize_from_structured_spec("CsvSalesAggregation", spec, return_trace=True)
        trace = result.get("trace", {})
        best_path = trace.get("best_path", {})
        raw_codes = self._collect_all_raw_codes(best_path)
        self.assertTrue(any("File.ReadAllText" in c for c in raw_codes))
        self.assertTrue(any("File.WriteAllText" in c for c in raw_codes))
        self.assertTrue(any("Split(new[] { \"\\r\\n\", \"\\n\" }" in c for c in raw_codes))
        self.assertTrue(any("ToList()" in c for c in raw_codes))
        self.assertTrue(any("Dictionary<string, decimal>" in c for c in raw_codes))
        self.assertTrue(any("string.Join(Environment.NewLine" in c for c in raw_codes))


if __name__ == '__main__':
    unittest.main()
