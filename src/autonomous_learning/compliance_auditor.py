# -*- coding: utf-8 -*-
import os
import json
import re
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

class ComplianceAuditor:
    """プロジェクト規約と構造の整合性を自律的に監査するクラス"""
    
    def __init__(self, workspace_root: str = ".", structural_memory=None):
        self.workspace_root = Path(workspace_root)
        self.memory = structural_memory
        self.logger = logging.getLogger(__name__)
        
        self.rules = self._load_rules()
        self.findings = []

    def _load_rules(self) -> dict:
        path = self.workspace_root / 'resources' / 'project_rules.json'
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def run_full_audit(self) -> List[Dict[str, Any]]:
        """全項目の監査を実行"""
        self.findings = []
        self._audit_mandatory_files()
        self._audit_document_quality() # NEW: Check content quality
        self._audit_dependencies()
        self._audit_semantic_overlaps()
        
        return self.findings

    def _audit_document_quality(self):
        """設計書の中身の品質（プレースホルダーの残存等）をチェック"""
        src_dir = self.workspace_root / 'src'
        if not src_dir.exists(): return

        placeholders = [
            r"ここにモジュールの目的を記述してください",
            r"ロギングの詳細をここに記述してください",
            r"ロジックの詳細をここに記述してください",
            r"Skeleton only",
            r"TODO:"
        ]

        for root, _, files in os.walk(src_dir):
            for file in files:
                if file.endswith('.design.md'):
                    path = Path(root) / file
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            for p in placeholders:
                                if re.search(p, content):
                                    self.findings.append({
                                        "type": "DOCUMENT_INCOMPLETE",
                                        "severity": "low",
                                        "file": str(path.relative_to(self.workspace_root)),
                                        "message": f"設計書に未記入の項目（プレースホルダー）が残っています: '{p}'"
                                    })
                                    break
                    except:
                        pass

    def _audit_mandatory_files(self):
        """必須ファイル（設計書等）の存在チェック"""
        rules = self.rules.get("structural_rules", [])
        for rule in rules:
            if rule.get("type") == "mandatory_file":
                pattern = rule.get("pattern")
                self._check_pattern_existence(pattern, rule.get("description"))

    def _check_pattern_existence(self, pattern: str, description: str):
        """特定のパターン（例: src/{module}/{module}.design.md）の存在を確認"""
        src_dir = self.workspace_root / 'src'
        if not src_dir.exists(): return

        for module_dir in src_dir.iterdir():
            if module_dir.is_dir() and module_dir.name != "__pycache__":
                expected_rel = pattern.replace("{module}", module_dir.name)
                expected_path = self.workspace_root / expected_rel
                
                if not expected_path.exists():
                    self.findings.append({
                        "type": "MANDATORY_FILE_MISSING",
                        "severity": "medium",
                        "file": str(expected_rel),
                        "message": f"設計書が見つかりません: {description}"
                    })

    def _audit_dependencies(self):
        """依存関係制約のチェック"""
        rules = self.rules.get("structural_rules", [])
        for rule in rules:
            if rule.get("type") == "dependency_constraint":
                source_prefix = rule.get("source")
                forbidden = rule.get("cannot_depend_on", [])
                self._check_imports(source_prefix, forbidden, rule.get("description"))

    def _check_imports(self, source_prefix: str, forbidden_list: List[str], description: str):
        """特定のディレクトリ内のファイルが禁止されたモジュールをインポートしていないか確認"""
        base_path = self.workspace_root / source_prefix
        if not base_path.exists(): return

        for root, _, files in os.walk(base_path):
            for file in files:
                if file.endswith('.py'):
                    path = Path(root) / file
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        for target in forbidden_list:
                            # Simple regex for Python imports
                            # Matches 'import target' or 'from target import'
                            pattern = rf'^\s*(import|from)\s+{target.replace("/", ".")}'
                            if re.search(pattern, content, re.MULTILINE):
                                self.findings.append({
                                    "type": "DEPENDENCY_VIOLATION",
                                    "severity": "high",
                                    "file": str(path.relative_to(self.workspace_root)),
                                    "message": f"依存関係違反: {description} (禁止対象: {target})"
                                })

    def _audit_semantic_overlaps(self):
        """意味的な重複（コピペコードや類似機能）のチェック"""
        if not self.memory or not hasattr(self.memory, 'collection') or self.memory.collection.vectors is None or len(self.memory.components) < 2:
            return

        vectors = self.memory.collection.vectors
        components = self.memory.components
        threshold = 0.95 # 重複とみなす類似度のしきい値

        # 全ペアの類似度を計算（上三角行列のみ）
        sim_matrix = np.dot(vectors, vectors.T)
        
        for i in range(len(components)):
            for j in range(i + 1, len(components)):
                if sim_matrix[i, j] >= threshold:
                    c1, c2 = components[i], components[j]
                    # 同じファイル内の別メソッド等は除外（要件に応じて調整）
                    if c1['file'] != c2['file']:
                        self.findings.append({
                            "type": "SEMANTIC_DUPLICATION",
                            "severity": "low",
                            "message": f"機能の重複が疑われます: '{c1['name']}' と '{c2['name']}' は極めて類似した役割を持っています。",
                            "details": {
                                "component1": c1,
                                "component2": c2,
                                "similarity": float(sim_matrix[i, j])
                            }
                        })

    def generate_proactive_suggestion(self) -> Optional[Dict[str, Any]]:
        """監査結果に基づき、ユーザーに提案する最も重要なタスクを1つ選択"""
        if not self.findings: return None
        
        # 深刻度順にソート
        severity_map = {"high": 3, "medium": 2, "low": 1}
        sorted_findings = sorted(self.findings, key=lambda x: severity_map.get(x['severity'], 0), reverse=True)
        
        top = sorted_findings[0]
        
        if top['type'] == 'DEPENDENCY_VIOLATION':
            return {
                "summary": f"アーキテクチャ違反の修正 ({top['file']})",
                "message": f"{top['file']} が禁止されたモジュールに依存しています。修正案を作成しますか？",
                "action_type": "REFACTOR",
                "finding": top
            }
        elif top['type'] == 'MANDATORY_FILE_MISSING':
            return {
                "summary": f"不足している設計書の作成 ({top['file']})",
                "message": f"モジュールの設計書 '{top['file']}' が不足しています。現在の実装から自動生成しますか？",
                "action_type": "DOC_GEN",
                "finding": top
            }
        elif top['type'] == 'DOCUMENT_INCOMPLETE':
            return {
                "summary": f"設計書の詳細追記 ({top['file']})",
                "message": f"設計書 '{top['file']}' に未記入の項目があります。AIがロジックを分析して補完を試みますか？",
                "action_type": "DOC_REFINE",
                "finding": top
            }
        
        return None
