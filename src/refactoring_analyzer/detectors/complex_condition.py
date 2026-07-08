# -*- coding: utf-8 -*-

import ast
import os
from typing import Dict, List, Any

from .base_detector import BaseSmellDetector


class ComplexConditionDetector(BaseSmellDetector):
    """構文木で明示された複雑な条件構造を検出する。"""

    ALLOWED_FACTS = {
        "mixed_boolean_operators",
        "negated_boolean_group",
        "chained_comparison",
    }

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
                "language": os.path.splitext(file_path)[1].lower(),
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
            condition = self._condition_for_node(node)
            if condition is None:
                continue
            facts = sorted(self._condition_facts(condition))
            if not facts:
                continue
            smells.append(self._build_smell(
                file_path=os.path.relpath(file_path, project_root),
                line=getattr(node, "lineno", None),
                facts=facts,
                content=ast.get_source_segment(content, condition),
            ))
        return smells

    @staticmethod
    def _condition_for_node(node: ast.AST) -> ast.AST | None:
        if isinstance(node, (ast.If, ast.While, ast.IfExp)):
            return node.test
        if isinstance(node, ast.Assert):
            return node.test
        return None

    def _condition_facts(self, condition: ast.AST) -> set[str]:
        facts = set()
        for node in ast.walk(condition):
            if isinstance(node, ast.BoolOp):
                child_operators = {
                    type(child.op)
                    for child in node.values
                    if isinstance(child, ast.BoolOp)
                }
                if child_operators and any(
                    operator is not type(node.op)
                    for operator in child_operators
                ):
                    facts.add("mixed_boolean_operators")
            elif (
                isinstance(node, ast.UnaryOp)
                and isinstance(node.op, ast.Not)
                and isinstance(node.operand, ast.BoolOp)
            ):
                facts.add("negated_boolean_group")
            elif isinstance(node, ast.Compare) and len(node.ops) > 1:
                facts.add("chained_comparison")
        return facts

    def detect_roslyn(
        self,
        object_details: Dict[str, Any],
        manifest_entry: Dict[str, Any],
        roslyn_analysis_results: Dict[str, Any],
        project_root: str,
    ) -> List[Dict[str, Any]]:
        self.diagnostics = []
        if object_details.get("type") != "Method":
            return []

        smells = []
        structures = object_details.get("conditionStructures", [])
        if not isinstance(structures, list):
            self.diagnostics.append({
                "type": "INVALID_CONDITION_STRUCTURES",
                "method": object_details.get("name"),
            })
            return []
        for structure in structures:
            if not isinstance(structure, dict):
                continue
            raw_facts = structure.get("facts", [])
            if not isinstance(raw_facts, list):
                continue
            facts = sorted({
                fact for fact in raw_facts
                if fact in self.ALLOWED_FACTS
            })
            if not facts:
                continue
            smells.append(self._build_smell(
                file_path=os.path.relpath(
                    manifest_entry["filePath"],
                    project_root,
                ),
                line=structure.get("line"),
                facts=facts,
                content=structure.get("source"),
                method=object_details.get("name"),
            ))
        return smells

    @staticmethod
    def _build_smell(
        *,
        file_path: str,
        line: int | None,
        facts: List[str],
        content: str | None,
        method: str | None = None,
    ) -> Dict[str, Any]:
        smell = {
            "type": "complex_condition",
            "severity": "medium",
            "file": file_path,
            "line": line,
            "metrics": {
                "structural_facts": facts,
            },
            "description": "条件式に複合的な構文構造があります。",
            "impact": "条件を名前付きの判定へ分割できる可能性があります。",
        }
        if content:
            smell["content"] = content
        if method:
            smell["method"] = method
        return smell
