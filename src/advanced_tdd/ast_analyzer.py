# -*- coding: utf-8 -*-
import ast
import re
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
                return self._analyze_csharp_structure(code)
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
            'all_keywords': set(),
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
                        
                        res = self.analyze_code_structure(content, language)
                        if res.get('status') == 'success':
                            struct = res.get('structure', {})
                            combined_structure['classes'].extend(struct.get('classes', []))
                            combined_structure['functions'].extend(struct.get('functions', []))
                            
                            # 単語のインデックス化（ロジック検索用）
                            words = re.findall(r'[a-zA-Z]{3,}', content)
                            combined_structure['all_keywords'].update([w.lower() for w in words])
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
        combined_structure['all_keywords'] = list(combined_structure['all_keywords'])
        
        return {
            'status': 'success',
            'language': language,
            'structure': combined_structure
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
        """C#コードの構造解析（簡易版）"""
        structure = {
            'classes': [],
            'methods': [],
            'properties': [],
            'using_statements': [],
            'namespace': 'Generated'
        }
        
        lines = code.split('\n')
        current_namespace = 'Generated'
        current_class_idx = -1
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            
            # namespaceの検出
            if line.startswith('namespace '):
                ns_match = re.search(r'namespace\s+([\w\.]+)', line)
                if ns_match:
                    current_namespace = ns_match.group(1)
                    structure['namespace'] = current_namespace
                    for cls in structure['classes']:
                        if cls.get('namespace') == 'Generated':
                            cls['namespace'] = current_namespace
            
            # using文の検出
            if line.startswith('using ') and line.endswith(';'):
                namespace = line[6:-1].strip()
                structure['using_statements'].append({'namespace': namespace, 'line': i})
            
            # クラス定義の検出 (修飾子を考慮)
            elif 'class ' in line:
                class_match = re.search(r'(?:public|private|internal|protected)?\s*(?:static|abstract|sealed)?\s*class\s+(\w+)', line)
                if class_match:
                    current_class_name = class_match.group(1)
                    structure['classes'].append({
                        'name': current_class_name,
                        'line': i,
                        'access_modifier': self._extract_access_modifier(line),
                        'namespace': current_namespace,
                        'methods': [],
                        'properties': []
                    })
                    current_class_idx = len(structure['classes']) - 1
            
            # メソッド定義の検出 (戻り値型とメソッド名をより正確に)
            else:
                # メソッド正規表現: アクセス修飾子 + 型 + メソッド名 + 引数カッコ
                method_match = re.search(r'(public|private|protected|internal|static)\s+([\w<>\[\]]+)\s+(\w+)\s*\(([^)]*)\)', line)
                if method_match:
                    # 前方のXMLコメント(summary)を探索
                    docstring_lines = []
                    j = i - 2  # Current line is lines[i-1], so previous is lines[i-2]
                    while j >= 0:
                        prev_line = lines[j].strip()
                        if prev_line.startswith('///'):
                            # Remove tags or '///'
                            clean = re.sub(r'///\s*<.*?>', '', prev_line).replace('///', '').strip()
                            if clean:
                                docstring_lines.append(clean)
                        elif not prev_line or prev_line.startswith('['):
                            # Skip empty lines or attributes
                            pass
                        else:
                            # Stop at any other line
                            break
                        j -= 1
                    
                    docstring = " ".join(reversed(docstring_lines))
                    
                    method_info = {
                        'access_modifier': method_match.group(1),
                        'return_type': method_match.group(2),
                        'name': method_match.group(3),
                        'parameters': method_match.group(4),
                        'line': i,
                        'docstring': docstring
                    }
                    structure['methods'].append(method_info)
                    if current_class_idx != -1:
                        structure['classes'][current_class_idx]['methods'].append(method_info)
                
                # プロパティの検出
                prop_match = re.search(r'(public|private|protected|internal)\s+([\w<>\[\]]+)\s+(\w+)\s*{\s*(?:get|set)', line)
                if prop_match:
                    prop_info = {
                        'access_modifier': prop_match.group(1),
                        'type': prop_match.group(2),
                        'name': prop_match.group(3),
                        'line': i
                    }
                    structure['properties'].append(prop_info)
                    if current_class_idx != -1:
                        structure['classes'][current_class_idx]['properties'].append(prop_info)
        
        return {
            'status': 'success',
            'language': 'csharp',
            'structure': structure
        }
    
    def _analyze_generic_structure(self, code: str) -> Dict[str, Any]:
        """汎用的なコード構造解析"""
        lines = code.split('\n')
        
        structure = {
            'total_lines': len(lines),
            'non_empty_lines': len([line for line in lines if line.strip()]),
            'comment_lines': len([line for line in lines if line.strip().startswith(('//', '#', '/*'))]),
            'functions': [],
            'complexity_estimate': 0
        }
        
        # 関数/メソッドの検出
        for i, line in enumerate(lines, 1):
            if re.search(r'(function|def|public|private)\s+\w+\s*\(', line):
                func_match = re.search(r'(function|def|public|private)\s+(\w+)\s*\(', line)
                if func_match:
                    structure['functions'].append({
                        'name': func_match.group(2),
                        'line': i,
                        'type': func_match.group(1)
                    })
        
        # 複雑度の推定
        complexity_keywords = ['if', 'else', 'for', 'while', 'switch', 'case', 'try', 'catch']
        for line in lines:
            for keyword in complexity_keywords:
                if keyword in line.lower():
                    structure['complexity_estimate'] += 1
        
        return {
            'status': 'success',
            'language': 'generic',
            'structure': structure
        }
    
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
            # C# stack trace pattern: "at ... in C:\path\file.cs:line 123"
            if ' in ' in line:
                m = re.search(r' in (.*?):(?:line|行|line:)\s*(\d+)', line)
                if m:
                    file_path = m.group(1).strip()
                    line_num = int(m.group(2))
                    # メソッド名の抽出
                    method_m = re.search(r'at\s+([\w\.]+)\(', line)
                    method_name = method_m.group(1).split('.')[-1] if method_m else None
                    matches.append({'file': file_path, 'line': line_num, 'method': method_name})
            # Simplified C# pattern for tests: "at Namespace.Class.Method"
            elif line.startswith('at '):
                m = re.search(r'at ([\w\.]+)', line)
                if m:
                    full_name = m.group(1).rstrip('.')
                    parts = full_name.split('.')
                    method_name = parts[-1] if parts else None
                    if len(parts) >= 2:
                        class_name = parts[-2]
                        if class_name:
                            matches.append({'file': f"{class_name}.cs", 'line': 0, 'method': method_name})
                    elif len(parts) == 1:
                         matches.append({'file': f"{parts[0]}.cs", 'line': 0, 'method': method_name})
            # Python stack trace pattern: "File \"...\", line 123, in ..."
            elif 'File "' in line and '", line ' in line:
                m = re.search(r'File "(.+?)", line (\d+)', line)
                if m:
                    matches.append({'file': m.group(1), 'line': int(m.group(2))})

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
                # C#の場合は簡易的な解析
                lines = code.split('\n')
                in_method = False
                
                for line in lines:
                    if f'{method_name}(' in line:
                        in_method = True
                    elif in_method and '}' in line:
                        column = line.find('}')
                        if column != -1:
                            in_method = False
                    elif in_method:
                        # メソッド呼び出しの検出
                        method_calls = re.findall(r'(\w+)\s*\(', line)
                        dependencies.extend(method_calls)
        
        except Exception as e:
            self.logger.error(f"依存関係分析中にエラー: {e}")
        
        return list(set(dependencies))  # 重複を除去
        # TODO: Implement Logic: 指定ディレクトリ配下の全ファイルを再帰的にスキャン。
        # TODO: Implement Logic: **メタデータ抽出**:
            # TODO: Implement Logic: クラス名、メソッド名、引数リスト、アクセス修飾子を抽出。
            # TODO: Implement Logic: 特定のメソッド内で呼び出されている他の関数やメソッドのリストを抽出。
