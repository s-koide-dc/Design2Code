# -*- coding: utf-8 -*-
import json
import os
import logging
from typing import List, Dict, Any, Optional
from src.utils.nuget_client import NuGetClient

class DependencyResolver:
    """C# の依存関係（シンボル -> NuGet パッケージ）を解決するクラス"""

    def __init__(self, config_manager=None, structural_memory=None):
        self.logger = logging.getLogger("DependencyResolver")
        self.config_manager = config_manager
        self.nuget_client = NuGetClient(config_manager)
        self.structural_memory = structural_memory
        
        # 既知のマッピングをロード
        self.map_path = self.nuget_client.map_path

    def resolve(self, symbol: str) -> Optional[Dict[str, str]]:
        """シンボル名からパッケージ情報を解決する"""
        if not symbol:
            return None
            
        # 1. プロジェクト内部のシンボルかチェック
        if self.structural_memory:
            # クラス名または完全修飾名で検索
            internal_matches = [c for c in self.structural_memory.items if c.get("name") == symbol or c.get("fullName") == symbol]
            if internal_matches:
                self.logger.info(f"Symbol '{symbol}' found in project internal memory. No NuGet package needed.")
                return {"internal": True, "file": internal_matches[0].get("file")}

        # 2. 既知のマップをチェック
        package = self.nuget_client.resolve_package(symbol)
        if package:
            return package
            
        # 3. 階層的名前空間の解決 (例: System.Text.Json.JsonSerializer -> System.Text.Json)
        parts = symbol.split('.')
        if len(parts) > 1:
            for i in range(len(parts) - 1, 0, -1):
                parent_ns = '.'.join(parts[:i])
                # 短すぎる名前空間（Systemなど）はノイズが多いのでスキップ
                if len(parent_ns) < 4: continue
                
                self.logger.info(f"Attempting to resolve parent namespace: {parent_ns}")
                package = self.nuget_client.resolve_package(parent_ns)
                if package:
                    return package
        
        return None

    def analyze_build_errors(self, errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ビルドエラーから不足しているパッケージまたは内部参照を特定する"""
        results = []
        seen_symbols = set()
        
        for error in errors:
            if error.get("code") == "CS0246":
                msg = error.get("message", "")
                import re
                match = re.search(r"'(.*?)'", msg)
                if match:
                    symbol = match.group(1)
                    if symbol not in seen_symbols:
                        seen_symbols.add(symbol)
                        res = self.resolve(symbol)
                        if res:
                            results.append(res)
                            
        return results

    def save_mappings(self):
        """解決に成功したマッピングを永続化する"""
        self.nuget_client.save()
