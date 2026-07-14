import os
import json
import shutil
import numpy as np
from typing import List, Dict, Any, Optional
from src.symbol_matching.symbol_matcher import SymbolMatcher
from src.semantic_search.semantic_search_base import SemanticSearchBase
from src.code_synthesis.method_store_policy import MethodStorePolicy

class MethodStore(SemanticSearchBase):
    """
    メソッド部品のメタデータを管理し、指示文に基づいた意味検索を行うクラス。
    HybridSearch (Vector + Keyword) と定義済みの Scoring Rules を統合する。
    """
    def __init__(self, config, morph_analyzer=None, vector_engine=None):
        self._migrate_legacy_vector_store_files(config)
        if vector_engine is None:
            try:
                from src.vector_engine.vector_engine import VectorEngine
                model_path = getattr(config, "vector_model_path", None)
                if isinstance(model_path, str) and os.path.exists(model_path):
                    vector_engine = VectorEngine(model_path=model_path)
                else:
                    vector_engine = None
            except Exception:
                vector_engine = None
        if vector_engine is not None and hasattr(vector_engine, "is_ready") and not getattr(vector_engine, "is_ready", False):
            vector_engine = None
        super().__init__("method_store", config.storage_dir, vector_engine=vector_engine, morph_analyzer=morph_analyzer, config=config)
        self.config_manager = config
        self.policy = MethodStorePolicy(workspace_root=str(getattr(config, "workspace_root", os.getcwd())))
        self.matcher = SymbolMatcher(config_manager=config, morph_analyzer=morph_analyzer, vector_engine=vector_engine)

        root = getattr(config, 'workspace_root', getattr(config, 'root_dir', os.getcwd()))

        # Load Scoring Rules
        self.scoring_rules = {}
        rules_path = os.path.join(root, "config", "scoring_rules.json")
        if os.path.exists(rules_path):
            with open(rules_path, 'r', encoding='utf-8') as f:
                self.scoring_rules = json.load(f)

        self.metadata_by_id = {}
        self.load()

    def _migrate_legacy_vector_store_files(self, config):
        """旧配置の method_store ベクトルDBファイルを storage_dir へ統一する。"""
        workspace_root = getattr(config, "workspace_root", None)
        # テスト用の簡易Config等で workspace_root がない場合は移行しない。
        if not workspace_root:
            return

        target_dir = str(getattr(config, "storage_dir", "") or "")
        if not target_dir:
            return
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception:
            return

        root = str(workspace_root)
        legacy_dirs = [
            root,
            os.path.join(root, "resources"),
            os.path.join(root, "cache"),
        ]
        target_meta = os.path.join(target_dir, "method_store_meta.json")
        target_vec = os.path.join(target_dir, "method_store_vectors.npy")

        for legacy_dir in legacy_dirs:
            legacy_meta = os.path.join(legacy_dir, "method_store_meta.json")
            legacy_vec = os.path.join(legacy_dir, "method_store_vectors.npy")
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

    @property
    def methods(self) -> Dict[str, Any]:
        """Backward compatibility property for metadata_by_id."""
        return self.metadata_by_id

    @methods.setter
    def methods(self, value):
        """Backward compatibility setter to support legacy tests."""
        if isinstance(value, dict):
            self.metadata_by_id = value
            self.items = list(value.values())
        elif isinstance(value, list):
            self.items = value
            self.metadata_by_id = {str(item.get("id", item.get("name"))): item for item in value if isinstance(item, dict)}
        else:
            self.items = []
            self.metadata_by_id = {}
        if hasattr(self, "collection") and hasattr(self.collection, "items"):
            self.collection.items = list(self.items)

    def load(self):
        """メタデータをロードし、正当なシンボルのみをインデックスする"""
        super().load()
        # SemanticSearchBase.load() によって self.items に読み込まれたデータを検証
        valid_items = []
        for item in self.items:
            item = self.policy.normalize(item)
            if item is None:
                continue
            m_name = item.get("name", "")
            m_class = item.get("class", "")

            # 内部シンボル、ジェネリックメタ表記、特殊なアクセサを排除 (Synthesizable Member Policy)
            if '`' in m_name or '`' in m_class or '$' in m_name:
                continue
            if m_name.startswith('get_') or m_name.startswith('set_'):
                continue

            valid_items.append(item)

        self.items = valid_items
        self.metadata_by_id = {str(item.get("id", item.get("name"))): item for item in self.items}

    def add_method(self, method_data: Dict[str, Any], overwrite: bool = True):
        """新しいメソッドをストアに追加する (ベクトル化込み)"""
        method_data = self.policy.normalize(method_data)
        if method_data is None:
            return
        m_id = str(method_data.get("id", method_data.get("name")))

        if m_id in self.metadata_by_id:
            if not overwrite: return
            # 既存メタデータの継承 (Tier等の手動設定を保護)
            existing = self.metadata_by_id[m_id]
            for field in ["tier", "capability", "role", "intent"]:
                if field in existing and field not in method_data:
                    method_data[field] = existing[field]

        vec = self._vectorize_method(method_data)

        self.add_item(method_data, vec)
        self.metadata_by_id[m_id] = method_data

    def rebuild_index_from_source(self) -> int:
        """method_store.json を唯一の入力としてベクトルDBを再構築する。"""
        source_items = self._load_source_items()
        self.items = source_items
        self.metadata_by_id = {str(item.get("id", item.get("name"))): item for item in self.items}
        self._rebuild_collection_from_items()
        return len(self.items)

    def _load_source_items(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.metadata_path):
            return []
        with open(self.metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            raw_items = data.get("methods", [])
        else:
            raw_items = data
        items = []
        for item in raw_items if isinstance(raw_items, list) else []:
            normalized = self.policy.normalize(item)
            if normalized is not None:
                items.append(normalized)
        return items

    def _method_vector_text(self, method_data: Dict[str, Any]) -> str:
        parts = [
            method_data.get("name", ""),
            method_data.get("class", ""),
            method_data.get("summary", ""),
            method_data.get("definition", ""),
            method_data.get("code", ""),
        ]
        parts.extend(method_data.get("tags", []) or [])
        parts.extend(method_data.get("capabilities", []) or [])
        return " ".join(str(part) for part in parts if part)

    def _vector_dimension(self) -> int:
        vectors = getattr(self.collection, "vectors", None)
        if vectors is not None and getattr(vectors, "ndim", 0) == 2 and vectors.shape[1] > 0:
            return int(vectors.shape[1])
        if self.vector_engine is not None and hasattr(self.vector_engine, "dim"):
            try:
                return int(self.vector_engine.dim)
            except Exception:
                pass
        return 300

    def _vectorize_method(self, method_data: Dict[str, Any]) -> np.ndarray:
        vec = self.vectorize_text(self._method_vector_text(method_data))
        if vec is None:
            vec = np.zeros(self._vector_dimension(), dtype=np.float32)
        return vec

    def _rebuild_collection_from_items(self) -> None:
        if not hasattr(self, "collection") or self.collection is None:
            return
        self.collection.items = []
        self.collection.vectors = None
        self.collection.id_to_index = {}
        if not self.items:
            self.collection._save()
            return
        ids = [str(item.get("id", item.get("name"))) for item in self.items]
        vectors = [self._vectorize_method(item) for item in self.items]
        self.collection.upsert(ids, vectors, list(self.items))

    def save(self):
        """現在の状態をベクトルDBとソースJSONの両方に保存する"""
        if hasattr(self, "collection") and self.collection is not None:
            self.collection.items = list(self.items)
            if self.collection.vectors is None or len(self.collection.vectors) != len(self.items):
                self._rebuild_collection_from_items()
            else:
                self.collection.id_to_index = {str(item.get("id", item.get("name"))): idx for idx, item in enumerate(self.items)}
        # 1. ベクトルDB (cache/) の保存
        super().save()

        # 2. ソースJSON (resources/method_store.json) の保存
        try:
            # 常に最新の self.items を書き出す
            output_data = {"methods": self.items}
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved {len(self.items)} methods to {self.metadata_path}")
        except Exception as e:
            self.logger.error(f"Failed to save method_store.json: {e}")

    def get_method_by_id(self, m_id: str) -> Optional[Dict[str, Any]]:
        return self.metadata_by_id.get(str(m_id))

    def search(
        self,
        query: str,
        limit: int = 5,
        intent: str = None,
        role: str = None,
        cardinality: str = None,
        input_type: str = None,
        target_entity: str = None,
        required_capabilities: Optional[List[str]] = None,
        return_type: str = None,
    ) -> List[Dict[str, Any]]:
        """
        メソッド部品を検索する。
        基本検索のみを行い、詳細なランク付けは UnifiedKnowledgeBase に委ねる。
        """
        if not query: return []
        if not self.items:
            self.load()
        candidates = [
            item
            for item in self.items
            if self._matches_search_constraints(
                item,
                intent=intent,
                role=role,
                cardinality=cardinality,
                input_type=input_type,
                target_entity=target_entity,
                required_capabilities=required_capabilities,
                return_type=return_type,
            )
        ]

        if not self.vector_engine:
            return [
                {**item, "score": None}
                for item in sorted(
                    candidates,
                    key=lambda candidate: (
                        str(candidate.get("class", "")),
                        str(candidate.get("name", "")),
                        str(candidate.get("id", "")),
                    ),
                )[:limit]
            ]

        # 2. 基本検索
        raw_results = self.hybrid_search(
            query,
            top_k=max(len(self.items), limit),
        )
        allowed_ids = {
            str(item.get("id", item.get("name")))
            for item in candidates
        }

        ranked_results = []
        for item, score in raw_results:
            item_id = item.get("id")
            if str(item_id or item.get("name")) not in allowed_ids:
                continue
            meta = self.metadata_by_id.get(item_id, item)

            # 基本的な類似度と情報を保持して UnifiedKnowledgeBase へ渡す
            item_copy = item.copy()
            for field in ["tier", "capability", "capabilities", "role", "intent", "params", "return_type"]:
                if field in meta:
                    item_copy[field] = meta[field]

            item_copy["score"] = score
            ranked_results.append(item_copy)
            if len(ranked_results) == limit:
                break

        return ranked_results[:limit]

    @staticmethod
    def _matches_search_constraints(
        item: Dict[str, Any],
        *,
        intent: Optional[str],
        role: Optional[str],
        cardinality: Optional[str],
        input_type: Optional[str],
        target_entity: Optional[str],
        required_capabilities: Optional[List[str]],
        return_type: Optional[str],
    ) -> bool:
        item_capabilities = set(item.get("capabilities") or [])
        if intent is not None and (
            item.get("intent") != intent
            and item.get("role") != intent
            and intent not in item_capabilities
        ):
            return False
        if role is not None and item.get("role") != role:
            return False
        required = set(required_capabilities or [])
        if not required.issubset(item_capabilities):
            return False
        if return_type is not None and item.get("return_type") != return_type:
            return False
        if input_type is not None:
            parameter_types = {
                parameter.get("type")
                for parameter in item.get("params", [])
                if isinstance(parameter, dict)
            }
            if input_type not in parameter_types:
                return False
        if target_entity is not None:
            declared_entity = item.get("target_entity")
            if declared_entity is not None and declared_entity != target_entity:
                return False
        if cardinality is not None:
            declared_cardinality = item.get("cardinality")
            if (
                declared_cardinality is not None
                and declared_cardinality != cardinality
            ):
                return False
        return True

