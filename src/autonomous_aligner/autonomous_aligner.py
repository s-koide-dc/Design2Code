# -*- coding: utf-8 -*-
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.utils.logic_auditor import LogicAuditor
from src.utils.design_doc_parser import DesignDocParser
from src.advanced_tdd.fix_engine import CodeFixSuggestionEngine
from src.config.config_manager import ConfigManager
from src.vector_engine.vector_engine import VectorEngine
from src.utils.stdout_guard import debug_print

class AutonomousAligner:
    """設計書と実装の整合性を自律的に修正・維持するクラス"""

    def __init__(
        self,
        project_root: str,
        config: Optional[Dict[str, Any]] = None,
        vector_engine=None,
        morph_analyzer=None,
        structural_patch_builder=None,
        post_change_validator=None,
    ):
        self.project_root = Path(project_root)
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 依存関係の注入
        if vector_engine is None:
            try:
                cfg = ConfigManager(str(self.project_root))
                vector_engine = VectorEngine(model_path=cfg.vector_model_path)
            except Exception:
                vector_engine = None

        self.vector_engine = vector_engine
        self.morph_analyzer = morph_analyzer
        self.structural_patch_builder = structural_patch_builder
        self.post_change_validator = post_change_validator

        self.auditor = LogicAuditor(
            vector_engine=self.vector_engine,
            morph_analyzer=self.morph_analyzer,
            knowledge_base=getattr(self, "ukb", None)
        )
        self.parser = DesignDocParser()
        self.fix_engine = CodeFixSuggestionEngine(self.config)
        self.alignment_history: List[Dict[str, Any]] = []

    def align_all_modules(self) -> Dict[str, Any]:
        """プロジェクト内の全モジュールの整合性を調整する"""
        results = []
        # デザインドキュメントを検索
        design_docs = list(self.project_root.rglob("*.design.md"))

        for doc_path in design_docs:
            res = self.align_module(doc_path)
            if res:
                results.append(res)

        report = {
            "timestamp": datetime.now().isoformat(),
            "total_modules_processed": len(results),
            "modules": results
        }
        return report

    def fix_build_errors(self, source_file: Path, build_result: Dict[str, Any]) -> bool:
        """明示された構造パッチを検証し、成功した場合だけ適用する。"""
        if build_result.get("valid"):
            return False

        if not callable(self.structural_patch_builder) or not callable(
            self.post_change_validator
        ):
            self.logger.info(
                "Build repair for %s was not applied because no structural "
                "patch and post-change validator are configured.",
                source_file,
            )
            return False

        resolved_root = self.project_root.resolve()
        resolved_source = source_file.resolve()
        if resolved_source != resolved_root and resolved_root not in resolved_source.parents:
            self.logger.error("Build repair target is outside project root: %s", source_file)
            return False

        original_content = source_file.read_text(encoding="utf-8")
        patch = self.structural_patch_builder(
            source_file,
            original_content,
            build_result,
        )
        if not isinstance(patch, dict) or not isinstance(patch.get("edits"), list):
            self.logger.error("Structural patch builder returned an invalid patch.")
            return False
        try:
            candidate_content = self._apply_structural_edits(
                original_content,
                patch["edits"],
            )
        except (TypeError, ValueError):
            self.logger.exception("Structural patch validation failed.")
            return False
        if candidate_content == original_content:
            return False

        validation = self.post_change_validator(
            source_file,
            candidate_content,
            build_result,
        )
        if not isinstance(validation, dict) or validation.get("valid") is not True:
            self.logger.info("Candidate build repair did not pass validation.")
            return False

        source_file.write_text(candidate_content, encoding="utf-8")
        self.alignment_history.append({
            "timestamp": datetime.now().isoformat(),
            "source_file": str(source_file),
            "patch": patch,
            "validation": validation,
        })
        return True

    @staticmethod
    def _apply_structural_edits(
        original_content: str,
        edits: List[Dict[str, Any]],
    ) -> str:
        lines = original_content.splitlines(keepends=True)
        normalized_edits = []
        for edit in edits:
            if not isinstance(edit, dict):
                raise TypeError("Each structural edit must be an object.")
            start_line = edit.get("start_line")
            end_line = edit.get("end_line")
            replacement = edit.get("replacement")
            if (
                not isinstance(start_line, int)
                or isinstance(start_line, bool)
                or not isinstance(end_line, int)
                or isinstance(end_line, bool)
                or not isinstance(replacement, str)
                or start_line < 1
                or end_line < start_line
                or end_line > len(lines)
            ):
                raise ValueError("Invalid structural edit range.")
            normalized_edits.append((start_line, end_line, replacement))

        normalized_edits.sort(key=lambda item: item[0])
        for previous, current in zip(normalized_edits, normalized_edits[1:]):
            if current[0] <= previous[1]:
                raise ValueError("Structural edits overlap.")

        updated_lines = list(lines)
        for start_line, end_line, replacement in reversed(normalized_edits):
            updated_lines[start_line - 1:end_line] = [replacement]
        return "".join(updated_lines)

    def align_module(self, design_doc_path: Path) -> Optional[Dict[str, Any]]:
        """特定のモジュールの整合性を監査・修正する"""
        try:
            # 1. 設計書のパース
            design_data = self.parser.parse_file(str(design_doc_path))
            module_name = design_data.get("module_name") or design_doc_path.name.replace(".design.md", "")

            # 2. 対応するソースファイルの特定
            source_file = self._find_source_file(design_doc_path)
            if not source_file or not source_file.exists():
                self.logger.warning(f"Source file not found for {design_doc_path}")
                return None

            with open(source_file, "r", encoding="utf-8") as f:
                code_content = f.read()

            # 3. 監査の実行。名称の単語集合など、コードから推測した特徴は渡さない。
            source_structure = {
                "files_analyzed": 1,
                "source_file": str(source_file),
                "language": source_file.suffix.lstrip("."),
            }

            audit_result = self.auditor.audit(design_data, source_structure, code_content)
            initial_score = audit_result["consistency_score"]

            if audit_result["status"] == "consistent":
                return {
                    "module": module_name,
                    "status": "consistent",
                    "score": initial_score,
                    "fixes_applied": [],
                    "pending_suggestions": [],
                }

            if audit_result["status"] == "indeterminate":
                return {
                    "module": module_name,
                    "status": "indeterminate",
                    "initial_score": None,
                    "final_score": None,
                    "findings": audit_result["findings"],
                    "fixes_applied": [],
                    "pending_suggestions": [],
                    "mutation_blocked_reason": (
                        "structured_design_and_implementation_steps_required"
                    ),
                }

            target_code = {
                "file": str(source_file),
                "current_implementation": code_content,
            }
            suggestions = self.fix_engine.generate_fix_suggestions(
                audit_result,
                target_code,
            )

            return {
                "module": module_name,
                "status": "inconsistent",
                "initial_score": initial_score,
                "final_score": audit_result["consistency_score"],
                "findings": audit_result["findings"],
                "fixes_applied": [],
                "pending_suggestions": [
                    {
                        "description": suggestion.description,
                        "current_code": suggestion.current_code,
                        "suggested_code": suggestion.suggested_code,
                        "line_number": suggestion.line_number,
                    }
                    for suggestion in suggestions
                ],
                "mutation_blocked_reason": (
                    "structural_patch_and_post_change_validation_required"
                ),
            }

        except Exception as e:
            self.logger.error(f"Error aligning module {design_doc_path}: {e}")
            return None

    def _find_source_file(self, design_doc_path: Path) -> Optional[Path]:
        """設計書に対応するソースファイルを探す"""
        # 同一ディレクトリの .py または .cs ファイルを探す
        base_name = design_doc_path.name.replace(".design.md", "")
        for ext in [".py", ".cs"]:
            src = design_doc_path.parent / (base_name + ext)
            if src.exists():
                return src
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    aligner = AutonomousAligner(".")
    report = aligner.align_all_modules()
    debug_print(f"Alignment completed. Modules processed: {report['total_modules_processed']}")
