# -*- coding: utf-8 -*- 
# src/test_generator/test_generator.py

import os
import json
import ast
import re
from typing import Dict, List, Any, Optional

class TestGenerator:
    """テストケース生成を支援するクラス (解説コメント・ブリッジ対応版)"""
    
    def __init__(self, workspace_root: str = ".", knowledge_base=None):
        self.workspace_root = workspace_root
        self.ukb = knowledge_base
        self.templates = self._load_templates()
        self.current_analysis_data = None # ナレッジグラフを一時保持

    def _load_test_config(self) -> Dict[str, Any]:
        if self.ukb and hasattr(self.ukb, "get"):
            data = self.ukb.get("test_generator", {})
            if isinstance(data, dict):
                return data
        # Fallback to canonical knowledge file if UKB not provided
        try:
            path = os.path.join(self.workspace_root, "resources", "canonical_knowledge.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cfg = data.get("test_generator", {})
                if isinstance(cfg, dict):
                    return cfg
        except Exception:
            pass
        return {}
    
    def _load_templates(self) -> Dict[str, str]:
        t = {}
        # プレースホルダーを含むテンプレート
        t['csharp_file'] = 'using Xunit;\nusing System;\nusing System.Collections.Generic;\nusing System.Threading.Tasks;\nusing NSubstitute;\n{extra_usings}\n\nnamespace {namespace}.Tests\n{{\n    public class {class_name}Tests\n    {{\n{test_methods}\n    }}\n}}'
        t['csharp_method'] = '\n        [Fact]\n        public void {method_name}_ShouldReturnExpectedValue_When{condition}()\n        {{\n            // Arrange\n            // {original_condition}\n            {arrange_code}\n            \n            // Act\n            {act_code}\n            \n            // Assert\n            {assert_code}\n        }}\n'
        return t

    def _generate_minimal_code(self, requirement: Dict[str, Any], language: str) -> str:
        """要求に基づいて最小限のスタブコードを生成"""
        desc = requirement.get('description', '')
        # クラス名の推測
        class_name = "GeneratedClass"
        m = re.search(r'(\w+)(?:クラス|Service|Processor)', desc)
        if m: class_name = m.group(1)
        
        if language == 'csharp':
            return f"using System;\n\nnamespace Generated\n{{\n    public class {class_name}\n    {{\n        // TODO: Implement based on requirements\n    }}\n}}"
        elif language == 'python':
            return f"class {class_name}:\n    def __init__(self):\n        pass"
        return ""

    def _normalize_identifier(self, text: str) -> str:
        safe = []
        for ch in str(text or ""):
            if ch.isalnum() or ch == "_":
                safe.append(ch)
            else:
                safe.append("_")
        normalized = "".join(safe).strip("_")
        return normalized if normalized else "Scenario"

    def _extract_class_name_from_module(self, module_name: str, fallback: str) -> str:
        if not module_name:
            return fallback
        text = str(module_name)
        marker = "(Class:"
        start = text.find(marker)
        if start == -1:
            return fallback
        start += len(marker)
        end = text.find(")", start)
        if end == -1:
            end = len(text)
        candidate = text[start:end].strip()
        filtered = []
        for ch in candidate:
            if ch.isalnum() or ch == "_":
                filtered.append(ch)
        name = "".join(filtered)
        return name if name else fallback

    def generate_service_tests(self, test_context: Dict[str, Any], root_namespace: str) -> Dict[str, Any]:
        """Generate CRUD-style service tests from structured context."""
        try:
            from src.test_generator.service_test_generator import render_service_tests
            if not test_context or not root_namespace:
                return {"status": "error", "message": "missing_context"}
            content = render_service_tests(test_context, root_namespace)
            return {"status": "success", "content": content}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def build_service_test_context(
        self,
        service_name: str,
        repo_name: str,
        entity_name: str,
        create_dto: str,
        entity_plural: str,
        crud_template: Dict[str, Any],
        validation_rules: Dict[str, List[str]],
        field_types: Dict[str, str],
        id_type: str,
        entity_fields: List[str],
        test_cases: Dict[str, List[Dict[str, str]]] | None = None,
    ) -> Dict[str, str]:
        from src.test_generator.service_test_builder import build_service_test_context
        return build_service_test_context(
            service_name=service_name,
            repo_name=repo_name,
            entity_name=entity_name,
            create_dto=create_dto,
            entity_plural=entity_plural,
            crud_template=crud_template,
            validation_rules=validation_rules,
            field_types=field_types,
            id_type=id_type,
            entity_fields=entity_fields,
            test_cases=test_cases,
        )

    def generate_tests(
        self,
        mode: str,
        source_file: str = None,
        language: str = "csharp",
        analysis_output_path: str = None,
        output_dir: str = None,
        design_path: str = None,
        test_context: Dict[str, Any] | None = None,
        root_namespace: str | None = None,
    ) -> Dict[str, Any]:
        if mode == "source":
            if not source_file:
                return {"status": "error", "message": "missing_source_file"}
            return self._generate_test_cases_impl(source_file, language, analysis_output_path, output_dir)
        if mode == "design":
            if not design_path:
                return {"status": "error", "message": "missing_design_path"}
            return self._generate_tests_from_design_impl(design_path, source_file)
        if mode == "service":
            return self.generate_service_tests(test_context or {}, root_namespace or "")
        return {"status": "error", "message": f"unknown_mode:{mode}"}

    def generate_test_cases(self, source_file: str, language: str = 'csharp', analysis_output_path: str = None, output_dir: str = None) -> Dict[str, Any]:
        return self.generate_tests(
            mode="source",
            source_file=source_file,
            language=language,
            analysis_output_path=analysis_output_path,
            output_dir=output_dir,
        )

    def _generate_test_cases_impl(self, source_file: str, language: str = 'csharp', analysis_output_path: str = None, output_dir: str = None) -> Dict[str, Any]:
        try:
            if not os.path.exists(source_file): return {'status': 'error', 'message': 'Source not found'}
            
            if language == 'csharp' and analysis_output_path:
                analysis = self._analyze_from_roslyn(source_file, analysis_output_path)
            else:
                analysis = self._analyze_source_code(source_file, language)
            
            if analysis['status'] != 'success': return analysis
            
            if not output_dir: output_dir = os.path.join(self.workspace_root, 'tests', 'generated')
            os.makedirs(output_dir, exist_ok=True)
            
            test_cases = []
            generated_files = []
            
            for class_info in analysis.get('classes', []):
                # 名前空間の決定 (クラスの FullName から取得)
                full_name = class_info.get('full_name', f"Generated.{class_info['name']}")
                ns = class_info.get('namespace') or (" ".join(full_name.split('.')[:-1]) if '.' in full_name else "Generated")
                class_info['namespace'] = ns

                method_codes = []
                class_test_cases = []
                for m in class_info.get('methods', []):
                    for scenario in m.get('test_scenarios', []):
                        m_code = self._generate_method_test_code(class_info, m, scenario, language)
                        if m_code:
                            method_codes.append(m_code)
                            class_test_cases.append({
                                'test_name': f"{class_info['name']}_{m['name']}_{scenario['condition']}",
                                'code': m_code,
                                'scenario_type': scenario.get('type', 'happy_path'),
                                'description': f"Test for {m['name']} with condition {scenario['condition']}"
                            })
                
                if method_codes:
                    if language == 'csharp':
                        full_code = self.templates['csharp_file'].format(
                            namespace=ns,
                            extra_usings=f"using {ns};" if ns != "Generated" and ns != "Generated.Tests" else "",
                            class_name=class_info['name'], 
                            test_methods=''.join(method_codes)
                        )
                        output_file = os.path.join(output_dir, f"Test_{class_info['name']}.cs")
                    else: # Python
                        full_code = f"import unittest\nfrom {os.path.basename(source_file).replace('.py', '')} import {class_info['name']}\n\nclass Test{class_info['name']}(unittest.TestCase):\n" + "".join(method_codes)
                        output_file = os.path.join(output_dir, f"test_{class_info['name'].lower()}.py")

                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(full_code)
                    generated_files.append(output_file)
                    
                    # 統合テストは 'code' フィールドにファイル全体が含まれていることを期待している場合がある
                    for tc in class_test_cases:
                        tc['code'] = full_code
                    test_cases.extend(class_test_cases)
            
            return {
                'status': 'success', 
                'test_cases': test_cases, 
                'generated_files': generated_files,
                'analysis': analysis,
                'message': f"{len(generated_files)} 個のオブジェクトに対して汎用テストを生成しました。"
            }
        except Exception as e: return {'status': 'error', 'message': str(e)}

    def _generate_method_test_code(self, class_info, m_info, scenario, lang):
        if lang == 'csharp':
            from src.advanced_tdd.dummy_factory import DummyDataFactory
            # 解析データを渡してファクトリを初期化
            factory = DummyDataFactory(analysis_results=self.current_analysis_data)
            
            is_property = m_info.get('is_property', False)
            params = self._parse_parameters(m_info['parameters'])
            is_static = 'static' in class_info.get('modifiers', [])
            
            # コンストラクタ引数/インスタンス化の準備
            arrange = []
            if not is_static:
                constructor_params = class_info.get('constructor_parameters', [])
                ctor_args = []
                for cp in constructor_params:
                    p_name = cp.get('name', 'arg')
                    p_type = cp.get('type', 'object')
                    val = self._guess_value_by_type(p_type, p_name, None)
                    arrange.append(f"var {p_name} = {val};")
                    ctor_args.append(p_name)
                # インスタンス化
                arrange.append(f"var target = new {class_info['name']}({', '.join(ctor_args)});")
            
            # メソッドパラメータの準備
            param_names = []
            for p_name, p_type in params:
                val = self._guess_value_by_type(p_type, p_name, scenario.get('original_condition'))
                arrange.append(f"var {p_name} = {val};")
                param_names.append(p_name)
            
            # Act (静的かインスタンスか、プロパティかメソッドかで切り分け)
            is_method_static = 'static' in m_info.get('modifiers', [])
            call_target = class_info['name'] if (is_static or is_method_static) else "target"
            
            # 非同期判定
            return_type = m_info.get('return_type', '')
            is_async = 'Task' in return_type
            await_prefix = "await " if is_async else ""

            if is_property:
                act_call = f"{call_target}.{m_info['name']}"
            else:
                act_call = f"{call_target}.{m_info['name']}({', '.join(param_names)})"
            
            # 統一された Act コード生成 (二重定義を防止)
            if act_call.startswith("var result ="):
                act_code = f"{await_prefix}{act_call};"
            else:
                act_code = f"var result = {await_prefix}{act_call};"
            
            expected = scenario.get('expected_behavior', 'Success')
            expected_val = f'"{expected}"' if isinstance(expected, str) and not expected.isdigit() and expected not in ['true', 'false', 'null'] else str(expected)
            
            assert_code = 'Assert.NotNull(result);' if scenario['type'] == 'property_access' else f'Assert.Equal({expected_val}, result);'
            
            # テンプレートの Fact を必要に応じて async Task に変換
            method_template = self.templates['csharp_method']
            if is_async:
                method_template = method_template.replace('public void', 'public async Task')

            cfg = self._load_test_config()
            default_original = cfg.get("default_original_condition", "デフォルト動作または外部呼び出し")
            return method_template.format(
                method_name=m_info['name'], 
                condition=scenario['condition'],
                original_condition=scenario.get('original_condition', default_original),
                arrange_code='\n            '.join(arrange), 
                act_code=act_code, 
                assert_code=assert_code
            )
        elif lang == 'python':
            # Python 用の簡易実装
            m_name = m_info['name']
            cond = scenario['condition']
            return f"\n    def test_{m_name}_{cond}(self):\n        # Arrange\n        target = {class_info['name']}()\n        \n        # Act\n        # TODO: parameters\n        result = target.{m_name}()\n        \n        # Assert\n        self.assertIsNotNone(result)\n"
        return ''

    def _parse_parameters(self, p_str):
        if not p_str: return []
        # C#の属性のみを除去
        clean_p = re.sub(r'\[[A-Z]\w*(\([^)]*\))?\]', '', p_str).strip()
        if not clean_p: return []
        
        params = []
        for p in clean_p.split(','):
            parts = p.strip().split()
            if len(parts) >= 2:
                name = parts[-1]
                type_name = " ".join(parts[:-1]) 
                params.append((name, type_name))
        return params

    def _guess_value_by_type(self, p_type, p_name, cond):
        from src.advanced_tdd.dummy_factory import DummyDataFactory
        factory = DummyDataFactory()
        cfg = self._load_test_config()
        length_markers = cfg.get("length_markers", ["Length", "Count"])
        null_or_empty_markers = cfg.get("string_null_or_empty_markers", ["string.IsNullOrEmpty"])
        non_empty_markers = cfg.get("non_empty_markers", [">", "!=", "!"])
        empty_markers = cfg.get("empty_markers", ["==", "string.IsNullOrEmpty"])
        
        # 1. 分岐条件 (cond) に基づく推論
        if cond:
            # 文字列の直接比較 (e.g., input == "target")
            m_str = re.search(fr'{{{p_name}}}\s*==\s*["](.*?)["]', cond)
            if m_str: return f'"{m_str.group(1)}"'
            
            # 数値比較
            m_num = re.search(fr'{{{p_name}}}\s*(>=|<=|>|<|==)\s*(\d+)', cond)
            if m_num:
                op, val = m_num.group(1), int(m_num.group(2))
                if op in ['>=', '==']: return str(val)
                if op == '>': return str(val + 1)
                if '<' in op: return str(val - 1)
                if op == '<=': return str(val)

            # 文字列やリストの長さ
            if any(f'{p_name}.{m}' in cond for m in length_markers) or any(f'{m}({p_name})' in cond for m in null_or_empty_markers):
                if any(m in cond for m in non_empty_markers): # !string.IsNullOrEmpty(x)
                    if 'string' in p_type.lower(): return '"non-empty"'
                    if '[]' in p_type or 'List' in p_type:
                        return factory.generate_instantiation(p_type) 
                if any(m in cond for m in empty_markers): # string.IsNullOrEmpty(x)
                    if 'string' in p_type.lower(): return '""'
                    if '[]' in p_type or 'List' in p_type:
                        base_type = p_type.replace('[]', '').replace('List<', '').replace('>', '').split('.')[-1]
                        if '[]' in p_type: return f"new {base_type}[0]"
                        return f"new List<{base_type}>()"

        # 2. 型に基づくデフォルト生成 (Factoryに委譲)
        return factory.generate_instantiation(p_type)

    def _analyze_from_roslyn(self, source_file, output_path):
        try:
            with open(os.path.join(output_path, 'manifest.json'), 'r', encoding='utf-8') as f: 
                manifest = json.load(f)
            
            source_abs = os.path.normpath(os.path.abspath(source_file).lower())
            analysis_classes = []
            
            for obj in manifest.get('objects', []):
                obj_file = os.path.normpath(os.path.abspath(obj.get('filePath', '')).lower())
                if obj.get('type') in ['Class', 'Record', 'Struct'] and obj_file == source_abs:
                    with open(os.path.join(output_path, 'details', f"{obj['id']}.json"), 'r', encoding='utf-8') as df: 
                        detail = json.load(df)
                    
                    methods = []
                    # 1. メソッドの処理 (Publicのみ)
                    for m in detail.get('methods', []):
                        if m.get('accessibility', '').lower() != 'public':
                            continue
                            
                        params = ", ".join([f"{p['type']} {p['name']}" for p in m.get('parameters', [])])
                        scenarios = []
                        cfg = self._load_test_config()
                        logic_prefix = cfg.get("logic_driven_prefix", {"condition_prefix": "Branch", "expected_prefix": "Expected"})
                        for i, b in enumerate(m.get('branches', [])):
                            scenarios.append({
                                'type': 'logic_driven',
                                'condition': f"{logic_prefix.get('condition_prefix', 'Branch')}{i}",
                                'expected_behavior': f"{logic_prefix.get('expected_prefix', 'Expected')}{i}",
                                'original_condition': b['condition']
                            })
                        if not scenarios:
                            fallback = cfg.get("fallback_scenario", {'type': 'happy_path', 'condition': 'Default', 'expected_behavior': 'Success'})
                            scenarios.append(fallback.copy())
                        
                        methods.append({
                            'name': m['name'], 
                            'return_type': m['returnType'], 
                            'parameters': params, 
                            'test_scenarios': scenarios,
                            'is_property': False,
                            'modifiers': m.get('modifiers', [])
                        })
                    
                    # 2. プロパティの処理
                    for prop in detail.get('properties', []):
                        cfg = self._load_test_config()
                        prop_scenario = cfg.get("property_scenario", {'type': 'property_access', 'condition': 'Getter', 'expected_behavior': 'NotNull'})
                        methods.append({
                            'name': prop['name'],
                            'return_type': prop['type'],
                            'parameters': '',
                            'test_scenarios': [prop_scenario.copy()],
                            'is_property': True
                        })

                    if methods:
                        # コンストラクタ引数
                        ctor_params = []
                        if detail.get('constructors'):
                            public_ctor = next((c for c in detail['constructors'] if c.get('accessibility') == 'Public'), detail['constructors'][0])
                            ctor_params = public_ctor.get('parameters', [])

                        analysis_classes.append({
                            'name': obj['fullName'].split('.')[-1], 
                            'full_name': obj['fullName'],
                            'methods': methods,
                            'constructor_parameters': ctor_params,
                            'modifiers': detail.get('modifiers', [])
                        })
            
            if analysis_classes:
                return {'status': 'success', 'classes': analysis_classes, 'language': 'csharp'}
            return {'status': 'error', 'message': f'No relevant objects found in {source_file}'}
        except Exception as e: return {'status': 'error', 'message': str(e)}

    def _analyze_source_code(self, source_file, language):
        from src.advanced_tdd.ast_analyzer import ASTAnalyzer
        analyzer = ASTAnalyzer()
        
        with open(source_file, 'r', encoding='utf-8') as f:
            code = f.read()
            
        result = analyzer.analyze_code_structure(code, language)
        if 'error' in result:
            return {'status': 'error', 'message': result['error']}
            
        structure = result.get('structure', {})
        # TestGenerator が期待する形式に変換
        analysis_classes = []
        
        # Python の場合は 'classes', C# の場合は 'classes'
        classes = structure.get('classes', [])
        for cls in classes:
            methods = []
            # C# の場合
            if language == 'csharp':
                for m in cls.get('methods', []):
                    cfg = self._load_test_config()
                    scenarios = [s.copy() for s in cfg.get("default_scenarios", [
                        {'type': 'happy_path', 'condition': 'Default', 'expected_behavior': 'Success'},
                        {'type': 'boundary', 'condition': 'Boundary', 'expected_behavior': 'Success'},
                        {'type': 'null_empty', 'condition': 'NullOrEmpty', 'expected_behavior': 'Success'},
                        {'type': 'exception', 'condition': 'ErrorCase', 'expected_behavior': 'Exception'}
                    ])]
                    methods.append({
                        'name': m['name'],
                        'return_type': m.get('return_type', 'void'),
                        'parameters': m.get('parameters', ''),
                        'test_scenarios': scenarios,
                        'is_property': False,
                        'modifiers': [m.get('access_modifier', 'public')]
                    })
                for p in cls.get('properties', []):
                    cfg = self._load_test_config()
                    prop_scenario = cfg.get("property_scenario", {'type': 'property_access', 'condition': 'Getter', 'expected_behavior': 'NotNull'})
                    methods.append({
                        'name': p['name'],
                        'return_type': p.get('type', 'object'),
                        'parameters': '',
                        'test_scenarios': [prop_scenario.copy()],
                        'is_property': True,
                        'modifiers': [p.get('access_modifier', 'public')]
                    })
            else: # Python
                # cls は辞書で 'methods' キーにメソッド名のリストを持っている
                for m_name in cls.get('methods', []):
                    cfg = self._load_test_config()
                    scenarios = [s.copy() for s in cfg.get("default_scenarios", [
                        {'type': 'happy_path', 'condition': 'Default', 'expected_behavior': 'Success'},
                        {'type': 'boundary', 'condition': 'Boundary', 'expected_behavior': 'Success'},
                        {'type': 'null_empty', 'condition': 'NullOrEmpty', 'expected_behavior': 'Success'},
                        {'type': 'exception', 'condition': 'ErrorCase', 'expected_behavior': 'Exception'}
                    ])]
                    methods.append({
                        'name': m_name,
                        'return_type': 'Any',
                        'parameters': '',
                        'test_scenarios': scenarios,
                        'is_property': False,
                        'modifiers': []
                    })
            
            analysis_classes.append({
                'name': cls['name'],
                'full_name': f"{cls.get('namespace')}.{cls['name']}" if cls.get('namespace') else cls['name'],
                'namespace': cls.get('namespace') or structure.get('namespace'),
                'methods': methods,
                'constructor_parameters': [],
                'modifiers': [cls.get('access_modifier', 'public')]
            })
            
        if analysis_classes:
            return {'status': 'success', 'classes': analysis_classes, 'language': language}
            
    def generate_tests_from_design(self, design_path: str, source_path: str = None) -> Dict[str, Any]:
        return self.generate_tests(mode="design", design_path=design_path, source_file=source_path)

    def _generate_tests_from_design_impl(self, design_path: str, source_path: str = None) -> Dict[str, Any]:
        """設計書(.design.md)のTest CasesからPythonユニットテストを生成する"""
        try:
            from ..utils.design_doc_parser import DesignDocParser
            parser = DesignDocParser(knowledge_base=self.ukb)
            design_data = parser.parse_file(design_path)
            
            test_cases = design_data.get('test_cases', [])
            if not test_cases:
                return {'status': 'warning', 'message': 'No test cases found in design document.'}
            
            module_name = design_data.get('module_name', 'UnknownModule')
            # クラス名の決定ロジック
            # 1. ヘッダーに (Class: Name) があればそれを使う
            # 2. ファイル名から推測
            base_name = os.path.basename(design_path).replace('.design.md', '')
            class_name = "".join(x.title() for x in base_name.split('_'))
            
            class_name = self._extract_class_name_from_module(module_name, class_name)
            
            # ソースパスが指定されていない場合、同じディレクトリの.pyを探す
            if not source_path:
                source_path = design_path.replace('.design.md', '.py')
            
            # Pythonコード生成
            lines = [
                "# -*- coding: utf-8 -*-",
                "import unittest",
                "import sys",
                "import os",
                "from unittest.mock import MagicMock, Mock",
                "",
                "# Add project root to path",
                f"sys.path.append(os.path.abspath('{self.workspace_root.replace(os.path.sep, '/')}') )",
                "",
                f"# Target Module: {source_path}",
                f"from {os.path.relpath(os.path.dirname(source_path), self.workspace_root).replace(os.path.sep, '.')}.{base_name} import {class_name}",
                "",
                f"class Test{class_name}Spec(unittest.TestCase):",
                "    \"\"\"Specification-based tests generated from design document\"\"\"",
                "",
                "    def setUp(self):",
                "        # Default initialization (overridden if init_args present)",
                "        try:",
                f"            self.target = {class_name}()",
                "        except:",
                "            self.target = None # Defer initialization",
                "",
                "    def assertDictSubset(self, expected, actual):",
                "        \"\"\"Recursively checks if expected is a subset of actual.\"\"\"",
                "        if isinstance(expected, dict) and isinstance(actual, dict):",
                "            for k, v in expected.items():",
                "                self.assertIn(k, actual)",
                "                self.assertDictSubset(v, actual[k])",
                "        elif isinstance(expected, list) and isinstance(actual, list):",
                "            self.assertEqual(len(expected), len(actual))",
                "            for i, item in enumerate(expected):",
                "                self.assertDictSubset(item, actual[i])",
                "        else:",
                "             # Primitive comparison with tolerance for floats",
                "            if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):",
                "                self.assertAlmostEqual(actual, expected, delta=0.1)",
                "            else:",
                "                self.assertEqual(actual, expected)",
                ""
            ]
            
            for i, case in enumerate(test_cases):
                scenario = case.get('scenario', f'Scenario{i}')
                safe_scenario = self._normalize_identifier(scenario)
                
                input_str = case.get('input', '').strip()
                expected_str = case.get('expected', '').strip()
                
                # JSON判定
                input_json = None
                try:
                    import json
                    input_json = json.loads(input_str)
                except:
                    input_json = None

                lines.append(f"    def test_{safe_scenario}(self):")
                lines.append(f"        # Scenario: {scenario}")
                
                if input_json:
                    # 汎用 JSON 形式の場合
                    init_args = input_json.get('init_args', {})
                    method_name = input_json.get('target_method', 'calculate')
                    method_args = input_json.get('args', {})
                    
                    lines.append(f"        # Arrange")
                    
                    # 1. Prepare Mocks
                    mock_config = input_json.get('mocks', {})
                    mock_arg_names = []
                    for mock_name, props in mock_config.items():
                        lines.append(f"        {mock_name} = MagicMock()")
                        for k, v in props.items():
                            lines.append(f"        {mock_name}.{k} = {repr(v)}")
                        mock_arg_names.append(mock_name)

                    # 2. Build Init Args
                    # init_args in JSON should contain primitives, AND potentially references to mocks
                    # Convention: if init_args contains "key": "$mock:name", we use the mock variable.
                    # Or simpler: if we rely on specific init signature, we might need more metadata.
                    # For now, let's mix: init_args (primitives) + mocks (implicit/explicit).
                    
                    # 2. Build Init Args
                    # init_args in JSON should contain primitives, AND potentially references to mocks
                    # Convention: if init_args contains "key": "$mock:name", we use the mock variable.
                    
                    # Generic dependency resolution
                    final_init_args = []
                    
                    # Try to get constructor info from source if available
                    constructor_params = []
                    if source_path and os.path.exists(source_path):
                        try:
                            from src.advanced_tdd.ast_analyzer import ASTAnalyzer
                            analyzer = ASTAnalyzer()
                            with open(source_path, 'r', encoding='utf-8') as f:
                                code = f.read()
                            lang = 'python' if source_path.endswith('.py') else 'csharp'
                            res = analyzer.analyze_code_structure(code, lang)
                            if res.get('status') == 'success':
                                struct = res.get('structure', {})
                                for cls in struct.get('classes', []):
                                    if cls['name'] == class_name:
                                        # Python AST analyzer currently lists methods in 'methods' list
                                        # We need to find __init__
                                        if lang == 'python':
                                            # We need to re-parse or extract __init__ args
                                            # Simple heuristic: find 'def __init__' line
                                            tree = ast.parse(code)
                                            for node in ast.walk(tree):
                                                if isinstance(node, ast.ClassDef) and node.name == class_name:
                                                    for item in node.body:
                                                        if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                                                            constructor_params = [arg.arg for arg in item.args.args if arg.arg != 'self']
                                                            break
                        except:
                            pass

                    if constructor_params:
                        # If we have constructor info, try to fill it
                        for p_name in constructor_params:
                            if p_name in mock_arg_names:
                                final_init_args.append(p_name)
                            elif p_name in init_args:
                                val = init_args[p_name]
                                if isinstance(val, str) and val.startswith('$mock:'):
                                    mock_ref = val.split(':')[1]
                                    final_init_args.append(mock_ref)
                                else:
                                    final_init_args.append(repr(val))
                            else:
                                # Auto-mock if it looks like a dependency
                                if p_name.endswith(('_executor', '_manager', '_engine', '_analyzer', '_factory')):
                                    lines.append(f"        {p_name} = MagicMock()")
                                    mock_arg_names.append(p_name)
                                    final_init_args.append(p_name)
                                else:
                                    final_init_args.append("None")
                        final_init_code = ", ".join(final_init_args)
                    else:
                        # Fallback to init_args dictionary plus any mocks not already included
                        init_parts = []
                        included_mocks = set()
                        for k, v in init_args.items():
                            if isinstance(v, str) and v.startswith('$mock:'):
                                mock_ref = v.split(':')[1]
                                init_parts.append(f"{k}={mock_ref}")
                                included_mocks.add(mock_ref)
                            elif k in mock_arg_names:
                                init_parts.append(f"{k}={k}")
                                included_mocks.add(k)
                            else:
                                init_parts.append(f"{k}={repr(v)}")
                        
                        # Add remaining mocks that might be expected as positional or keyword args
                        for m_name in mock_arg_names:
                            if m_name not in included_mocks:
                                init_parts.append(f"{m_name}={m_name}")
                                
                        final_init_code = ", ".join(init_parts)
                    
                    lines.append(f"        self.target = {class_name}({final_init_code})")
                    
                    # Setup Code Injection
                    setup_code = input_json.get('setup_code', [])
                    if setup_code:
                        lines.append(f"        # Custom Setup from Design Doc")
                        for code_line in setup_code:
                            lines.append(f"        {code_line}")

                    lines.append(f"        ")
                    lines.append(f"        # Act")
                    args_code = ", ".join([f"{k}={repr(v)}" for k, v in method_args.items()])
                    lines.append(f"        result = self.target.{method_name}({args_code})")
                    
                    lines.append(f"        ")
                    lines.append(f"        # Assert")
                    # Expected も JSON か判定
                    try:
                        expected_json = json.loads(expected_str)
                        lines.append(f"        expected = {repr(expected_json)}")
                        lines.append(f"        # Recursive Subset Verification")
                        lines.append(f"        self.assertDictSubset(expected, result)")
                    except:
                        lines.append(f"        expected = {repr(expected_str)}")
                        lines.append(f"        self.assertEqual(result, expected)")

                else:
                    # レガシー形式 (ConditionEvaluator用)
                    lines.append(f"        # Input: {input_str}")
                    lines.append(f"        # Expected: {expected_str}")
                    
                    condition_val = "None"
                    context_val = "{}"
                    
                    m_cond = re.search(r"condition=(.+?)(?:, context=|$)", input_str)
                    if m_cond: condition_val = m_cond.group(1).strip()
                    
                    m_ctx = re.search(r"context=(.+)$", input_str)
                    if m_ctx: context_val = m_ctx.group(1).strip()
                    
                    if context_val.count('{') > context_val.count('}'):
                        context_val += '}' * (context_val.count('{') - context_val.count('}'))

                    lines.append(f"        # Arrange")
                    lines.append(f"        condition = {condition_val}")
                    lines.append(f"        context = {context_val}")
                    lines.append(f"        mock_context = MagicMock()")
                    lines.append(f"        for k, v in context.items():")
                    lines.append(f"            setattr(mock_context, k, v)")
                    lines.append(f"        if self.target is None: self.target = {class_name}()")
                    
                    lines.append(f"        # Act")
                    lines.append(f"        if isinstance(context, dict):")
                    lines.append(f"             result = self.target.evaluate(condition, context)")
                    lines.append(f"        else:")
                    lines.append(f"             result = self.target.evaluate(condition, mock_context)")
                    lines.append(f"        ")
                    lines.append(f"        # Assert")
                    lines.append(f"        expected = {expected_str}")
                    lines.append(f"        self.assertEqual(result, expected)")

                lines.append("")
            
            output_code = "\n".join(lines)
            
            # 出力ファイル保存
            output_dir = os.path.join(self.workspace_root, 'tests', 'generated')
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"test_{base_name}_spec.py")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output_code)
                
            return {'status': 'success', 'output_file': output_file, 'test_count': len(test_cases)}
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
