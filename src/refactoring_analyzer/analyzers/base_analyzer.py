# -*- coding: utf-8 -*-
# src/refactoring_analyzer/base_analyzer.py

import os
from typing import Dict, List, Any
from ..detectors import LongMethodDetector, DuplicateCodeDetector, ComplexConditionDetector, GodClassDetector

class BaseRefactoringAnalyzer:
    """リファクタリング分析器の基底クラス"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.analysis_diagnostics: List[Dict[str, str]] = []
        self.smell_detectors = self._initialize_detectors()

    def _record_analysis_error(self, file_path: str, operation: str, error_type: str, detector: str = None) -> None:
        diagnostic = {
            "file": file_path,
            "operation": operation,
            "error_type": error_type,
        }
        if detector:
            diagnostic["detector"] = detector
        if diagnostic not in self.analysis_diagnostics:
            self.analysis_diagnostics.append(diagnostic)
    
    def _initialize_detectors(self) -> Dict[str, Any]:
        """検出器を初期化（サブクラスで実装）"""
        raise NotImplementedError
    
    def detect_smells(self, project_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """コードスメルを検出（サブクラスで実装）"""
        raise NotImplementedError
    
    def _safe_analyze_file(self, file_path: str, project_root: str) -> List[Dict[str, Any]]:
        """安全なファイル分析（エラーハンドリング強化版）"""
        smells = []
        
        # ファイルサイズチェック（10MB制限）
        try:
            file_size = os.path.getsize(file_path)
        except OSError as exc:
            self._record_analysis_error(file_path, "stat_file", type(exc).__name__)
            return smells
        if file_size > 10 * 1024 * 1024:  # 10MB
            self._record_analysis_error(file_path, "read_file", "FileTooLarge")
            return smells

        # ファイル読み込み（複数エンコーディング対応）
        content = None
        encodings = ['utf-8', 'utf-8-sig', 'cp1252', 'latin1']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
            except OSError as exc:
                self._record_analysis_error(file_path, "read_file", type(exc).__name__)
                return smells

        if content is None:
            self._record_analysis_error(file_path, "decode_file", "UnicodeDecodeError")
            return smells

        # 各検出器を実行。プラグイン境界なので個別失敗は診断して継続する。
        for detector_name, detector in self.smell_detectors.items():
            try:
                file_smells = detector.detect(file_path, content, project_root)
                smells.extend(file_smells)
            except Exception as exc:
                self._record_analysis_error(
                    file_path,
                    "detect_smells",
                    type(exc).__name__,
                    detector=detector_name,
                )
        
        return smells
    
    def _should_exclude_file(self, file_path: str, content: str = None) -> bool:
        """ファイルを除外すべきかどうかを判定"""
        exclusion_rules = self.config.get("exclusion_rules", {})
        
        # ファイルパターンによる除外
        file_patterns = exclusion_rules.get("file_patterns", [])
        for pattern in file_patterns:
            if self._match_pattern(file_path, pattern):
                return True
        
        # ディレクトリパターンによる除外
        dir_patterns = exclusion_rules.get("directory_patterns", [])
        for pattern in dir_patterns:
            if pattern in file_path.replace("\\", "/"):
                return True
        
        # コンテンツパターンによる除外
        if content:
            content_patterns = exclusion_rules.get("content_patterns", [])
            for pattern in content_patterns:
                if pattern in content:
                    return True
        
        return False
    
    def _match_pattern(self, file_path: str, pattern: str) -> bool:
        """パターンマッチングを実行"""
        import fnmatch
        normalized_path = file_path.replace("\\", "/")
        return fnmatch.fnmatch(normalized_path, pattern)
