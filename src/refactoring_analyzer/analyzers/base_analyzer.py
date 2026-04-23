# -*- coding: utf-8 -*-
# src/refactoring_analyzer/base_analyzer.py

import os
from typing import Dict, List, Any
from ..detectors import LongMethodDetector, DuplicateCodeDetector, ComplexConditionDetector, GodClassDetector

class BaseRefactoringAnalyzer:
    """リファクタリング分析器の基底クラス"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.smell_detectors = self._initialize_detectors()
    
    def _initialize_detectors(self) -> Dict[str, Any]:
        """検出器を初期化（サブクラスで実装）"""
        raise NotImplementedError
    
    def detect_smells(self, project_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """コードスメルを検出（サブクラスで実装）"""
        raise NotImplementedError
    
    def _safe_analyze_file(self, file_path: str, project_root: str) -> List[Dict[str, Any]]:
        """安全なファイル分析（エラーハンドリング強化版）"""
        smells = []
        
        try:
            # ファイルサイズチェック（10MB制限）
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:  # 10MB
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
            
            if content is None:
                return smells
            
            # 各検出器を実行
            for detector_name, detector in self.smell_detectors.items():
                try:
                    file_smells = detector.detect(file_path, content, project_root)
                    smells.extend(file_smells)
                except Exception:
                    pass
            
        except (FileNotFoundError, PermissionError, OSError):
            pass
        except Exception:
            pass
        
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
        # TODO: Implement Logic: ファイルサイズ（10MB制限）をチェック。
