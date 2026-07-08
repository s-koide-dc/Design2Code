import ast
import os
from typing import Dict, List, Any

from .base_detector import BaseSmellDetector


class GodClassDetector(BaseSmellDetector):
    """明示された構造factから責務過多クラスを報告する。"""

    FACT = "god_class"

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

        smells = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if self.FACT not in self._decorator_facts(node.decorator_list):
                continue
            smells.append(self._build_smell(
                file_path=os.path.relpath(file_path, project_root),
                class_name=node.name,
                line_start=node.lineno,
                line_end=node.end_lineno,
            ))
        return smells

    @staticmethod
    def _decorator_facts(decorators: List[ast.expr]) -> set[str]:
        facts = set()
        for decorator in decorators:
            if not isinstance(decorator, ast.Call):
                continue
            function = decorator.func
            is_fact_decorator = (
                isinstance(function, ast.Name)
                and function.id == "refactoring_fact"
            ) or (
                isinstance(function, ast.Attribute)
                and function.attr == "refactoring_fact"
            )
            if (
                is_fact_decorator
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
            ):
                facts.add(decorator.args[0].value)
        return facts

    def detect_roslyn(
        self,
        object_details: Dict[str, Any],
        manifest_entry: Dict[str, Any],
        roslyn_analysis_results: Dict[str, Any],
        project_root: str,
    ) -> List[Dict[str, Any]]:
        if object_details.get("type") not in {"Class", "Struct"}:
            return []
        facts = object_details.get("refactoringFacts", [])
        if not isinstance(facts, list) or self.FACT not in facts:
            return []
        return [self._build_smell(
            file_path=os.path.relpath(
                manifest_entry["filePath"],
                project_root,
            ),
            class_name=object_details.get("fullName"),
            line_start=object_details.get("startLine"),
            line_end=object_details.get("endLine"),
        )]

    @staticmethod
    def _build_smell(
        *,
        file_path: str,
        class_name: str,
        line_start: int,
        line_end: int,
    ) -> Dict[str, Any]:
        return {
            "type": "god_class",
            "severity": "high",
            "file": file_path,
            "class": class_name,
            "line_start": line_start,
            "line_end": line_end,
            "metrics": {
                "structural_facts": ["god_class"],
            },
            "description": f"クラス '{class_name}' にgod_class factがあります。",
            "impact": "責務分割の妥当性を確認してください。",
        }
