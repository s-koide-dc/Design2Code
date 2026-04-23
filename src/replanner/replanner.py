# -*- coding: utf-8 -*-
from typing import List, Dict, Any
import copy
from src.replanner.reason_analyzer import ReasonAnalyzer
from src.replanner.ir_patcher import IRPatcher

class Replanner:
    """Design-to-Code パイプラインの再試行サイクルを管理するクラス"""

    def __init__(self, config=None):
        self.config = config
        self.analyzer = ReasonAnalyzer()
        self.patcher = IRPatcher()
        self.history = [] # Trial history to ensure convergence

    def replan(self, 
               structured_spec: Dict[str, Any], 
               ir_tree: Dict[str, Any], 
               synthesis_result: Dict[str, Any], 
               verification_result: Dict[str, Any],
               semantic_issues: List[str]) -> Dict[str, Any]:
        
        # 1. 分析失敗理由の特定
        hints = self.analyzer.analyze(synthesis_result, verification_result, semantic_issues)
        
        # 2. 合成結果の論理検証（妄想的リテラルの検出など）
        mismatch_hints = self.analyzer.analyze_logic_mismatch(ir_tree, synthesis_result)
        hints.extend(mismatch_hints)

        if not hints:
            return {"status": "FAILED", "message": "Could not identify repairable issues."}

        # [Convergence Guard] Prevent infinite loops
        non_link_hints = [
            h for h in hints
            if h.get("reason") not in ["SPEC_INPUT_LINK_UNUSED", "SPEC_INPUT_REF_UNUSED"]
        ]
        hint_fingerprint = str(sorted([str(h) for h in non_link_hints or hints]))
        if hint_fingerprint in self.history:
            # Allow repeated input_link/ref hints to be retried within retry budget
            if non_link_hints:
                return {"status": "FAILED", "message": "Convergence error: Repeating repair hints detected."}
        
        self.history.append(hint_fingerprint)
        if len(self.history) > 5:
            return {"status": "FAILED", "message": "Max retry limit reached."}

        print(f"    - Generated Hints: {hints}")

        # 3. IR ツリーへのパッチ適用
        patched_ir = self.patcher.apply_patches(copy.deepcopy(ir_tree), hints)
        
        return {
            "status": "REPLANNED",
            "patched_ir": patched_ir,
            "hints": hints
        }
