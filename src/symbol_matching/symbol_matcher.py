# -*- coding: utf-8 -*-
import json
import os
from typing import Dict, List, Any, Optional, Tuple

class SymbolMatcher:
    """日本語の設計文と英語のコードシンボルを橋渡しするマッチングエンジン"""

    def __init__(self, config_manager=None, morph_analyzer=None, vector_engine=None, knowledge_base=None):
        self.config_manager = config_manager
        self.morph_analyzer = morph_analyzer
        self.vector_engine = vector_engine
        self.knowledge_base = knowledge_base
        self.domain_dict = self._load_domain_dictionary()

    def calculate_semantic_similarity(self, sentence: str, symbol_name: str) -> float:
        """文章とシンボル名の意味的類似度を計算する"""
        if not self.vector_engine:
            return 0.0

        # 1. 文章のベクトル化
        sentence_tokens = self.extract_keywords(sentence)
        sentence_vec = self.vector_engine.get_sentence_vector(sentence_tokens)

        # 2. シンボルのベクトル化 (トークン分割して平均)
        symbol_tokens = self.tokenize_symbol(symbol_name)
        symbol_vec = self.vector_engine.get_sentence_vector(symbol_tokens)

        if sentence_vec is not None and symbol_vec is not None:
            return self.vector_engine.vector_similarity(sentence_vec, symbol_vec)
        return 0.0

    def _load_domain_dictionary(self) -> Dict[str, List[str]]:
        base_mappings: Dict[str, List[str]] = {}
        if self.knowledge_base and hasattr(self.knowledge_base, "get"):
            kb_mappings = self.knowledge_base.get("domain_mappings", {})
            if isinstance(kb_mappings, dict):
                base_mappings.update(kb_mappings)

        if not self.config_manager:
            return base_mappings

        dict_path = self.config_manager.domain_dictionary_path
        if os.path.exists(dict_path):
            try:
                with open(dict_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    user_mappings = data.get("mappings", {})
                    if isinstance(user_mappings, dict):
                        base_mappings.update(user_mappings)
            except Exception:
                pass
        return base_mappings

    def _expand_domain_terms(self, tokens: List[str]) -> List[str]:
        if not tokens or not self.domain_dict:
            return tokens
        expanded: List[str] = []
        seen = set()
        for tok in tokens:
            if not tok:
                continue
            if tok not in seen:
                expanded.append(tok)
                seen.add(tok)
            synonyms = self.domain_dict.get(tok)
            if not synonyms:
                continue
            for syn in synonyms:
                if syn and syn not in seen:
                    expanded.append(syn)
                    seen.add(syn)
        return expanded

    def get_compatible_properties(self, properties: Dict[str, str], operator: str, hint_text: str = "") -> List[str]:
        """演算子とヒント文に適合するプロパティのみを抽出する (制約充足)"""
        numeric_ops = ["Greater", "GreaterEqual", "Less", "LessEqual", "Percent", "Percent_Discount"]
        string_ops = ["Contains", "StartsWith", "EndsWith"]

        candidates = []
        for p_name, p_type in properties.items():
            p_type_low = p_type.lower()

            # 1. 物理的な型制約のチェック
            if operator in numeric_ops:
                if not any(k in p_type_low for k in ["int", "decimal", "double", "float", "long", "short"]):
                    continue
            elif operator in string_ops:
                if "string" not in p_type_low:
                    continue

            # 2. 意味的な適合度の評価 (類似度が極端に低いものは除外)
            if hint_text:
                sim = self.calculate_semantic_similarity(hint_text, p_name)
                if sim > 0.25:
                    candidates.append((p_name, sim))
            else:
                candidates.append((p_name, 0.0))

        # 3. 優先順位: 類似度
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in candidates]
    def is_semantic_match(self, symbol: str, sentence: str, threshold: float = 0.35) -> bool:
        """指定されたシンボルが文章の意味と合致するか判定する (決定論的アプローチ)"""
        # ベクトルベースの類似度のみで判定
        if self.vector_engine:
            similarity = self.calculate_semantic_similarity(sentence, symbol)
            if similarity > threshold:
                return True

        return False

    def search_existence_check(self, text: str, target_entity: str) -> List[Dict[str, Any]]:
        """存在チェックに関連するメソッドテンプレートを検索する"""
        # IRGenerator/Synthesizer が UKB を持っているため、そこから検索
        if hasattr(self, 'synthesizer') and self.synthesizer.ukb:
            return self.synthesizer.ukb.search(text, limit=5, intent="EXISTS", target_entity=target_entity)
        return []


    def tokenize_symbol(self, symbol_name: str) -> List[str]:
        """PascalCase or CamelCase symbol to lowercase tokens."""
        if not symbol_name:
            return []
        tokens: List[str] = []
        current = []
        prev_is_lower = False
        prev_is_alpha = False
        for ch in symbol_name:
            if not ch.isalnum():
                if current:
                    tokens.append("".join(current).lower())
                    current = []
                prev_is_lower = False
                prev_is_alpha = False
                continue
            is_upper = ch.isalpha() and ch.isupper()
            is_lower = ch.isalpha() and ch.islower()
            if current and is_upper and (prev_is_lower or (prev_is_alpha and not prev_is_lower)):
                tokens.append("".join(current).lower())
                current = [ch]
            else:
                current.append(ch)
            prev_is_lower = is_lower
            prev_is_alpha = ch.isalpha()
        if current:
            tokens.append("".join(current).lower())
        return [t for t in tokens if t]

    def extract_keywords(self, sentence: str) -> List[str]:
        """Extract Japanese and English keywords from a sentence."""
        if self.morph_analyzer:
            context = {"original_text": sentence}
            res = self.morph_analyzer.analyze(context)
            tokens = res.get("analysis", {}).get("tokens", [])
            keywords = [t["base"] for t in tokens if t["pos"].startswith(("名詞", "動詞"))]
            expanded = self._expand_domain_terms(keywords)
            return list(dict.fromkeys(expanded))
        else:
            return self._expand_domain_terms(list(sentence))

    def find_best_match(self, sentence: str, candidates: List[str], intent: str = None) -> Tuple[Optional[str], float]:
        """制約を満たす最適なシンボルを選択する (スコアリングを廃止し、フィルタリングと優先順位で決定)"""
        if not candidates:
            return None, 0.0
        if not self.vector_engine:
            keywords: List[str] = []
            if self.morph_analyzer:
                keywords = self.extract_keywords(sentence)
            else:
                keywords = [t for t in str(sentence).split() if t]
            synonyms: List[str] = []
            seen = set()
            for k in keywords:
                if not k:
                    continue
                if k not in seen:
                    synonyms.append(k)
                    seen.add(k)
                mapped = self.domain_dict.get(k)
                if mapped:
                    for syn in mapped:
                        if syn and syn not in seen:
                            synonyms.append(syn)
                            seen.add(syn)
            for syn in synonyms:
                syn_low = syn.lower()
                for cand in candidates:
                    if cand.lower() == syn_low:
                        return cand, 0.0
                    for token in self.tokenize_symbol(cand):
                        if token == syn_low:
                            return cand, 0.0
            sent_clean = str(sentence).strip().strip("\"' ")
            for cand in candidates:
                if cand.lower() == sent_clean.lower():
                    return cand, 0.0
            return None, 0.0

        # 1. 意味的にマッチしないものを物理排除 (Constraint Filtering)
        valid_candidates = []
        for cand in candidates:
            if self.is_semantic_match(cand, sentence):
                valid_candidates.append(cand)

        if not valid_candidates:
            # 緩和された閾値で再試行
            for cand in candidates:
                if self.is_semantic_match(cand, sentence, threshold=0.25):
                    valid_candidates.append(cand)

        if not valid_candidates: return None, 0.0

        final_list = valid_candidates

        # 3. 決定論的な優先順位付け (Tie-breaking)
        # スコアの代わりに、以下の順序でソート:
        # 1. 類似度 (Similarity) - これ自体は浮動小数点だが、唯一の動的指標
        # 2. シンボル名の短さ (Shortest is best / Minimal principle)
        # 3. アルファベット順

        results = []
        for cand in final_list:
            sim = self.calculate_semantic_similarity(sentence, cand)
            results.append((cand, sim))

        results.sort(key=lambda x: (x[1], -len(x[0]), x[0]), reverse=True)
        return results[0]
