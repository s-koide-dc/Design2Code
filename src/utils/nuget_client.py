# -*- coding: utf-8 -*-
import urllib.request
import urllib.parse
import json
import logging
import os
from typing import Optional, Dict, Any, List

class NuGetClient:
    """NuGet Search API 経由でパッケージ情報を取得するクライアント"""

    def __init__(self, config_manager=None):
        self.logger = logging.getLogger("NuGetClient")
        self.search_url = "https://azuresearch-usnc.nuget.org/query"
        self.config_manager = config_manager
        self.map_path = config_manager.dependency_map_path if config_manager else os.path.join('resources', 'dependency_map.json')
        self._cache: Dict[str, Dict[str, Any]] = self._load_map()

    def _load_map(self) -> Dict[str, Any]:
        """永続化されたマップをロードする"""
        if os.path.exists(self.map_path):
            try:
                with open(self.map_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load dependency map: {e}")
        return {}

    def save(self):
        """現在のキャッシュをファイルに永続化する"""
        try:
            os.makedirs(os.path.dirname(self.map_path), exist_ok=True)
            with open(self.map_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Saved {len(self._cache)} mappings to {self.map_path}")
        except Exception as e:
            self.logger.error(f"Failed to save dependency map: {e}")

    def resolve_package(self, namespace_or_name: str) -> Optional[Dict[str, str]]:
        # ... (keep existing implementation)
        if namespace_or_name in self._cache:
            return self._cache[namespace_or_name]

        query = namespace_or_name
        
        url = f"{self.search_url}?q={urllib.parse.quote(query)}&prerelease=false&take=1"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
                if data.get('data'):
                    pkg = data['data'][0]
                    result = {
                        "name": pkg['id'],
                        "version": pkg['version']
                    }
                    if query.lower() in pkg['id'].lower() or pkg['id'].lower() in query.lower():
                        self._cache[namespace_or_name] = result
                        return result
        except Exception as e:
            self.logger.error(f"NuGet API error for '{query}': {e}")

        return None

    def resolve_packages_from_usings(self, usings: List[str], fallback: Optional[Dict[str, Dict[str, str]]] = None) -> List[Dict[str, str]]:
        """using一覧からNuGet依存を決定する（決定的なマッピングのみ）"""
        if not usings:
            return []
        fallback = fallback or {}
        deps_by_name: Dict[str, Dict[str, str]] = {}
        for ns in usings:
            if not ns or ns.startswith("System"):
                continue
            pkg = self.resolve_package(ns)
            if not pkg:
                if ns in fallback:
                    pkg = fallback[ns]
                else:
                    for key, val in fallback.items():
                        if ns.startswith(f"{key}."):
                            pkg = val
                            break
            if pkg and pkg.get("name"):
                deps_by_name[pkg["name"]] = pkg
        if deps_by_name:
            self.save()
        return list(deps_by_name.values())

    def get_package_dlls(self, package_name: str, version: str) -> List[str]:
        """ローカルの NuGet キャッシュから指定されたパッケージの DLL パスを取得する"""
        user_profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        package_root = os.path.join(user_profile, ".nuget", "packages", package_name.lower(), version)
        
        if not os.path.exists(package_root):
            # Try original case if lower case fails
            package_root = os.path.join(user_profile, ".nuget", "packages", package_name, version)
            if not os.path.exists(package_root):
                return []
        
        # lib フォルダ配下の DLL を探索
        lib_path = os.path.join(package_root, "lib")
        if not os.path.exists(lib_path):
            return []

        # フレームワークごとのフォルダを取得し、最適なものを選択
        frameworks = [d for d in os.listdir(lib_path) if os.path.isdir(os.path.join(lib_path, d))]
        if not frameworks:
            return []
        
        # 優先順位: net10.0 > net9.0 > net8.0 > net7.0 > net6.0 > net5.0 > netcoreapp... > net48 > net47... > netstandard...
        # 簡易的にソート (netX.0 が上位に来るように)
        def fw_score(fw):
            fw = fw.lower()
            if fw.startswith("net10"): return 100
            if fw.startswith("net9"): return 90
            if fw.startswith("net8"): return 80
            if fw.startswith("net7"): return 70
            if fw.startswith("net6"): return 60
            if fw.startswith("net5"): return 50
            if fw.startswith("netcoreapp"): return 40
            if fw.startswith("netstandard2.1"): return 35
            if fw.startswith("netstandard2.0"): return 30
            if fw.startswith("net48"): return 20
            if fw.startswith("net47"): return 15
            if fw.startswith("net46"): return 10
            return 0
        
        frameworks.sort(key=fw_score, reverse=True)
        best_fw = frameworks[0]
        
        dlls = []
        target_path = os.path.join(lib_path, best_fw)
        for root, dirs, files in os.walk(target_path):
            for file in files:
                if file.endswith(".dll") and not file.endswith(".resources.dll"):
                    dlls.append(os.path.abspath(os.path.join(root, file)))
        
        return dlls

if __name__ == "__main__":
    client = NuGetClient()
    print(client.resolve_package("YamlDotNet"))
    print(client.resolve_package("System.Text.Json")) # Standard library might also appear
