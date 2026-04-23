# -*- coding: utf-8 -*-
# src/refactoring_analyzer/detectors/base_detector.py

from typing import Dict, List, Any, Optional

class BaseSmellDetector:
    """コードスメル検出器の基底クラス"""
    
    def __init__(self, thresholds: Dict[str, Any]):
        self.thresholds = thresholds
        
    def detect(self, file_path: str, content: str, project_root: str) -> List[Dict[str, Any]]:
        """スメルを検出（サブクラスで実装）"""
        raise NotImplementedError
        
    def detect_roslyn(self, object_details: Dict[str, Any], manifest_entry: Dict[str, Any], 
                      roslyn_analysis_results: Dict[str, Any], project_root: str) -> List[Dict[str, Any]]:
        """Roslyn解析結果からスメルを検出（サブクラスで実装）"""
        return []
