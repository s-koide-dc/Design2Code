# -*- coding: utf-8 -*-
import json
import os
import shutil
import logging
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
from src.semantic_search.semantic_search_base import SemanticSearchBase

class RepairKnowledgeBase(SemanticSearchBase):
    """テスト修復のための知識ベース (SemanticSearchBase統合版)"""
    
    def __init__(self, workspace_root: str = ".", vector_engine=None, morph_analyzer=None, config_manager=None):
        self.config_manager = config_manager
        root_path = config_manager.workspace_root if config_manager else workspace_root
        if config_manager:
            storage_dir = config_manager.storage_dir
            metadata_path = config_manager.repair_knowledge_path
        else:
            storage_dir = os.path.join(root_path, 'resources', 'vectors', 'vector_db')
            metadata_path = None

        self._migrate_legacy_vector_store_files(str(root_path), storage_dir)
            
        super().__init__("repair_knowledge", storage_dir, vector_engine, morph_analyzer, metadata_path=metadata_path)
        
        self.workspace_root = root_path
        self.semantic_threshold = 0.85 # 類似度のしきい値
        
        # 固有メタデータ
        self.fix_stats = {}
        self.type_mappings = {}
        self.negative_feedbacks: List[Dict[str, Any]] = []
        self.unresolved_symbols: List[str] = []
        
        self.load()

    def _migrate_legacy_vector_store_files(self, workspace_root: str, target_dir: str):
        """旧配置の repair_knowledge ベクトルDBファイルを統一保存先へ移行する。"""
        if not workspace_root or not target_dir:
            return
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception:
            return

        legacy_dirs = [
            workspace_root,
            os.path.join(workspace_root, "resources"),
            os.path.join(workspace_root, "cache"),
        ]
        target_meta = os.path.join(target_dir, "repair_knowledge_meta.json")
        target_vec = os.path.join(target_dir, "repair_knowledge_vectors.npy")

        for legacy_dir in legacy_dirs:
            legacy_meta = os.path.join(legacy_dir, "repair_knowledge_meta.json")
            legacy_vec = os.path.join(legacy_dir, "repair_knowledge_vectors.npy")
            try:
                if os.path.exists(legacy_meta):
                    if not os.path.exists(target_meta):
                        shutil.move(legacy_meta, target_meta)
                    else:
                        if os.path.getmtime(legacy_meta) > os.path.getmtime(target_meta):
                            shutil.copy2(legacy_meta, target_meta)
                        os.remove(legacy_meta)
                if os.path.exists(legacy_vec):
                    if not os.path.exists(target_vec):
                        shutil.move(legacy_vec, target_vec)
                    else:
                        if os.path.getmtime(legacy_vec) > os.path.getmtime(target_vec):
                            shutil.copy2(legacy_vec, target_vec)
                        os.remove(legacy_vec)
            except Exception:
                # 移行失敗は初期化を止めない
                pass

    def load(self):
        super().load()
        # 固有データの復元 (metadata_pathから再読み込み)
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.fix_stats = data.get('fix_stats', {})
                    self.type_mappings = data.get('type_mappings', {})
                    self.negative_feedbacks = data.get('negative_feedbacks', [])
                    self.unresolved_symbols = data.get('unresolved_symbols', [])
            except: pass

    def save_knowledge(self):
        # メタデータを拡張して保存
        os.makedirs(self.storage_dir, exist_ok=True)
        try:
            wrapper = {
                "patterns": self.items, 
                "fix_stats": self.fix_stats,
                "type_mappings": self.type_mappings,
                "negative_feedbacks": self.negative_feedbacks,
                "unresolved_symbols": self.unresolved_symbols,
                "count": len(self.items)
            }
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(wrapper, f, ensure_ascii=False, indent=2)
            
            if hasattr(self, 'vectors') and self.vectors is not None:
                np.save(self.vector_path, self.vectors)
            
            self.is_dirty = False
        except Exception as e:
            self.logger.error(f"Failed to save knowledge base: {e}")

    def add_negative_feedback(self, source_type: str, target_type: str, penalty: float = -100.0):
        """ビルド失敗等の負の体験を記録し、将来のスコアリングに反映させる"""
        self.negative_feedbacks.append({
            "source_type": source_type,
            "target_type": target_type,
            "penalty": penalty,
            "timestamp": datetime.now().isoformat()
        })
        self.save_knowledge()

    def add_unresolved_symbol(self, symbol: str):
        """NuGet等でも解決できなかったシンボルを記録する"""
        if symbol not in self.unresolved_symbols:
            self.unresolved_symbols.append(symbol)
            self.save_knowledge()

    def get_negative_penalties(self) -> Dict[str, float]:
        """蓄積された負のフィードバックを統合したペナルティマップを返す"""
        penalties = {}
        for feedback in self.negative_feedbacks:
            key = f"{feedback['source_type']}->{feedback['target_type']}"
            penalties[key] = penalties.get(key, 0.0) + feedback.get('penalty', -100.0)
        return penalties

    def get_best_fix_direction(self, root_cause: str, error_message: str) -> Optional[str] :
        """原因とエラーメッセージから最適な修正方針を取得 (Hybrid Search優先)"""
        
        def kw_fn(item, query_keywords):
            # 文字列部分一致
            if item.get('error_message_regex') in error_message:
                return 1.0
            return 0.0

        results = self.hybrid_search(error_message, top_k=1, keyword_fn=kw_fn, semantic_weight=0.7)
        
        if results:
            best_pattern, score = results[0]
            if score >= self.semantic_threshold:
                self.logger.info(f"Semantic match found (score={score:.3f}): {best_pattern.get('error_message_regex')}")
                return best_pattern.get('fix_direction')
        
        return None

    def add_repair_experience(self, experience: Dict[str, Any]):
        """修復の成功体験を記録し、必要に応じて新しいパターンを学習 (ベクトル化含む)"""
        root_cause = experience.get('root_cause', 'unknown')
        error_type = experience.get('error_type') 
        fix_type = experience.get('fix_type')
        success = experience.get('success', False)
        
        if not error_type: return

        # 1. 統計の更新
        if root_cause not in self.fix_stats:
            self.fix_stats[root_cause] = {'total': 0, 'success': 0, 'fixes': {}}
        
        stats = self.fix_stats[root_cause]
        stats['total'] += 1
        if success:
            stats['success'] += 1
            if fix_type:
                stats['fixes'][fix_type] = stats['fixes'].get(fix_type, 0) + 1
        
        # 2. 新しいパターンの学習
        if success and fix_type:
            exists = any(p.get('error_message_regex') == error_type for p in self.items)
            
            if not exists:
                new_vec = self.vectorize_text(error_type)
                if new_vec is not None:
                    self.add_item({
                        'root_cause': root_cause,
                        'error_message_regex': error_type,
                        'fix_direction': fix_type,
                        'timestamp': datetime.now().isoformat()
                    }, new_vec, item_id_key="error_message_regex")
                    self.logger.info(f"Learned new semantic repair pattern: {error_type} -> {fix_type}")
        
        self.save_knowledge()


    def add_type_mapping(self, type_name: str, prop_name: str, suggested_value: str):
        """特定の型に対する不足プロパティの知識を蓄積"""
        if type_name not in self.type_mappings:
            self.type_mappings[type_name] = {}
            
        self.type_mappings[type_name][prop_name] = suggested_value
        self.save_knowledge()

    def learn_from_session_logs(self, log_dir: str):
        """セッションログから自律的に修復パターンを学習"""
        self.logger.info(f"Learning from logs in {log_dir}...")
        count = 0
        if not os.path.exists(log_dir):
            return

        for filename in os.listdir(log_dir):
            # LogManagerが出力する pipeline_*.json 形式をサポート
            if (filename.startswith('pipeline_') or filename.startswith('SESSION_COMPLETED')) and filename.endswith('.json'):
                try:
                    path = os.path.join(log_dir, filename)
                    with open(path, 'r', encoding='utf-8') as f:
                        # JSON Line形式と単一JSON形式の両方をサポート
                        for line in f:
                            line = line.strip()
                            if not line: continue
                            if line.endswith(','): line = line[:-1]
                            try:
                                session = json.loads(line)
                                count += self._extract_knowledge_from_session(session)
                            except:
                                continue
                except Exception as e:
                    self.logger.warning(f"Error parsing log {filename}: {e}")
        
        self.logger.info(f"Learned {count} new repair facts.")
        if count > 0:
            self.save_knowledge()

    def _extract_knowledge_from_session(self, session: Dict[str, Any]) -> int:
        data = session.get('data', {})
        history = data.get('history', [])
        found = 0
        
        # 0. セッション自体の分析結果も対象にする
        main_analysis = None
        if session.get('event_type') == 'SESSION_COMPLETED':
            ar = data.get('action_result', {}).get('analysis_result', {})
            if ar.get('analyses'):
                main_analysis = ar['analyses'][0]

        # 1. 分析結果を収集
        analyses = []
        if main_analysis: analyses.append(main_analysis)
        for turn in history:
            if turn.get('intent') == 'ANALYZE_TEST_FAILURE':
                ar = turn.get('action_result', {}).get('analysis_result', {})
                if ar.get('analyses'):
                    analyses.append(ar['analyses'][0])

        # 2. 修正が適用され、その後のテストが成功しているパターンを探す
        for i, turn in enumerate(history):
            action_result = turn.get('action_result', {})
            # 修正適用が成功したか (意図名が APPLY_CODE_FIX またはそれを含むもの)
            intent = turn.get('intent', '')
            if (intent == 'APPLY_CODE_FIX' or 'FIX' in intent) and action_result.get('status') == 'success':
                # 直近の分析結果と紐付け
                last_analysis = main_analysis # デフォルトはセッション全体の分析
                for j in range(i-1, -1, -1):
                    if history[j].get('intent') == 'ANALYZE_TEST_FAILURE':
                        ar = history[j].get('action_result', {}).get('analysis_result', {})
                        if ar.get('analyses'):
                            last_analysis = ar['analyses'][0]
                            break
                
                if not last_analysis: continue

                # 以降のターンのどこかで成功したか
                success_verified = False
                for k in range(i + 1, len(history)):
                    next_turn = history[k]
                    next_result = next_turn.get('action_result', {})
                    next_intent = next_turn.get('intent', '')
                    if ('TEST_RUN' in next_intent) and next_result.get('status') == 'success':
                        success_verified = True
                        break
                
                # 特例: セッション全体の最終結果が成功なら、それも成功とみなす
                if not success_verified and data.get('action_result', {}).get('status') == 'success':
                    success_verified = True

                if success_verified:
                    self.add_repair_experience({
                        'root_cause': last_analysis.get('root_cause'),
                        'error_type': last_analysis.get('error_type'),
                        'fix_type': last_analysis.get('fix_direction'),
                        'success': True
                    })
                    found += 1

        return found
        # TODO: Implement Logic: 「テスト失敗分析」の直後に「コード修正適用」があり、さらにその後に「テスト成功」が続いているシーケンスを「成功パターン」として抽出。
        # TODO: Implement Logic: 過去の正規表現パターンにマッチするエラーメッセージがあれば、その時の修正方針を返す。
        # TODO: Implement Logic: （将来的に）統計的に最も成功率の高い方針を優先的に提案するロジックを統合。
