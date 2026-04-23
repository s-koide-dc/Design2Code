# -*- coding: utf-8 -*-
import os
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.utils.logic_auditor import LogicAuditor
from src.utils.design_doc_parser import DesignDocParser
from src.advanced_tdd.fix_engine import CodeFixSuggestionEngine
from src.config.config_manager import ConfigManager
from src.vector_engine.vector_engine import VectorEngine

class AutonomousAligner:
    """設計書と実装の整合性を自律的に修正・維持するクラス"""

    def __init__(self, project_root: str, config: Optional[Dict[str, Any]] = None, vector_engine=None, morph_analyzer=None):
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
        """ビルドエラーの内容に基づいてソースコードを直接修復する"""
        if build_result.get("valid"):
            return False

        try:
            with open(source_file, "r", encoding="utf-8") as f:
                code_content = f.read()

            errors = build_result.get("errors", [])
            if not errors:
                return False

            new_code = code_content
            any_fix_applied = False
            
            # 各エラーに対して修正を試みる
            for err in errors:
                analysis = {
                    "fix_direction": "fix_syntax_error",
                    "analysis_details": {
                        "error_message": f"{err['code']}: {err['message']}",
                        "line_number": err.get("line")
                    }
                }
                target_code = {
                    "file": str(source_file),
                    "current_implementation": new_code
                }
                
                suggestions = self.fix_engine.generate_fix_suggestions(analysis, target_code)
                
                for sug in suggestions:
                    if sug.auto_applicable and sug.safety_score >= 0.8:
                        if sug.current_code in new_code:
                            new_code = new_code.replace(sug.current_code, sug.suggested_code, 1)
                            any_fix_applied = True
                            self.logger.info(f"Applied build fix: {sug.description}")
                            break # 一つのエラーが直ったら次のエラー（または再ビルド）へ
            
            if any_fix_applied:
                with open(source_file, "w", encoding="utf-8") as f:
                    f.write(new_code)
                return True

        except Exception as e:
            self.logger.error(f"Error during build error fixing: {e}")
        
        return False

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

            # 3. 監査の実行
            # 現状、source_structure は簡易的に作成
            source_structure = {
                "files_analyzed": 1,
                "all_keywords": list(set(re.findall(r'[a-zA-Z]{3,}', code_content.lower())))
            }
            
            audit_result = self.auditor.audit(design_data, source_structure, code_content)
            
            if audit_result["status"] == "consistent":
                return {"module": module_name, "status": "consistent", "score": audit_result["consistency_score"]}

            # 4. 修正の生成と適用 (収束するまで繰り返す)
            applied_suggestions = []
            max_iterations = 5
            current_iteration = 0
            new_code = code_content
            
            while current_iteration < max_iterations:
                target_code = {
                    "file": str(source_file),
                    "current_implementation": new_code
                }
                
                suggestions = self.fix_engine.generate_fix_suggestions(audit_result, target_code)
                
                if not suggestions:
                    break
                
                # 安全スコアの高い最初の提案を適用
                applied_in_this_cycle = False
                for sug in suggestions:
                    if sug.auto_applicable and sug.safety_score >= 0.8:
                        if not sug.current_code:
                             # 末尾に単純挿入
                             new_code = new_code.rstrip() + f"\n{sug.suggested_code}\n"
                        elif sug.current_code in new_code:
                             new_code = new_code.replace(sug.current_code, sug.suggested_code, 1)
                        else:
                             continue
                        
                        applied_suggestions.append(sug.description)
                        applied_in_this_cycle = True
                        break # 次の監査サイクルへ
                
                if not applied_in_this_cycle:
                    break
                
                # 再監査
                audit_result = self.auditor.audit(design_data, source_structure, new_code)
                if audit_result["status"] == "consistent":
                    break
                
                current_iteration += 1
            
            if new_code != code_content:
                with open(source_file, "w", encoding="utf-8") as f:
                    f.write(new_code)
                self.logger.info(f"Applied {len(applied_suggestions)} fixes to {source_file}")

            return {
                "module": module_name,
                "status": "aligned" if applied_suggestions else "consistent" if audit_result["status"] == "consistent" else "inconsistent",
                "initial_score": audit_result["consistency_score"],
                "final_score": audit_result["consistency_score"],
                "findings": audit_result["findings"],
                "fixes_applied": applied_suggestions
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
    print(f"Alignment completed. Modules processed: {report['total_modules_processed']}")
    # TODO: Implement Logic: **整合性修復サイクル (Iterative Repair)**:
        # TODO: Implement Logic: **修正提案の生成**: `findings` を `FixEngine` に渡し、スタブ挿入等の修正案を取得。
        # TODO: Implement Logic: 以下のステップを、不整合が解消されるか最大試行回数（5回）に達するまで繰り返す。
        # TODO: Implement Logic: **修正の適用**: 安全スコアが一定（0.8）以上の提案を、ソースファイルに直接適用。
        # TODO: Implement Logic: **結果報告**: 最終的な整合性スコアと、適用された修正の履歴をレポートにまとめる。
