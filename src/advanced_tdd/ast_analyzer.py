# -*- coding: utf-8 -*-
import ast
import os
import logging
from typing import Dict, List, Any, Optional

class ASTAnalyzer:
    """AST解析を担当するクラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_code_structure(self, code: str, language: str = 'python', roslyn_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """コード構造を解析"""
        try:
            if language == 'python':
                return self._analyze_python_ast(code)
            elif language == 'csharp':
                if roslyn_data:
                    return self._analyze_csharp_from_roslyn(roslyn_data)
                return {
                    'status': 'structural_analysis_required',
                    'language': 'csharp',
                    'diagnostic': 'CSharp analysis requires Roslyn data.',
                    'structure': self._empty_csharp_structure(),
                }
            else:
                return self._analyze_generic_structure(code)
                
        except Exception as e:
            self.logger.error(f"AST解析中にエラーが発生: {e}")
            return {'error': str(e), 'structure': {}}

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """ファイルを読み込んで構造を解析"""
        if not os.path.exists(file_path):
            return {"error": "File not found"}
        
        ext = os.path.splitext(file_path)[1].lower()
        lang = 'python' if ext == '.py' else 'csharp' if ext == '.cs' else 'generic'
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            if lang == 'csharp':
                return {
                    "error": "CSharp analysis requires Roslyn data",
                    "diagnostic": "STRUCTURAL_ANALYSIS_REQUIRED",
                }
            res = self.analyze_code_structure(content, language=lang)
            return res.get('structure', {})
        except Exception as e:
            return {"error": str(e)}

    def analyze_directory(self, dir_path: str, language: str = 'python') -> Dict[str, Any]:
        """ディレクトリ配下の全ファイルを解析して構造を統合する"""
        combined_structure = {
            'classes': [],
            'functions': [],
            'methods': [], # Flattened for easy search
            'all_identifiers': set(),
            'files_analyzed': 0
        }
        
        if not os.path.exists(dir_path):
            return {'error': f"Directory not found: {dir_path}", 'structure': {}}

        for root, _, files in os.walk(dir_path):
            for file in files:
                if (language == 'python' and file.endswith('.py')) or \
                   (language == 'csharp' and file.endswith('.cs')):
                    
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        if language == 'csharp':
                            self.logger.warning(
                                "Skipping C# file without Roslyn data: %s",
                                file_path,
                            )
                            continue

                        res = self.analyze_code_structure(content, language)
                        if res.get('status') == 'success':
                            struct = res.get('structure', {})
                            combined_structure['classes'].extend(struct.get('classes', []))
                            combined_structure['functions'].extend(struct.get('functions', []))
                            combined_structure['all_identifiers'].update(
                                self._collect_python_identifiers(content)
                            )
                            combined_structure['files_analyzed'] += 1
                            
                            # メソッド名のフラット化
                            for cls in struct.get('classes', []):
                                if 'methods' in cls:
                                    for m in cls['methods']:
                                        m_name = m['name'] if isinstance(m, dict) else str(m)
                                        combined_structure['methods'].append(m_name.lower())
                    except Exception as e:
                        self.logger.warning(f"Failed to analyze {file_path}: {e}")

        # JSON変換のためにセットをリストに戻す
        combined_structure['all_identifiers'] = sorted(combined_structure['all_identifiers'])
        
        return {
            'status': 'success',
            'language': language,
            'structure': combined_structure
            }
    
    @staticmethod
    def _empty_csharp_structure() -> Dict[str, Any]:
        return {
            'classes': [],
            'methods': [],
            'properties': [],
            'using_statements': [],
            'namespace': None,
        }

    def _analyze_csharp_from_roslyn(self, roslyn_data: Dict[str, Any]) -> Dict[str, Any]:
        """MyRoslynAnalyzerのデータからC#構造を構築"""
        try:
            structure = {
                'classes': [],
                'methods': [],
                'properties': [],
                'using_statements': []
            }
            
            manifest = roslyn_data.get('manifest', {})
            details = roslyn_data.get('details_by_id', {})
            
            objects = manifest.get('objects', [])
            for obj in objects:
                obj_id = obj.get('id')
                detail = details.get(obj_id, {})
                obj_type = obj.get('type')
                
                if obj_type in ['Class', 'Struct', 'Interface']:
                    structure['classes'].append({
                        'name': obj.get('fullName'),
                        'line': obj.get('startLine', 0),
                        'end_line': obj.get('endLine', 0),
                        'access_modifier': obj.get('accessibility', 'public'),
                        'metrics': detail.get('metrics', {}) if detail else {}
                    })
                
                # 詳細データがある場合はメソッド等を追加
                if detail:
                    # 依存関係の抽出
                    for dep in detail.get('dependencies', []):
                        if 'dependencies' not in structure:
                            structure['dependencies'] = []
                        structure['dependencies'].append({
                            'source_id': obj_id,
                            'target_id': dep.get('id'),
                            'file': dep.get('filePath'),
                            'line': dep.get('line')
                        })

                    for method in detail.get('methods', []):
                        if isinstance(method, dict):
                            m_name = method.get('name')
                            m_params = method.get('parameters', [])
                            m_line = method.get('startLine', 0)
                            m_end_line = method.get('endLine', 0)
                            m_return = method.get('returnType', 'void')
                            m_metrics = method.get('metrics', {})
                        else:
                            m_name = str(method)
                            m_params = []
                            m_line = 0
                            m_end_line = 0
                            m_return = 'dynamic'
                            m_metrics = {}
                            
                        structure['methods'].append({
                            'name': m_name,
                            'parameters': m_params,
                            'line': m_line,
                            'end_line': m_end_line,
                            'return_type': m_return,
                            'metrics': m_metrics,
                            'branches': method.get('branches', []),
                            'class_id': obj_id
                        })
            
            return {
                'status': 'success',
                'language': 'csharp',
                'structure': structure,
                'source': 'roslyn'
            }
        except Exception as e:
            self.logger.error(f"RoslynデータからのC#構造解析中にエラーが発生: {e}")
            return {'error': str(e), 'structure': {}}
    
    def _analyze_python_ast(self, code: str) -> Dict[str, Any]:
        """PythonコードのAST解析"""
        try:
            tree = ast.parse(code)
            
            structure = {
                'classes': [],
                'functions': [],
                'variables': [],
                'imports': [],
                'complexity': 0,
                'namespace': 'global'
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            methods.append(item.name)
                    
                    structure['classes'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'methods': methods,
                        'docstring': ast.get_docstring(node),
                        'access_modifier': 'public'
                    })
                
                elif isinstance(node, ast.FunctionDef):
                    structure['functions'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args],
                        'returns': self._extract_return_type(node),
                        'complexity': self._calculate_complexity(node),
                        'docstring': ast.get_docstring(node)
                    })
                
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            structure['variables'].append({
                                'name': target.id,
                                'line': node.lineno,
                                'type': self._infer_type(node.value)
                            })
                
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            structure['imports'].append({
                                'module': alias.name,
                                'alias': alias.asname,
                                'line': node.lineno
                            })
                    else:  # ImportFrom
                        for alias in node.names:
                            structure['imports'].append({
                                'module': node.module,
                                'name': alias.name,
                                'alias': alias.asname,
                                'line': node.lineno
                            })
            
            # 全体の複雑度計算
            structure['complexity'] = sum(f['complexity'] for f in structure['functions'])
            
            return {
                'status': 'success',
                'language': 'python',
                'structure': structure
            }
            
        except SyntaxError as e:
            return {
                'status': 'syntax_error',
                'error': f'構文エラー: {e}',
                'line': e.lineno,
                'structure': {}
            }
    
    def _analyze_csharp_structure(self, code: str) -> Dict[str, Any]:
        """C#コードの直接解析は行わない。Roslyn解析結果を使用する。"""
        return {
            'status': 'structural_analysis_required',
            'language': 'csharp',
            'diagnostic': 'CSharp analysis requires Roslyn data.',
            'structure': self._empty_csharp_structure(),
        }
    
    def _analyze_generic_structure(self, code: str) -> Dict[str, Any]:
        """汎用的なコード構造解析"""
        lines = code.split('\n')
        
        structure = {
            'total_lines': len(lines),
            'non_empty_lines': len([line for line in lines if line.strip()]),
            'comment_lines': len([line for line in lines if line.strip().startswith(('//', '#', '/*'))]),
            'functions': [],
            'complexity_estimate': None,
            'diagnostic': 'STRUCTURAL_ANALYSIS_REQUIRED',
        }

        return {
            'status': 'structural_analysis_required',
            'language': 'generic',
            'structure': structure
        }

    @staticmethod
    def _collect_python_identifiers(code: str) -> set[str]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return set()
        identifiers = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                identifiers.add(node.id.lower())
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                identifiers.add(node.name.lower())
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for arg in node.args.args:
                        identifiers.add(arg.arg.lower())
            elif isinstance(node, ast.Attribute):
                identifiers.add(node.attr.lower())
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    identifiers.add((alias.asname or alias.name).split('.')[0].lower())
        return identifiers
    
    def _extract_return_type(self, node: ast.FunctionDef) -> Optional[str]:
        """関数の戻り値型を抽出"""
        if node.returns:
            if isinstance(node.returns, ast.Name):
                return node.returns.id
            elif isinstance(node.returns, ast.Constant):
                return str(node.returns.value)
    def analyze_stack_trace(self, stack_trace: str) -> Dict[str, Any]:
        """スタックトレースからファイルパスと行番号を抽出"""
        if not stack_trace:
            return {'stack_depth': 0, 'file_locations': [], 'primary_location': None, 'test_context': {}}
            
        lines = stack_trace.split('\n')
        matches = []
        for line in lines:
            line = line.strip()
            parsed = (
                self._parse_csharp_stack_frame(line)
                or self._parse_python_stack_frame(line)
            )
            if parsed:
                matches.append(parsed)

        primary = matches[0] if matches else None
        return {
            'stack_depth': len(lines),
            'file_locations': matches,
            'primary_location': primary,
            'test_context': {
                'test_file': primary['file'] if primary else None,
                'test_method': primary['method'] if primary else None
            } if primary else {}
        }

    @staticmethod
    def _parse_csharp_stack_frame(line: str) -> Optional[Dict[str, Any]]:
        if not line.startswith('at '):
            return None
        frame = line[3:].strip()
        method_part = frame
        file_path = None
        line_number = 0

        if ' in ' in frame:
            method_part, location_part = frame.split(' in ', 1)
            parsed_location = ASTAnalyzer._parse_dotnet_location(location_part)
            if parsed_location:
                file_path, line_number = parsed_location
            else:
                return None

        method_name = ASTAnalyzer._method_name_from_frame(method_part)
        if not file_path:
            class_name = ASTAnalyzer._class_name_from_frame(method_part)
            file_path = f"{class_name}.cs" if class_name else None
        if not file_path:
            return None
        return {'file': file_path, 'line': line_number, 'method': method_name}

    @staticmethod
    def _parse_dotnet_location(location_part: str) -> Optional[tuple[str, int]]:
        markers = [':line ', ':line:', ':行 ']
        for marker in markers:
            marker_index = location_part.rfind(marker)
            if marker_index == -1:
                continue
            file_path = location_part[:marker_index].strip()
            digits = []
            for char in location_part[marker_index + len(marker):]:
                if char.isdigit():
                    digits.append(char)
                elif digits:
                    break
            if file_path and digits:
                return file_path, int(''.join(digits))
        return None

    @staticmethod
    def _parse_python_stack_frame(line: str) -> Optional[Dict[str, Any]]:
        if not line.startswith('File "'):
            return None
        after_prefix = line[len('File "'):]
        if '", line ' not in after_prefix:
            return None
        file_path, rest = after_prefix.split('", line ', 1)
        digits = []
        index = 0
        while index < len(rest) and rest[index].isdigit():
            digits.append(rest[index])
            index += 1
        if not file_path or not digits:
            return None
        method_name = None
        in_marker = ', in '
        in_index = rest.find(in_marker, index)
        if in_index != -1:
            method_name = rest[in_index + len(in_marker):].strip() or None
        return {'file': file_path, 'line': int(''.join(digits)), 'method': method_name}

    @staticmethod
    def _method_name_from_frame(method_part: str) -> Optional[str]:
        before_params = method_part.split('(', 1)[0].strip().rstrip('.')
        if not before_params:
            return None
        parts = [part for part in before_params.split('.') if part]
        return parts[-1] if parts else None

    @staticmethod
    def _class_name_from_frame(method_part: str) -> Optional[str]:
        before_params = method_part.split('(', 1)[0].strip().rstrip('.')
        parts = [part for part in before_params.split('.') if part]
        if len(parts) >= 2:
            return parts[-2]
        if len(parts) == 1:
            return parts[0]
        return None
    
    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """関数の循環複雑度を計算"""
        complexity = 1  # 基本複雑度
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.Try)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    def _infer_type(self, node: ast.AST) -> str:
        """変数の型を推論"""
        if isinstance(node, ast.Constant):
            return type(node.value).__name__
        elif isinstance(node, ast.List):
            return 'list'
        elif isinstance(node, ast.Dict):
            return 'dict'
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return f'result_of_{node.func.id}'
        return 'unknown'
    
    def _extract_access_modifier(self, line: str) -> str:
        """アクセス修飾子を抽出"""
        modifiers = ['public', 'private', 'protected', 'internal']
        for modifier in modifiers:
            if modifier in line:
                return modifier
        return 'default'
    
    def find_method_dependencies(self, code: str, method_name: str, language: str = 'python') -> List[str]:
        """メソッドの依存関係を特定"""
        dependencies = []
        
        try:
            if language == 'python':
                tree = ast.parse(code)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name == method_name:
                        for child in ast.walk(node):
                            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                                dependencies.append(child.func.id)
                            elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                                dependencies.append(child.id)
            
            elif language == 'csharp':
                self.logger.warning(
                    "C# dependency analysis requires Roslyn data for method %s",
                    method_name,
                )
        
        except Exception as e:
            self.logger.error(f"依存関係分析中にエラー: {e}")
        
        return list(set(dependencies))  # 重複を除去
