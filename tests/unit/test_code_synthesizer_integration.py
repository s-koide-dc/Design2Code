# -*- coding: utf-8 -*-
import unittest
import json
import os
import numpy as np
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.config.config_manager import ConfigManager
from src.morph_analyzer.morph_analyzer import MorphAnalyzer
from src.utils.code_builder_client import CodeBuilderClient

class TestCodeSynthesizerIntegration(unittest.TestCase):

    def _debug_dump_generated_code(self, label, code):
        flag = str(os.environ.get("NLP_TEST_DEBUG_STDOUT", "")).strip().lower()
        if flag not in {"1", "true", "yes", "on"}:
            return
        print(f"\n--- {label} ---\n")
        print(code)

    def setUp(self):
        from unittest.mock import MagicMock
        import tempfile
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
                    elif s_type == "retry":
                        max_attempts = s.get("max_attempts", 3)
                        exception_type = s.get("exception_type", "Exception")
                        base_delay_ms = s.get("base_delay_ms", 0)
                        max_delay_ms = s.get("max_delay_ms", 0)
                        backoff_multiplier = s.get("backoff_multiplier", 1.0)
                        if base_delay_ms:
                            code_lines.append(
                                f"{indent}for (int retryAttempt = 0, retryDelayMs = {int(base_delay_ms)}; retryAttempt < {max_attempts}; retryAttempt++) {{"
                            )
                        else:
                            code_lines.append(f"{indent}for (var retryAttempt = 0; retryAttempt < {max_attempts}; retryAttempt++) {{")
                        code_lines.append(f"{indent}  try {{")
                        render(s.get("body", []), indent + "    ")
                        code_lines.append(f"{indent}    break;")
                        code_lines.append(f"{indent}  }} catch ({exception_type}) {{")
                        code_lines.append(f"{indent}    if (retryAttempt == {int(max_attempts) - 1}) throw;")
                        if base_delay_ms:
                            code_lines.append(f"{indent}    System.Threading.Thread.Sleep(retryDelayMs);")
                            if max_delay_ms:
                                if float(backoff_multiplier) > 1.0:
                                    code_lines.append(f"{indent}    retryDelayMs = Math.Min({int(max_delay_ms)}, (int)Math.Ceiling(retryDelayMs * {float(backoff_multiplier)}));")
                                else:
                                    code_lines.append(f"{indent}    retryDelayMs = Math.Min({int(max_delay_ms)}, retryDelayMs);")
                            elif float(backoff_multiplier) > 1.0:
                                code_lines.append(f"{indent}    retryDelayMs = (int)Math.Ceiling(retryDelayMs * {float(backoff_multiplier)});")
                        code_lines.append(f"{indent}  }}")
                        code_lines.append(f"{indent}}}")
                    elif s_type == "timeout":
                        timeout_ms = int(s.get("timeout_ms", 30000))
                        code_lines.append(f"{indent}{{")
                        if method.get("is_async"):
                            code_lines.append(f"{indent}  using var timeoutCts = new System.Threading.CancellationTokenSource(System.TimeSpan.FromMilliseconds({timeout_ms}));")
                            code_lines.append(f"{indent}  var timeoutTask = System.Threading.Tasks.Task.Run(async () => {{")
                            render(s.get("body", []), indent + "    ")
                            code_lines.append(f"{indent}  }}, timeoutCts.Token);")
                            code_lines.append(f"{indent}  try {{")
                            code_lines.append(f"{indent}    await timeoutTask.WaitAsync(timeoutCts.Token);")
                            code_lines.append(f"{indent}  }} catch (System.OperationCanceledException) {{")
                            code_lines.append(f"{indent}    throw new System.TimeoutException(\"Operation timed out after {timeout_ms}ms.\");")
                            code_lines.append(f"{indent}  }}")
                        else:
                            code_lines.append(f"{indent}  var timeoutTask = System.Threading.Tasks.Task.Run(() => {{")
                            render(s.get('body', []), indent + '    ')
                            code_lines.append(f"{indent}  }});")
                            code_lines.append(f"{indent}  if (!timeoutTask.Wait(System.TimeSpan.FromMilliseconds({timeout_ms}))) {{")
                            code_lines.append(f"{indent}    throw new System.TimeoutException(\"Operation timed out after {timeout_ms}ms.\");")
                            code_lines.append(f"{indent}  }}")
                        code_lines.append(f"{indent}}}")
                    elif s_type == "transaction":
                        code_lines.append(f"{indent}{{")
                        if method.get("is_async"):
                            code_lines.append(f"{indent}  using var transactionScope = new System.Transactions.TransactionScope(System.Transactions.TransactionScopeAsyncFlowOption.Enabled);")
                        else:
                            code_lines.append(f"{indent}  using var transactionScope = new System.Transactions.TransactionScope();")
                        render(s.get("body", []), indent + "  ")
                        code_lines.append(f"{indent}  transactionScope.Complete();")
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

    def _base_path(self):
        return {
            "consumed_ids": set(),
            "completed_nodes": 0,
            "statements": [],
            "type_to_vars": {},
            "used_names": set(["db", "http", "logger", "_logger", "_httpClient", "_dbConnection"]),
            "all_usings": set(),
            "poco_defs": {},
            "method_return_type": "void",
            "last_literal_map": {},
            "input_defs": [],
            "dependencies": set(),
            "rank_tuple": (0, 0, 0, 0.0),
        }

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
        self._debug_dump_generated_code("DI Generated Code", code)
        
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

    def test_spec_role_deserialize_dispatches_json_handler(self):
        node = {
            "id": "step_json",
            "type": "ACTION",
            "intent": "TRANSFORM",
            "role": "ACTION",
            "target_entity": "User",
            "cardinality": "COLLECTION",
            "output_type": "List<User>",
            "semantic_map": {
                "spec_role": "DESERIALIZE",
                "semantic_roles": {"source_var": "jsonText"},
                "logic": []
            }
        }
        path = self._base_path()
        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertTrue(any("JsonSerializer.Deserialize<List<User>>(jsonText)" in c for c in raw_codes))

    def test_spec_role_filter_dispatches_linq_handler(self):
        node = {
            "id": "step_filter",
            "type": "ACTION",
            "intent": "TRANSFORM",
            "role": "ACTION",
            "target_entity": "User",
            "cardinality": "COLLECTION",
            "output_type": "IEnumerable<User>",
            "semantic_map": {
                "spec_role": "FILTER",
                "semantic_roles": {"ops": ["filter_points_gt_input"]},
                "logic": []
            }
        }
        path = self._base_path()
        path["type_to_vars"] = {
            "IEnumerable<User>": [{"var_name": "users", "role": "data", "node_id": "step_1", "target_entity": "User"}],
            "int": [{"var_name": "input_1", "role": "input", "node_id": "input"}],
        }
        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertTrue(any("users.Where" in c and "Points > input_1" in c for c in raw_codes))

    def test_filter_with_default_provenance_stays_conservative_downstream(self):
        node = {
            "id": "step_filter_weak",
            "type": "ACTION",
            "intent": "LINQ",
            "role": "FILTER",
            "target_entity": "User",
            "cardinality": "COLLECTION",
            "output_type": "IEnumerable<User>",
            "semantic_map": {
                "spec_role": "FILTER",
                "semantic_roles": {
                    "property": "Points",
                    "predicate_resolution": "default_predicate",
                    "collection_resolution": "default_collection",
                },
                "logic": []
            }
        }
        path = self._base_path()
        path["type_to_vars"] = {
            "IEnumerable<User>": [{"var_name": "users", "role": "data", "node_id": "step_1", "target_entity": "User"}],
        }
        results = self.synthesizer.action_synthesizer.process_node(node, path)
        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertTrue(any("Resolve weak FILTER provenance" in c for c in raw_codes))
        self.assertFalse(any(".Where(" in c and "Points" in c for c in raw_codes))

    def test_spec_role_transform_bridges_weak_intent_to_transform_handler(self):
        node = {
            "id": "step_transform_bridge",
            "type": "ACTION",
            "intent": "GENERAL",
            "role": "ACTION",
            "target_entity": "string",
            "cardinality": "SINGLE",
            "output_type": "string",
            "semantic_map": {
                "spec_role": "TRANSFORM",
                "semantic_roles": {"ops": ["trim_upper"]},
                "logic": []
            }
        }
        path = self._base_path()
        path["active_scope_item"] = "inputText"
        path["type_to_vars"] = {
            "string": [{"var_name": "inputText", "role": "content", "node_id": "step_1", "target_entity": "string"}],
        }

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertTrue(any("Trim().ToUpperInvariant()" in c for c in raw_codes))

    def test_transform_input_link_metadata_prefers_exact_upstream_var_over_active_scope_item(self):
        node = {
            "id": "step_transform_exact_source",
            "type": "ACTION",
            "intent": "TRANSFORM",
            "role": "TRANSFORM",
            "target_entity": "string",
            "cardinality": "SINGLE",
            "output_type": "string",
            "semantic_map": {
                "spec_role": "TRANSFORM",
                "semantic_roles": {
                    "ops": ["trim_upper"],
                    "transform_op_resolution": "explicit_ops",
                    "transform_source_node_id": "step_fetch_text",
                    "transform_source_resolution": "input_link_var",
                },
                "logic": []
            }
        }
        path = self._base_path()
        path["active_scope_item"] = "latestText"
        path["type_to_vars"] = {
            "string": [
                {"var_name": "fetchedText", "role": "content", "node_id": "step_fetch_text", "target_entity": "string"},
                {"var_name": "latestText", "role": "content", "node_id": "step_other_text", "target_entity": "string"},
            ],
        }

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertTrue(any("fetchedText.Trim().ToUpperInvariant()" in c for c in raw_codes))
        self.assertFalse(any("latestText.Trim().ToUpperInvariant()" in c for c in raw_codes))

    def test_iterate_runtime_bridge_keeps_loop_structure_in_synthesis(self):
        node = {
            "id": "step_loop",
            "type": "LOOP",
            "intent": "GENERAL",
            "role": "ITERATE",
            "target_entity": "User",
            "cardinality": "COLLECTION",
            "output_type": "void",
            "children": [
                {
                    "id": "step_display",
                    "type": "ACTION",
                    "intent": "DISPLAY",
                    "role": "DISPLAY",
                    "target_entity": "User",
                    "cardinality": "SINGLE",
                    "output_type": "void",
                    "semantic_map": {
                        "spec_role": "DISPLAY",
                        "semantic_roles": {"ops": ["display_names"]},
                        "logic": []
                    },
                    "children": [],
                    "else_children": [],
                }
            ],
            "semantic_map": {
                "spec_role": "ITERATE",
                "semantic_roles": {"structure_kind": "loop"},
                "logic": []
            },
            "else_children": [],
        }
        path = self._base_path()
        path["type_to_vars"] = {
            "IEnumerable<User>": [{"var_name": "users", "role": "data", "node_id": "step_1", "target_entity": "User"}],
        }
        path["poco_defs"] = {"User": {"Name": "string"}}

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        foreach_statements = [s for s in results[0].get("statements", []) if s.get("type") == "foreach"]
        self.assertTrue(foreach_statements)
        self.assertTrue(any("Console.WriteLine" in c and ".Name" in c for c in self._collect_all_raw_codes(results[0])))

    def test_iterate_input_link_metadata_prefers_exact_collection_over_latest_collection(self):
        node = {
            "id": "step_loop_exact_collection",
            "type": "LOOP",
            "intent": "GENERAL",
            "role": "ITERATE",
            "target_entity": "User",
            "cardinality": "COLLECTION",
            "output_type": "void",
            "children": [
                {
                    "id": "step_display",
                    "type": "ACTION",
                    "intent": "DISPLAY",
                    "role": "DISPLAY",
                    "target_entity": "User",
                    "cardinality": "SINGLE",
                    "output_type": "void",
                    "semantic_map": {
                        "spec_role": "DISPLAY",
                        "semantic_roles": {"ops": ["display_names"]},
                        "logic": []
                    },
                    "children": [],
                    "else_children": [],
                }
            ],
            "semantic_map": {
                "spec_role": "ITERATE",
                "semantic_roles": {
                    "structure_kind": "loop",
                    "iteration_source_node_id": "step_fetch_users",
                    "iteration_source_resolution": "input_link_collection",
                },
                "logic": []
            },
            "else_children": [],
        }
        path = self._base_path()
        path["type_to_vars"] = {
            "IEnumerable<User>": [
                {"var_name": "fetchedUsers", "role": "data", "node_id": "step_fetch_users", "target_entity": "User"},
                {"var_name": "latestUsers", "role": "data", "node_id": "step_other_users", "target_entity": "User"},
            ],
        }
        path["poco_defs"] = {"User": {"Name": "string"}}

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        foreach_statements = [s for s in results[0].get("statements", []) if s.get("type") == "foreach"]
        self.assertTrue(foreach_statements)
        self.assertEqual(foreach_statements[0].get("source"), "fetchedUsers")

    def test_iterate_item_entity_metadata_overrides_weak_collection_inner_type(self):
        node = {
            "id": "step_loop_item_entity",
            "type": "LOOP",
            "intent": "GENERAL",
            "role": "ITERATE",
            "target_entity": "Item",
            "cardinality": "COLLECTION",
            "output_type": "void",
            "children": [],
            "semantic_map": {
                "spec_role": "ITERATE",
                "semantic_roles": {
                    "structure_kind": "loop",
                    "iteration_item_entity": "User",
                    "iteration_item_resolution": "collection_inner",
                    "iteration_source_node_id": "step_fetch_users",
                    "iteration_source_resolution": "input_link_collection",
                },
                "logic": []
            },
            "else_children": [],
        }
        path = self._base_path()
        path["type_to_vars"] = {
            "IEnumerable<object>": [
                {"var_name": "fetchedUsers", "role": "data", "node_id": "step_fetch_users", "target_entity": "User"},
            ],
        }

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        foreach_statements = [s for s in results[0].get("statements", []) if s.get("type") == "foreach"]
        self.assertTrue(foreach_statements)
        self.assertEqual(foreach_statements[0].get("var_type"), "User")

    def test_iterate_explicit_item_entity_keeps_nested_condition_property_binding(self):
        node = {
            "id": "step_loop_users",
            "type": "LOOP",
            "original_text": "各項目に対して、以下の処理を行う：",
            "intent": "GENERAL",
            "role": "ITERATE",
            "target_entity": "User",
            "cardinality": "COLLECTION",
            "output_type": "void",
            "input_link": "step_fetch_items",
            "semantic_map": {
                "spec_role": "ITERATE",
                "semantic_roles": {
                    "structure_kind": "loop",
                    "iteration_source_node_id": "step_fetch_items",
                    "iteration_source_resolution": "input_link_collection",
                    "iteration_item_entity": "User",
                    "iteration_item_resolution": "explicit_item_entity",
                },
                "logic": [],
            },
            "children": [
                {
                    "id": "step_condition_points",
                    "type": "CONDITION",
                    "original_text": "もし Points が 100 より大きいならば、以下の処理を行う：",
                    "intent": "EXISTS",
                    "role": "CHECK",
                    "target_entity": "User",
                    "cardinality": "SINGLE",
                    "output_type": "void",
                    "input_link": "step_loop_users",
                    "semantic_map": {
                        "spec_role": "CHECK",
                        "check_kind": "comparison_check",
                        "check_subject": "Points",
                        "subject_resolution": "schema_property",
                        "check_operator": ">",
                        "check_value": "100",
                        "semantic_roles": {"structure_kind": "condition"},
                        "logic": [],
                    },
                    "children": [
                        {
                            "id": "step_display_name",
                            "type": "ACTION",
                            "original_text": "名前を表示する。",
                            "intent": "DISPLAY",
                            "role": "DISPLAY",
                            "target_entity": "User",
                            "cardinality": "SINGLE",
                            "output_type": "void",
                            "input_link": "step_condition_points",
                            "semantic_map": {
                                "spec_role": "DISPLAY",
                                "semantic_roles": {},
                                "logic": [],
                            },
                            "children": [],
                            "else_children": [],
                        }
                    ],
                    "else_children": [],
                }
            ],
            "else_children": [],
        }
        path = self._base_path()
        path["type_to_vars"] = {
            "IEnumerable<object>": [
                {"var_name": "fetchedItems", "role": "data", "node_id": "step_fetch_items", "target_entity": "Item"},
            ],
        }
        path["poco_defs"] = {"User": {"Points": "int", "Name": "string"}}

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        statements = results[0].get("statements", [])
        foreach_statements = [s for s in statements if s.get("type") == "foreach"]
        self.assertTrue(foreach_statements)
        loop_stmt = foreach_statements[0]
        self.assertEqual(loop_stmt.get("var_type"), "User")
        self.assertEqual(loop_stmt.get("source"), "fetchedItems")
        body_json = json.dumps(loop_stmt.get("body", []), ensure_ascii=False)
        self.assertIn("item.Points > 100", body_json)

    def test_iterate_display_property_metadata_uses_item_property_inside_loop(self):
        from src.ir_generator.ir_generator import IRGenerator
        generator = IRGenerator(
            self.cm,
            entity_schema={
                "entities": [
                    {
                        "name": "User",
                        "keywords": ["ユーザー"],
                        "properties": [
                            {"name": "Name", "aliases": ["名前"]},
                            {"name": "Points", "aliases": ["ポイント"]},
                        ],
                    },
                ]
            }
        )
        steps = [
            {
                "text": "対象一覧を取得する。",
                "intent": "FETCH",
                "explicit_intent": True,
                "target_entity": "Item",
                "output_type": "IEnumerable<object>",
            },
            {
                "text": "各項目に対して、以下の処理を行う：",
                "kind": "LOOP",
                "intent": "GENERAL",
                "explicit_intent": True,
                "input_refs": ["step_1"],
                "semantic_roles": {"item_entity": "User"},
            },
            "名前を表示する。",
            "を終えて。",
        ]

        ir = generator.generate(steps)
        loop_node = ir["logic_tree"][1]
        path = self._base_path()
        path["type_to_vars"] = {
            "IEnumerable<object>": [
                {"var_name": "fetchedItems", "role": "data", "node_id": "step_1", "target_entity": "Item"},
            ],
        }
        path["poco_defs"] = {"User": {"Name": "string", "Points": "int"}}

        results = self.synthesizer.action_synthesizer.process_node(loop_node, path)

        self.assertTrue(results)
        statements = results[0].get("statements", [])
        foreach_statements = [s for s in statements if s.get("type") == "foreach"]
        self.assertTrue(foreach_statements)
        body_json = json.dumps(foreach_statements[0].get("body", []), ensure_ascii=False)
        self.assertIn("Console.WriteLine(item.Name)", body_json)

    def test_iterate_explicit_item_var_is_used_as_foreach_alias_and_branch_context(self):
        from src.ir_generator.ir_generator import IRGenerator
        generator = IRGenerator(
            self.cm,
            entity_schema={
                "entities": [
                    {
                        "name": "User",
                        "keywords": ["ユーザー"],
                        "properties": [
                            {"name": "Name", "aliases": ["名前"]},
                            {"name": "Points", "aliases": ["ポイント"]},
                        ],
                    },
                ]
            }
        )
        steps = [
            {
                "text": "対象一覧を取得する。",
                "intent": "FETCH",
                "explicit_intent": True,
                "target_entity": "Item",
                "output_type": "IEnumerable<object>",
            },
            {
                "text": "各ユーザーに対して、以下の処理を行う：",
                "kind": "LOOP",
                "intent": "GENERAL",
                "explicit_intent": True,
                "input_refs": ["step_1"],
                "semantic_roles": {"item_entity": "User", "item_var": "user"},
            },
            "もし Points が 100 より大きいならば、以下の処理を行う：",
            "名前を表示する。",
            "を終えて。",
            "を終えて。",
        ]

        ir = generator.generate(steps)
        loop_node = ir["logic_tree"][1]
        path = self._base_path()
        path["type_to_vars"] = {
            "IEnumerable<object>": [
                {"var_name": "fetchedItems", "role": "data", "node_id": "step_1", "target_entity": "Item"},
            ],
        }
        path["poco_defs"] = {"User": {"Name": "string", "Points": "int"}}

        results = self.synthesizer.action_synthesizer.process_node(loop_node, path)

        self.assertTrue(results)
        foreach_statements = [s for s in results[0].get("statements", []) if s.get("type") == "foreach"]
        self.assertTrue(foreach_statements)
        loop_stmt = foreach_statements[0]
        self.assertEqual(loop_stmt.get("item_name"), "user")
        body_json = json.dumps(loop_stmt.get("body", []), ensure_ascii=False)
        self.assertIn("user.Points > 100", body_json)
        self.assertIn("Console.WriteLine(user.Name)", body_json)

    def test_wrap_runtime_bridge_preserves_child_body_in_synthesis(self):
        spec = {
            "module_name": "RetryDisplay",
            "purpose": "Preserve wrapper body",
            "inputs": [],
            "outputs": [{"type_format": "void", "description": "none"}],
            "steps": [
                {
                    "id": "step_1",
                    "text": "リトライする。以下の処理を繰り返す：",
                    "kind": "ACTION",
                    "intent": "GENERAL",
                    "explicit_intent": True,
                    "target_entity": "Item",
                    "input_refs": [],
                    "output_type": "void",
                    "side_effect": "NONE"
                },
                {
                    "id": "step_2",
                    "text": "処理を完了しました、と表示する。",
                    "kind": "ACTION",
                    "intent": "DISPLAY",
                    "explicit_intent": True,
                    "target_entity": "string",
                    "input_refs": ["step_1"],
                    "output_type": "void",
                    "side_effect": "NONE",
                    "semantic_roles": {"message": "処理を完了しました"}
                },
                {
                    "id": "step_3",
                    "text": "を終えて。",
                    "kind": "ACTION",
                    "intent": "GENERAL",
                    "explicit_intent": True,
                    "target_entity": "Item",
                    "input_refs": ["step_2"],
                    "output_type": "void",
                    "side_effect": "NONE"
                }
            ],
            "constraints": [],
            "test_cases": [],
            "data_sources": []
        }

        result = self.synthesizer.synthesize_from_structured_spec("RetryDisplay", spec, return_trace=True)
        best_path = result.get("trace", {}).get("best_path", {})
        statements = best_path.get("statements", [])
        retry_statements = [s for s in statements if s.get("type") == "retry"]
        raw_codes = self._collect_all_raw_codes(best_path)
        code = result.get("code", "")

        self.assertTrue(retry_statements)
        self.assertEqual(retry_statements[0].get("max_attempts"), 3)
        self.assertEqual(retry_statements[0].get("max_attempts_resolution"), "default_attempts")
        self.assertEqual(retry_statements[0].get("exception_type"), "Exception")
        self.assertEqual(retry_statements[0].get("exception_type_resolution"), "default_exception_type")
        self.assertEqual(retry_statements[0].get("base_delay_ms"), 0)
        self.assertEqual(retry_statements[0].get("backoff_multiplier"), 1.0)
        self.assertEqual(retry_statements[0].get("retry_delay_policy_resolution"), "default_no_delay_policy")
        self.assertTrue(any("Console.WriteLine" in c and "処理を完了しました" in c for c in raw_codes))
        self.assertIn("for (var retryAttempt = 0; retryAttempt < 3; retryAttempt++)", code)
        self.assertIn("try {", code)
        self.assertNotIn("validate_plan()", code)

    def test_wrap_runtime_bridge_uses_explicit_retry_metadata(self):
        ir_tree = {
            "logic_tree": [
                {
                    "id": "step_wrap",
                    "type": "ACTION",
                    "original_text": "リトライする。",
                    "intent": "GENERAL",
                    "role": "ACTION",
                    "cardinality": "SINGLE",
                    "target_entity": "Item",
                    "output_type": "void",
                    "source_kind": None,
                    "source_ref": None,
                    "input_link": None,
                    "semantic_map": {
                        "spec_role": "WRAP",
                        "semantic_roles": {
                            "wrapper_kind": "retry",
                            "max_attempts": 5,
                            "exception_type": "IOException",
                        },
                    },
                    "children": [
                        {
                            "id": "step_display",
                            "type": "ACTION",
                            "original_text": "処理を完了しました、と表示する。",
                            "intent": "DISPLAY",
                            "role": "DISPLAY",
                            "cardinality": "SINGLE",
                            "target_entity": "string",
                            "output_type": "void",
                            "source_kind": None,
                            "source_ref": None,
                            "input_link": "step_wrap",
                            "semantic_map": {
                                "spec_role": "DISPLAY",
                                "semantic_roles": {"message": "処理を完了しました"},
                                "logic": [],
                            },
                            "children": [],
                            "else_children": [],
                        }
                    ],
                    "else_children": [],
                }
            ]
        }

        result = self.synthesizer._synthesize_from_ir_tree("RetryDisplayExplicit", ir_tree, expected_steps=1)
        statements = result.get("trace", {}).get("best_path", {}).get("statements", [])
        retry_statement = next((s for s in statements if s.get("type") == "retry"), None)
        code = result.get("code", "")

        self.assertIsNotNone(retry_statement)
        self.assertEqual(retry_statement.get("max_attempts_resolution"), "explicit_attempts")
        self.assertEqual(retry_statement.get("exception_type_resolution"), "explicit_exception_type")
        self.assertIn("retryAttempt < 5", code)
        self.assertIn("catch (IOException)", code)
        self.assertIn("Console.WriteLine", code)

    def test_wrap_runtime_bridge_preserves_explicit_backoff_policy(self):
        ir_tree = {
            "logic_tree": [
                {
                    "id": "step_wrap",
                    "type": "ACTION",
                    "original_text": "リトライする。",
                    "intent": "GENERAL",
                    "role": "ACTION",
                    "cardinality": "SINGLE",
                    "target_entity": "Item",
                    "output_type": "void",
                    "source_kind": None,
                    "source_ref": None,
                    "input_link": None,
                    "semantic_map": {
                        "spec_role": "WRAP",
                        "semantic_roles": {
                            "wrapper_kind": "retry",
                            "max_attempts": 4,
                            "base_delay_ms": 200,
                            "max_delay_ms": 1000,
                            "backoff_multiplier": 2.0,
                        },
                    },
                    "children": [
                        {
                            "id": "step_display",
                            "type": "ACTION",
                            "original_text": "処理を完了しました、と表示する。",
                            "intent": "DISPLAY",
                            "role": "DISPLAY",
                            "cardinality": "SINGLE",
                            "target_entity": "string",
                            "output_type": "void",
                            "source_kind": None,
                            "source_ref": None,
                            "input_link": "step_wrap",
                            "semantic_map": {
                                "spec_role": "DISPLAY",
                                "semantic_roles": {"message": "処理を完了しました"},
                                "logic": [],
                            },
                            "children": [],
                            "else_children": [],
                        }
                    ],
                    "else_children": [],
                }
            ]
        }

        result = self.synthesizer._synthesize_from_ir_tree("RetryDisplayBackoff", ir_tree, expected_steps=1)
        code = result.get("code", "")

        self.assertIn("retryDelayMs = 200", code)
        self.assertIn("System.Threading.Thread.Sleep(retryDelayMs);", code)
        self.assertIn("retryDelayMs = Math.Min(1000, (int)Math.Ceiling(retryDelayMs * 2.0));", code)

    def test_async_retry_blueprint_uses_task_delay_for_backoff(self):
        client = CodeBuilderClient(self.cm)
        blueprint = {
            "namespace": "Generated",
            "class_name": "RetryAsyncProcessor",
            "usings": ["System", "System.Threading.Tasks"],
            "fields": [],
            "methods": [{
                "name": "RetryAsync",
                "return_type": "Task",
                "is_async": True,
                "params": [],
                "body": [{
                    "type": "retry",
                    "max_attempts": 4,
                    "exception_type": "Exception",
                    "base_delay_ms": 200,
                    "max_delay_ms": 1000,
                    "backoff_multiplier": 2.0,
                    "body": [
                        {"type": "raw", "code": "await Task.Delay(1);"}
                    ],
                }],
            }],
            "extra_classes": [],
            "extra_code": [],
            "optimize": False,
        }

        result = client.build_code(blueprint)

        self.assertEqual(result.get("status"), "success")
        code = result.get("code", "")
        self.assertIn("public async Task RetryAsync()", code)
        self.assertIn("await Task.Delay(retryDelayMs);", code)
        self.assertIn("retryDelayMs = Math.Min(1000, (int)Math.Ceiling(retryDelayMs * 2));", code)

    def test_wrap_runtime_bridge_uses_explicit_timeout_metadata(self):
        ir_tree = {
            "logic_tree": [
                {
                    "id": "step_wrap_timeout",
                    "type": "ACTION",
                    "original_text": "5秒以内に実行する。",
                    "intent": "GENERAL",
                    "role": "ACTION",
                    "cardinality": "SINGLE",
                    "target_entity": "Item",
                    "output_type": "void",
                    "source_kind": None,
                    "source_ref": None,
                    "input_link": None,
                    "semantic_map": {
                        "spec_role": "WRAP",
                        "semantic_roles": {
                            "wrapper_kind": "timeout",
                            "timeout_ms": 5000,
                            "timeout_resolution": "explicit_timeout_ms",
                        },
                    },
                    "children": [
                        {
                            "id": "step_display",
                            "type": "ACTION",
                            "original_text": "処理を完了しました、と表示する。",
                            "intent": "DISPLAY",
                            "role": "DISPLAY",
                            "cardinality": "SINGLE",
                            "target_entity": "string",
                            "output_type": "void",
                            "source_kind": None,
                            "source_ref": None,
                            "input_link": "step_wrap_timeout",
                            "semantic_map": {
                                "spec_role": "DISPLAY",
                                "semantic_roles": {"message": "処理を完了しました"},
                                "logic": [],
                            },
                            "children": [],
                            "else_children": [],
                        }
                    ],
                    "else_children": [],
                }
            ]
        }

        result = self.synthesizer._synthesize_from_ir_tree("TimeoutDisplayExplicit", ir_tree, expected_steps=1)
        statements = result.get("trace", {}).get("best_path", {}).get("statements", [])
        timeout_statement = next((s for s in statements if s.get("type") == "timeout"), None)
        code = result.get("code", "")

        self.assertIsNotNone(timeout_statement)
        self.assertEqual(timeout_statement.get("timeout_ms"), 5000)
        self.assertEqual(timeout_statement.get("timeout_resolution"), "explicit_timeout_ms")
        self.assertIn("System.Threading.Tasks.Task.Run(() =>", code)
        self.assertIn("System.TimeSpan.FromMilliseconds(5000)", code)
        self.assertIn("System.TimeoutException(\"Operation timed out after 5000ms.\")", code)

    def test_async_timeout_blueprint_uses_wait_async(self):
        client = CodeBuilderClient(self.cm)
        blueprint = {
            "namespace": "Generated",
            "class_name": "TimeoutAsyncProcessor",
            "usings": ["System", "System.Threading.Tasks"],
            "fields": [],
            "methods": [{
                "name": "TimeoutAsync",
                "return_type": "Task",
                "is_async": True,
                "params": [],
                "body": [{
                    "type": "timeout",
                    "timeout_ms": 2500,
                    "body": [
                        {"type": "raw", "code": "await Task.Delay(1);"}
                    ],
                }],
            }],
            "extra_classes": [],
            "extra_code": [],
            "optimize": False,
        }

        result = client.build_code(blueprint)

        self.assertEqual(result.get("status"), "success")
        code = result.get("code", "")
        self.assertIn("public async Task TimeoutAsync()", code)
        self.assertIn("using var timeoutCts = new System.Threading.CancellationTokenSource(System.TimeSpan.FromMilliseconds(2500));", code)
        self.assertIn("await timeoutTask.WaitAsync(timeoutCts.Token);", code)
        self.assertIn("throw new System.TimeoutException(\"Operation timed out after 2500ms.\");", code)

    def test_wrap_runtime_bridge_uses_explicit_transaction_metadata(self):
        ir_tree = {
            "logic_tree": [
                {
                    "id": "step_wrap_tx",
                    "type": "ACTION",
                    "original_text": "トランザクションで実行する。",
                    "intent": "GENERAL",
                    "role": "ACTION",
                    "cardinality": "SINGLE",
                    "target_entity": "Item",
                    "output_type": "void",
                    "source_kind": None,
                    "source_ref": None,
                    "input_link": None,
                    "semantic_map": {
                        "spec_role": "WRAP",
                        "semantic_roles": {
                            "wrapper_kind": "transaction",
                            "transaction_resolution": "explicit_transaction_wrapper",
                        },
                    },
                    "children": [
                        {
                            "id": "step_display",
                            "type": "ACTION",
                            "original_text": "処理を完了しました、と表示する。",
                            "intent": "DISPLAY",
                            "role": "DISPLAY",
                            "cardinality": "SINGLE",
                            "target_entity": "string",
                            "output_type": "void",
                            "source_kind": None,
                            "source_ref": None,
                            "input_link": "step_wrap_tx",
                            "semantic_map": {
                                "spec_role": "DISPLAY",
                                "semantic_roles": {"message": "処理を完了しました"},
                                "logic": [],
                            },
                            "children": [],
                            "else_children": [],
                        }
                    ],
                    "else_children": [],
                }
            ]
        }

        result = self.synthesizer._synthesize_from_ir_tree("TransactionDisplayExplicit", ir_tree, expected_steps=1)
        statements = result.get("trace", {}).get("best_path", {}).get("statements", [])
        transaction_statement = next((s for s in statements if s.get("type") == "transaction"), None)
        code = result.get("code", "")

        self.assertIsNotNone(transaction_statement)
        self.assertEqual(transaction_statement.get("transaction_resolution"), "explicit_transaction_wrapper")
        self.assertIn("using var transactionScope = new System.Transactions.TransactionScope();", code)
        self.assertIn("transactionScope.Complete();", code)
        self.assertIn("Console.WriteLine", code)

    def test_async_transaction_blueprint_uses_transaction_scope_async_flow(self):
        client = CodeBuilderClient(self.cm)
        blueprint = {
            "namespace": "Generated",
            "class_name": "TransactionAsyncProcessor",
            "usings": ["System", "System.Threading.Tasks"],
            "fields": [],
            "methods": [{
                "name": "TransactionAsync",
                "return_type": "Task",
                "is_async": True,
                "params": [],
                "body": [{
                    "type": "transaction",
                    "body": [
                        {"type": "raw", "code": "await Task.Delay(1);"}
                    ],
                }],
            }],
            "extra_classes": [],
            "extra_code": [],
            "optimize": False,
        }

        result = client.build_code(blueprint)

        self.assertEqual(result.get("status"), "success")
        code = result.get("code", "")
        self.assertIn("public async Task TransactionAsync()", code)
        self.assertIn("using var transactionScope = new System.Transactions.TransactionScope(System.Transactions.TransactionScopeAsyncFlowOption.Enabled);", code)
        self.assertIn("transactionScope.Complete();", code)

    def test_filter_with_history_provenance_uses_generic_logic_path(self):
        node = {
            "id": "step_filter_history",
            "type": "ACTION",
            "intent": "LINQ",
            "role": "FILTER",
            "target_entity": "User",
            "cardinality": "COLLECTION",
            "output_type": "IEnumerable<User>",
            "semantic_map": {
                "spec_role": "FILTER",
                "semantic_roles": {
                    "predicate_resolution": "history_predicate",
                    "collection_resolution": "history_collection",
                },
                "logic": [{
                    "type": "numeric",
                    "operator": "Greater",
                    "expected_value": "100",
                    "variable_hint": "Points"
                }]
            }
        }
        path = self._base_path()
        path["type_to_vars"] = {
            "IEnumerable<User>": [{"var_name": "users", "role": "data", "node_id": "step_1", "target_entity": "User"}],
        }
        path["poco_defs"] = {"User": {"Points": "int"}}
        results = self.synthesizer.action_synthesizer.process_node(node, path)
        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertTrue(any(".Where(" in c and "Points > 100" in c for c in raw_codes))
        self.assertFalse(any("Resolve weak FILTER provenance" in c for c in raw_codes))

    def test_ambiguous_calculate_stays_conservative_downstream(self):
        node = {
            "id": "step_calc_ambiguous",
            "type": "ACTION",
            "intent": "CALC",
            "role": "CALC",
            "target_entity": "Item",
            "cardinality": "SINGLE",
            "output_type": "decimal",
            "semantic_map": {
                "spec_role": "CALCULATE",
                "semantic_roles": {
                    "target_hint": "Total",
                    "property": "Total",
                    "target_entity": "Item",
                    "entity_resolution": "ambiguous"
                },
                "logic": []
            }
        }
        path = self._base_path()
        path["active_scope_item"] = "item"
        path["type_to_vars"] = {
            "Order": [{"var_name": "order", "role": "data", "node_id": "step_1", "target_entity": "Order"}],
            "Invoice": [{"var_name": "invoice", "role": "data", "node_id": "step_2", "target_entity": "Invoice"}],
        }
        path["poco_defs"] = {
            "Order": {"Total": "decimal", "Id": "int"},
            "Invoice": {"Total": "decimal", "Number": "string"},
        }

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertTrue(any("Resolve ambiguous CALCULATE target for Total" in c for c in raw_codes))
        self.assertFalse(any(".Total" in c for c in raw_codes))

    def test_history_fallback_calculate_uses_exact_target_without_cross_entity_fallback(self):
        node = {
            "id": "step_calc_history",
            "type": "ACTION",
            "intent": "CALC",
            "role": "CALC",
            "target_entity": "Order",
            "cardinality": "SINGLE",
            "output_type": "decimal",
            "semantic_map": {
                "spec_role": "CALCULATE",
                "semantic_roles": {
                    "target_hint": "Total",
                    "property": "Total",
                    "target_entity": "Order",
                    "entity_resolution": "history_fallback"
                },
                "logic": []
            }
        }
        path = self._base_path()
        path["active_scope_item"] = "order"
        path["type_to_vars"] = {
            "Order": [{"var_name": "order", "role": "data", "node_id": "step_1", "target_entity": "Order"}],
            "Invoice": [{"var_name": "invoice", "role": "data", "node_id": "step_2", "target_entity": "Invoice"}],
        }
        path["poco_defs"] = {
            "Invoice": {"Total": "decimal", "Number": "string"},
            "Order": {"Total": "decimal", "Id": "int"},
        }

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertFalse(any("Resolve ambiguous CALCULATE target" in c for c in raw_codes))
        self.assertTrue(any("order.Total" in c for c in raw_codes))

    def test_calculate_input_link_metadata_prefers_exact_upstream_var_over_active_scope(self):
        node = {
            "id": "step_calc_exact_source",
            "type": "ACTION",
            "intent": "CALC",
            "role": "CALC",
            "target_entity": "Order",
            "cardinality": "SINGLE",
            "output_type": "decimal",
            "semantic_map": {
                "spec_role": "CALCULATE",
                "semantic_roles": {
                    "target_hint": "Total",
                    "property": "Total",
                    "target_entity": "Order",
                    "entity_resolution": "history_fallback",
                    "calculate_source_node_id": "step_fetch_order",
                    "calculate_source_resolution": "input_link_var",
                },
                "logic": [],
            }
        }
        path = self._base_path()
        path["active_scope_item"] = "latestOrder"
        path["type_to_vars"] = {
            "Order": [
                {"var_name": "fetchedOrder", "role": "data", "node_id": "step_fetch_order", "target_entity": "Order"},
                {"var_name": "latestOrder", "role": "data", "node_id": "step_other_order", "target_entity": "Order"},
            ],
        }
        path["poco_defs"] = {
            "Order": {"Total": "decimal", "Id": "int"},
        }

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertTrue(any("fetchedOrder.Total" in c for c in raw_codes))
        self.assertFalse(any("latestOrder.Total" in c for c in raw_codes))

    def test_calculate_default_scope_metadata_stays_with_active_scope(self):
        node = {
            "id": "step_calc_default_scope",
            "type": "ACTION",
            "intent": "CALC",
            "role": "CALC",
            "target_entity": "Order",
            "cardinality": "SINGLE",
            "output_type": "decimal",
            "semantic_map": {
                "spec_role": "CALCULATE",
                "semantic_roles": {
                    "target_hint": "Total",
                    "property": "Total",
                    "target_entity": "Order",
                    "entity_resolution": "history_fallback",
                    "calculate_source_resolution": "default_scope_var",
                },
                "logic": [],
            }
        }
        path = self._base_path()
        path["active_scope_item"] = "currentOrder"
        path["type_to_vars"] = {
            "Order": [
                {"var_name": "previousOrder", "role": "data", "node_id": "step_prev_order", "target_entity": "Order"},
                {"var_name": "currentOrder", "role": "data", "node_id": "step_current_order", "target_entity": "Order"},
            ],
        }
        path["poco_defs"] = {
            "Order": {"Total": "decimal", "Id": "int"},
        }

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertTrue(any("currentOrder.Total" in c for c in raw_codes))
        self.assertFalse(any("previousOrder.Total" in c for c in raw_codes))

    def test_calculate_explicit_target_without_schema_upgrade_stays_local_result(self):
        node = {
            "id": "step_calc_explicit_target",
            "type": "ACTION",
            "intent": "CALC",
            "role": "CALC",
            "target_entity": "Item",
            "cardinality": "SINGLE",
            "output_type": "decimal",
            "semantic_map": {
                "spec_role": "CALCULATE",
                "semantic_roles": {
                    "target_hint": "結果",
                    "property": "結果",
                    "target_entity": "Item",
                    "entity_resolution": "history_fallback",
                    "calculate_target_resolution": "explicit_target",
                    "calculate_source_resolution": "default_scope_var",
                },
                "logic": [],
            }
        }
        path = self._base_path()
        path["active_scope_item"] = "currentOrder"
        path["type_to_vars"] = {
            "Order": [
                {"var_name": "currentOrder", "role": "data", "node_id": "step_current_order", "target_entity": "Order"},
            ],
        }
        path["poco_defs"] = {
            "Order": {"Total": "decimal", "Id": "int"},
        }

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertTrue(any("Resolve weak CALCULATE target for 結果" in c for c in raw_codes))
        self.assertFalse(any(".結果" in c for c in raw_codes))
        self.assertFalse(any(".Total =" in c for c in raw_codes))

    def test_return_literal_metadata_overrides_latest_typed_variable(self):
        node = {
            "id": "step_return_true",
            "type": "ACTION",
            "intent": "RETURN",
            "role": "RETURN",
            "target_entity": "bool",
            "cardinality": "SINGLE",
            "output_type": "bool",
            "semantic_map": {
                "spec_role": "RETURN",
                "semantic_roles": {
                    "return_value": "true",
                    "return_value_resolution": "literal_boolean",
                },
                "logic": [],
            },
        }
        path = self._base_path()
        path["method_return_type"] = "bool"
        path["type_to_vars"] = {
            "bool": [{"var_name": "isValid", "role": "data", "node_id": "step_1", "target_entity": "bool"}],
        }

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertTrue(any("return true;" in c for c in raw_codes))
        self.assertFalse(any("return isValid;" in c for c in raw_codes))

    def test_return_null_metadata_overrides_latest_object_variable(self):
        node = {
            "id": "step_return_null",
            "type": "ACTION",
            "intent": "RETURN",
            "role": "RETURN",
            "target_entity": "User",
            "cardinality": "SINGLE",
            "output_type": "User",
            "semantic_map": {
                "spec_role": "RETURN",
                "semantic_roles": {
                    "return_value": "null",
                    "return_value_resolution": "literal_null",
                },
                "logic": [],
            },
        }
        path = self._base_path()
        path["method_return_type"] = "User"
        path["type_to_vars"] = {
            "User": [{"var_name": "user", "role": "data", "node_id": "step_1", "target_entity": "User"}],
        }

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertTrue(any("return null;" in c for c in raw_codes))
        self.assertFalse(any("return user;" in c for c in raw_codes))

    def test_return_input_link_metadata_prefers_exact_upstream_var_over_latest_type_var(self):
        node = {
            "id": "step_return_user",
            "type": "ACTION",
            "intent": "RETURN",
            "role": "RETURN",
            "target_entity": "User",
            "cardinality": "SINGLE",
            "output_type": "User",
            "semantic_map": {
                "spec_role": "RETURN",
                "semantic_roles": {
                    "return_source_node_id": "step_fetch_user",
                    "return_value_resolution": "input_link_var",
                },
                "logic": [],
            },
        }
        path = self._base_path()
        path["method_return_type"] = "User"
        path["type_to_vars"] = {
            "User": [
                {"var_name": "fetchedUser", "role": "data", "node_id": "step_fetch_user", "target_entity": "User"},
                {"var_name": "transformedUser", "role": "data", "node_id": "step_transform_user", "target_entity": "User"},
            ],
        }

        results = self.synthesizer.action_synthesizer.process_node(node, path)

        self.assertTrue(results)
        raw_codes = self._collect_all_raw_codes(results[0])
        self.assertTrue(any("return fetchedUser;" in c for c in raw_codes))
        self.assertFalse(any("return transformedUser;" in c for c in raw_codes))


if __name__ == '__main__':
    unittest.main()
