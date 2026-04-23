import os
import re
import ast # Import the AST module for Python code analysis
from typing import Dict, List, Any
from .base_detector import BaseSmellDetector

class LongMethodDetector(BaseSmellDetector):
    """長いメソッド検出器"""
    
    def detect(self, file_path: str, content: str, project_root: str) -> List[Dict[str, Any]]:
        """
        コード内の長いメソッドを検出します。
        Pythonファイルの場合はASTモジュールを使用し、その他の言語の場合はより汎用的な行数カウントロジックを使用します。
        """
        smells = []
        
        rel_path = os.path.relpath(file_path, project_root)

        if file_path.endswith('.py'):
            smells.extend(self._detect_python_long_methods(file_path, content, rel_path))
        else:
            smells.extend(self._detect_generic_long_methods(file_path, content, rel_path))
            
        return smells

    def _detect_python_long_methods(self, file_path: str, content: str, rel_path: str) -> List[Dict[str, Any]]:
        smells = []
        try:
            tree = ast.parse(content, filename=file_path)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Calculate method length, excluding decorators and comments/docstrings from raw line count
                    # ast.get_source_segment can be used for exact source, but node.lineno and node.end_lineno are sufficient for length
                    method_start_line = node.lineno
                    method_end_line = node.end_lineno if hasattr(node, 'end_lineno') else method_start_line # Python 3.8+
                    
                    if method_end_line is None: # Fallback for older Python or if end_lineno not available
                        method_end_line = method_start_line
                        # Try to estimate end_lineno from body
                        if node.body:
                            method_end_line = node.body[-1].end_lineno if hasattr(node.body[-1], 'end_lineno') else method_end_line

                    # Count actual code lines (ignoring blank lines and comments) within the method body
                    method_lines = content.splitlines()[method_start_line-1:method_end_line]
                    
                    code_lines = 0
                    for line in method_lines:
                        stripped_line = line.strip()
                        if stripped_line: # Count all non-empty lines including comments
                            code_lines += 1

                    threshold = self.thresholds.get("long_method_lines", 20)
                    
                    if code_lines > threshold:
                        smells.append({
                            "type": "long_method",
                            "severity": "high" if code_lines > threshold * 2 else "medium",
                            "file": rel_path,
                            "method": node.name,
                            "line_start": method_start_line,
                            "line_end": method_end_line,
                            "metrics": {
                                "line_count": code_lines,
                                "threshold": threshold
                            },
                            "description": f"メソッド '{node.name}' が長すぎます（{code_lines}行）。推奨は{threshold}行以下です。",
                            "impact": "可読性とテスト容易性が低下しています。"
                        })
        except SyntaxError:
            # Handle files that might not be valid Python syntax
            pass
        return smells

    def _detect_generic_long_methods(self, file_path: str, content: str, rel_path: str) -> List[Dict[str, Any]]:
        """
        Python以外の言語（JavaScriptなど）向けの汎用的な長いメソッド検出。
        C#とJavaScriptのパターンを統合し、より柔軟にメソッドを識別し、
        コード行数のみを考慮する（コメントや空行は無視）。
        """
        smells = []
        lines = content.split('\n')
        
        # C#とJavaScriptの両方をカバーするより汎用的なメソッドパターン
        # (function|public|private|protected|internal)?\s*(static|async)?\s*(virtual|override)?\s*(\w+)\s*(\w+)?\s*\(
        method_pattern = r'^\s*(?:(?:function|public|private|protected|internal)\s+)?(?:(?:static|async|virtual|override)\s+)?(?:(\w+)\s+)?(\w+)\s*\('
        
        current_method = None
        method_start_index = -1
        brace_level = 0
        in_method_body = False
        
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            
            # 既にメソッド本体内にいるか、新しいメソッド定義を探す
            if not in_method_body:
                method_match = re.search(method_pattern, stripped_line)
                if method_match:
                    # グループ2がメソッド名であることが多い（例: function foo(), public void bar()）
                    method_name = method_match.group(2) if method_match.group(2) else method_match.group(1)
                    if method_name: # 有効なメソッド名が見つかった場合
                        current_method = method_name
                        method_start_index = i
                        brace_level = 0 # 新しいメソッドの波括弧レベルをリセット
                        # メソッド定義の行に '{' があるか確認して即座に本体開始を検出
                        if '{' in stripped_line:
                            for char in stripped_line:
                                if char == '{': brace_level += 1
                                elif char == '}': brace_level -= 1
                            if brace_level > 0:
                                in_method_body = True
                                method_start_index = i # 本体開始をメソッド定義行に設定
                        continue # この行でメソッド定義を処理したので、次の行へ
            
            if current_method:
                # メソッド本体内の行を処理
                for char in stripped_line:
                    if char == '{': brace_level += 1
                    elif char == '}': brace_level -= 1

                # メソッド本体が開始したかどうか
                if not in_method_body and brace_level > 0:
                    in_method_body = True
                    method_start_index = i # メソッド本体の開始行

                # メソッド終了の検出（波括弧が閉じ、レベルが0になる）
                if in_method_body and brace_level == 0 and method_start_index != -1:
                    method_length = 0
                    for k in range(method_start_index, i + 1):
                        current_method_line = lines[k].strip()
                        # 空行を無視してすべての行（コメントを含む）をカウント
                        if current_method_line:
                            method_length += 1

                    threshold = self.thresholds.get("long_method_lines", 20)
                    
                    if method_length > threshold:
                        smells.append({
                            "type": "long_method",
                            "severity": "high" if method_length > threshold * 2 else "medium",
                            "file": rel_path,
                            "method": current_method,
                            "line_start": method_start_index + 1,
                            "line_end": i + 1,
                            "metrics": {
                                "line_count": method_length,
                                "threshold": threshold
                            },
                            "description": f"メソッド '{current_method}' が長すぎます（{method_length}行）。推奨は{threshold}行以下です。",
                            "impact": "可読性とテスト容易性が低下しています。"
                        })
                    
                    current_method = None
                    method_start_index = -1
                    in_method_body = False
                    brace_level = 0 # リセット

        return smells

    def detect_roslyn(self, object_details: Dict[str, Any], manifest_entry: Dict[str, Any], 
                      roslyn_analysis_results: Dict[str, Any], project_root: str) -> List[Dict[str, Any]]:
        """Roslyn解析結果から長いメソッドを検出"""
        smells = []
        
        if object_details.get("type") == "Method":
            method_name = object_details.get("name")
            method_start_line = object_details.get("startLine")
            method_end_line = object_details.get("endLine")
            
            if method_start_line is not None and method_end_line is not None:
                # Use the lineCount directly from Roslyn metrics
                method_line_count = object_details.get("metrics", {}).get("lineCount", 0)
                
                threshold = self.thresholds.get("long_method_lines", 20)
                
                if method_line_count > threshold:
                    rel_file_path = os.path.relpath(manifest_entry["filePath"], project_root)
                    smells.append({
                        "type": "long_method",
                        "severity": "high" if method_line_count > threshold * 2 else "medium",
                        "file": rel_file_path,
                        "method": method_name,
                        "line_start": method_start_line,
                        "line_end": method_end_line,
                        "metrics": {
                            "line_count": method_line_count,
                            "threshold": threshold
                        },
                        "description": f"メソッド '{method_name}' が長すぎます（{method_line_count}行）。推奨は{threshold}行以下です。",
                        "impact": "可読性とテスト容易性が低下しています。"
                    })
        
        return smells
        # TODO: Implement Logic: **言語判定**: ファイル拡張子に基づき解析手法を選択。
        # TODO: Implement Logic: 装飾子や空行を除いた実質的なコード行数をカウント。
        # TODO: Implement Logic: 正規表現でメソッド定義を特定。
