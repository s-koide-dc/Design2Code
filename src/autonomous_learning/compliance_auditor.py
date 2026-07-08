# -*- coding: utf-8 -*-
import os
import json
import ast
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from src.utils.action_intents import INTENT_DOC_GEN, INTENT_DOC_REFINE

class ComplianceAuditor:
    """プロジェクト規約と構造の整合性を自律的に監査するクラス"""
    
    def __init__(self, workspace_root: str = ".", structural_memory=None):
        self.workspace_root = Path(workspace_root)
        self.memory = structural_memory
        self.logger = logging.getLogger(__name__)
        self.configuration_diagnostics = []
        self.rules = self._load_rules()
        self.findings = []

    def _load_rules(self) -> dict:
        path = self.workspace_root / "config" / "project_rules.json"
        if not path.exists():
            self.configuration_diagnostics.append({
                "type": "AUDIT_CONFIGURATION_ERROR",
                "severity": "high",
                "file": str(path.relative_to(self.workspace_root)),
                "message": "Project rule file is missing.",
            })
            return {}
        try:
            with open(path, "r", encoding="utf-8") as rules_file:
                rules = json.load(rules_file)
        except (OSError, json.JSONDecodeError) as exc:
            self.configuration_diagnostics.append({
                "type": "AUDIT_CONFIGURATION_ERROR",
                "severity": "high",
                "file": str(path.relative_to(self.workspace_root)),
                "message": f"Project rule file could not be loaded: {type(exc).__name__}",
            })
            return {}
        if not isinstance(rules, dict):
            self.configuration_diagnostics.append({
                "type": "AUDIT_CONFIGURATION_ERROR",
                "severity": "high",
                "file": str(path.relative_to(self.workspace_root)),
                "message": "Project rule root must be an object.",
            })
            return {}
        return rules

    def run_full_audit(self) -> List[Dict[str, Any]]:
        """全項目の監査を実行"""
        self.findings = list(self.configuration_diagnostics)
        self._audit_mandatory_files()
        self._audit_document_quality() # NEW: Check content quality
        self._audit_dependencies()
        self._audit_semantic_overlaps()
        
        return self.findings

    def _audit_document_quality(self):
        """設計書の中身の品質（プレースホルダーの残存等）をチェック"""
        src_dir = self.workspace_root / 'src'
        if not src_dir.exists(): return

        contract = self.rules.get("document_contract", {})
        minimum_sections = contract.get("minimum_level_2_sections", 2)
        require_section_body = contract.get("require_section_body", True)

        for root, _, files in os.walk(src_dir):
            for file in files:
                if file.endswith('.design.md'):
                    path = Path(root) / file
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            lines = f.read().splitlines()
                    except OSError as exc:
                        self.findings.append({
                            "type": "DOCUMENT_READ_ERROR",
                            "severity": "medium",
                            "file": str(path.relative_to(self.workspace_root)),
                            "message": f"設計書を読み取れません: {type(exc).__name__}",
                        })
                        continue

                    title_present = any(
                        line.startswith("# ") for line in lines
                    )
                    section_indexes = [
                        index for index, line in enumerate(lines)
                        if line.startswith("## ")
                    ]
                    empty_sections = []
                    if require_section_body:
                        for position, section_index in enumerate(section_indexes):
                            end_index = (
                                section_indexes[position + 1]
                                if position + 1 < len(section_indexes)
                                else len(lines)
                            )
                            body = lines[section_index + 1:end_index]
                            if not any(
                                line.strip() and not line.startswith("#")
                                for line in body
                            ):
                                empty_sections.append(lines[section_index][3:].strip())

                    if (
                        not title_present
                        or len(section_indexes) < minimum_sections
                        or empty_sections
                    ):
                        self.findings.append({
                            "type": "DOCUMENT_INCOMPLETE",
                            "severity": "low",
                            "file": str(path.relative_to(self.workspace_root)),
                            "message": "設計書が構造契約を満たしていません。",
                            "details": {
                                "title_present": title_present,
                                "level_2_section_count": len(section_indexes),
                                "minimum_level_2_sections": minimum_sections,
                                "empty_sections": empty_sections,
                            },
                        })

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
                    try:
                        with open(path, 'r', encoding='utf-8') as source_file:
                            tree = ast.parse(source_file.read(), filename=str(path))
                    except OSError as exc:
                        self.findings.append({
                            "type": "SOURCE_READ_ERROR",
                            "severity": "medium",
                            "file": str(path.relative_to(self.workspace_root)),
                            "message": f"ソースを読み取れません: {type(exc).__name__}",
                        })
                        continue
                    except SyntaxError as exc:
                        self.findings.append({
                            "type": "SOURCE_PARSE_ERROR",
                            "severity": "medium",
                            "file": str(path.relative_to(self.workspace_root)),
                            "message": f"Python構文を解析できません: line {exc.lineno}",
                        })
                        continue

                    imported_modules = set()
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            imported_modules.update(
                                alias.name for alias in node.names
                            )
                        elif isinstance(node, ast.ImportFrom) and node.module:
                            imported_modules.add(node.module)

                    for target in forbidden_list:
                        forbidden_module = target.replace("/", ".")
                        if any(
                            module == forbidden_module
                            or module.startswith(forbidden_module + ".")
                            for module in imported_modules
                        ):
                            self.findings.append({
                                "type": "DEPENDENCY_VIOLATION",
                                "severity": "high",
                                "file": str(path.relative_to(self.workspace_root)),
                                "message": f"依存関係違反: {description} (禁止対象: {target})"
                            })

    def _audit_semantic_overlaps(self):
        """明示された重複グループの整合性を監査する。"""
        if not self.memory or not hasattr(self.memory, "components"):
            return
        components = self.memory.components
        duplicate_groups = {}
        for component in components:
            if not isinstance(component, dict):
                continue
            group_id = component.get("duplicate_group_id")
            if isinstance(group_id, str) and group_id:
                duplicate_groups.setdefault(group_id, []).append(component)

        for group_id, group_components in duplicate_groups.items():
            for index, first in enumerate(group_components):
                for second in group_components[index + 1:]:
                    if first.get("file") == second.get("file"):
                        continue
                    self.findings.append({
                        "type": "SEMANTIC_DUPLICATION",
                        "severity": "low",
                        "message": (
                            f"明示された重複グループ '{group_id}' に "
                            f"'{first.get('name')}' と '{second.get('name')}' "
                            "が登録されています。"
                        ),
                        "details": {
                            "component1": first,
                            "component2": second,
                            "duplicate_group_id": group_id,
                            "evidence_type": "declared_duplicate_group",
                        },
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
                "action_type": INTENT_DOC_GEN,
                "finding": top
            }
        elif top['type'] == 'DOCUMENT_INCOMPLETE':
            return {
                "summary": f"設計書の詳細追記 ({top['file']})",
                "message": f"設計書 '{top['file']}' に未記入の項目があります。AIがロジックを分析して補完を試みますか？",
                "action_type": INTENT_DOC_REFINE,
                "finding": top
            }
        
        return None
