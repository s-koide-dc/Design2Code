import ast
import os
from typing import Any, Dict, List, Optional

from .base_detector import BaseSmellDetector


class DuplicateCodeDetector(BaseSmellDetector):
    """明示された重複グループ情報から重複コードを報告する。"""

    def __init__(self, thresholds: Dict[str, Any]):
        super().__init__(thresholds)
        self.diagnostics: List[Dict[str, Any]] = []

    def detect(
        self,
        file_path: str,
        content: str,
        project_root: str,
    ) -> List[Dict[str, Any]]:
        self.diagnostics = []
        if not file_path.lower().endswith(".py"):
            self.diagnostics.append({
                "type": "STRUCTURAL_ANALYSIS_REQUIRED",
                "file": file_path,
            })
            return []

        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError as exc:
            self.diagnostics.append({
                "type": "SOURCE_PARSE_ERROR",
                "file": file_path,
                "line": exc.lineno,
            })
            return []

        grouped_occurrences: Dict[str, List[Dict[str, Any]]] = {}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            group_id = self._duplicate_group_id(node.decorator_list)
            if not group_id:
                continue
            grouped_occurrences.setdefault(group_id, []).append({
                "file": os.path.relpath(file_path, project_root),
                "method": node.name,
                "line_start": node.lineno,
                "line_end": node.end_lineno,
            })

        return [
            self._build_smell(group_id=group_id, occurrences=occurrences)
            for group_id, occurrences in sorted(grouped_occurrences.items())
            if len(occurrences) > 1
        ]

    @staticmethod
    def _duplicate_group_id(decorators: List[ast.expr]) -> Optional[str]:
        for decorator in decorators:
            if not isinstance(decorator, ast.Call):
                continue
            function = decorator.func
            is_duplicate_group = (
                isinstance(function, ast.Name)
                and function.id == "duplicate_group"
            ) or (
                isinstance(function, ast.Attribute)
                and function.attr == "duplicate_group"
            )
            if (
                is_duplicate_group
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
            ):
                return decorator.args[0].value
        return None

    def detect_roslyn(
        self,
        object_details: Dict[str, Any],
        manifest_entry: Dict[str, Any],
        roslyn_analysis_results: Dict[str, Any],
        project_root: str,
    ) -> List[Dict[str, Any]]:
        if object_details.get("type") != "Method":
            return []
        group_id = object_details.get("duplicateGroupId")
        if not isinstance(group_id, str) or not group_id:
            return []

        occurrences = []
        for other_detail in roslyn_analysis_results.get("details_by_id", {}).values():
            if (
                other_detail.get("type") == "Method"
                and other_detail.get("duplicateGroupId") == group_id
            ):
                occurrences.append({
                    "file": os.path.relpath(other_detail["filePath"], project_root),
                    "method": other_detail.get("name"),
                    "line_start": other_detail.get("startLine"),
                    "line_end": other_detail.get("endLine"),
                })
        occurrences.sort(key=lambda occurrence: (
            occurrence["file"],
            occurrence["line_start"],
            occurrence["method"],
        ))

        if len(occurrences) < 2:
            return []
        first = occurrences[0]
        current = {
            "file": os.path.relpath(manifest_entry["filePath"], project_root),
            "line_start": object_details.get("startLine"),
            "method": object_details.get("name"),
        }
        if (
            current["file"],
            current["line_start"],
            current["method"],
        ) != (
            first["file"],
            first["line_start"],
            first["method"],
        ):
            return []

        return [self._build_smell(group_id=group_id, occurrences=occurrences)]

    @staticmethod
    def _build_smell(
        *,
        group_id: str,
        occurrences: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        first = occurrences[0]
        return {
            "type": "duplicate_code",
            "severity": "medium",
            "file": first["file"],
            "method": first["method"],
            "duplicate_group_id": group_id,
            "occurrences": occurrences,
            "metrics": {
                "duplicate_group_id": group_id,
                "occurrences_count": len(occurrences),
            },
            "description": (
                f"duplicate_group '{group_id}' が"
                f"{len(occurrences)}箇所で宣言されています。"
            ),
            "impact": "共通化または責務分離の妥当性を確認してください。",
        }
