# -*- coding: utf-8 -*-
import os
import re
from typing import List, Dict, Any

class SyntacticAnalyzer:
    """
    形態素解析結果に基づき、日本語の文節分割と係り受け構造（構文木）を解析するクラス。
    決定論的なルールに基づき、軽量かつ予測可能な解析を行う。
    """
    def __init__(self, config_manager=None):
        self.config_manager = config_manager

    def analyze(self, context: dict) -> dict:
        context.setdefault("analysis", {})
        context.setdefault("pipeline_history", [])
        
        if "tokens" not in context["analysis"]:
            context.setdefault("errors", []).append({
                "module": "syntactic_analyzer",
                "message": "分析するトークンがありません。形態素解析が先に行われている必要があります。"
            })
            return context

        tokens = context["analysis"]["tokens"]
        if not tokens:
            context["analysis"]["chunks"] = []
            context["analysis"]["syntax_tree"] = []
            context["pipeline_history"].append("syntactic_analyzer")
            return context

        # 1. 文節分割 (Chunking)
        chunks = self._chunk_tokens(tokens)
        
        # 2. 係り受け解析 (Dependency Parsing)
        self._parse_dependencies(chunks)
        
        # Backward Compatibility: analysis.chunks (List of token lists)
        context["analysis"]["chunks"] = [node["tokens"] for node in chunks]
        
        # New Feature: analysis.syntax_tree (List of Node dicts)
        context["analysis"]["syntax_tree"] = chunks
        
        context["pipeline_history"].append("syntactic_analyzer")
        return context

    def _chunk_tokens(self, tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """トークンを文節単位にまとめる"""
        chunks = []
        current_chunk_tokens = []
        
        for i, token in enumerate(tokens):
            pos = token["pos"]
            surface = token["surface"]
            
            # 新しい文節を開始する条件 (自立語系)
            # 名詞、動詞（自立）、形容詞、連体詞、副詞、接続詞、感動詞、記号
            is_independent = any(pos.startswith(p) for p in ["名詞", "動詞,自立", "形容詞", "連体詞", "副詞", "接続詞", "感動詞", "記号"])
            
            # 数値リテラルの連続などを考慮
            if is_independent and current_chunk_tokens:
                # 前のトークンが接頭辞の場合は分離しない
                if not current_chunk_tokens[-1]["pos"].startswith("接頭辞"):
                    # 現在のトークンが助詞・助動詞でないなら、新しい文節を開始
                    if not any(pos.startswith(p) for p in ["助詞", "助動詞", "動詞,非自立"]):
                        chunks.append(self._create_chunk_node(len(chunks), current_chunk_tokens))
                        current_chunk_tokens = []

            current_chunk_tokens.append(token)

        if current_chunk_tokens:
            chunks.append(self._create_chunk_node(len(chunks), current_chunk_tokens))
            
        return chunks

    def _create_chunk_node(self, node_id: int, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
        surface = "".join([t["surface"] for t in tokens])
        return {
            "id": node_id,
            "surface": surface,
            "tokens": tokens,
            "head": -1,
            "dep_type": "ROOT"
        }

    def _parse_dependencies(self, chunks: List[Dict[str, Any]]):
        """文末から逆向きに走査して係り受けを決定する（簡易ルールベース）"""
        n = len(chunks)
        for i in range(n - 1): # 最後の文節は常に ROOT
            current = chunks[i]
            last_token = current["tokens"][-1]
            last_pos = last_token["pos"]
            last_surface = last_token["surface"]
            
            # 係り先を探す（常に自分より後ろ）
            found_head = False
            for j in range(i + 1, n):
                target = chunks[j]
                target_first_pos = target["tokens"][0]["pos"]
                target_main_pos = self._get_main_pos(target)
                
                # ルール1: 「の」は直後の名詞に係る
                if last_surface == "の" and "名詞" in target_first_pos:
                    self._set_dep(current, j, "MOD")
                    found_head = True; break
                
                # ルール2: 「が」「を」などの格助詞は、後ろにある最も近い述語（動詞・形容詞）に係る
                if any(k in last_surface for k in ["が", "を", "に", "へ", "と"]):
                    if "動詞" in target_main_pos or "形容詞" in target_main_pos:
                        dep = "SUBJ" if "が" in last_surface else "OBJ"
                        self._set_dep(current, j, dep)
                        found_head = True; break
                
                # ルール3: 「より」は比較表現に係る
                if last_surface == "より" and any(k in target["surface"] for k in ["大きい", "小さい", "超える", "未満", "以上", "以下"]):
                    self._set_dep(current, j, "COMP")
                    found_head = True; break

                # ルール4: 連体修飾 (接頭辞や連体詞など)
                if "連体詞" in last_pos or "名詞" in last_pos:
                    if "名詞" in target_first_pos:
                        self._set_dep(current, j, "MOD")
                        found_head = True; break

            # デフォルト: 最も近い後ろの文節に係る
            if not found_head:
                self._set_dep(current, i + 1, "MOD")

    def _get_main_pos(self, chunk: Dict[str, Any]) -> str:
        """文節内の主要な品詞を返す"""
        for t in chunk["tokens"]:
            if any(p in t["pos"] for p in ["名詞", "動詞", "形容詞"]):
                return t["pos"]
        return chunk["tokens"][0]["pos"]

    def _set_dep(self, node: Dict[str, Any], head_id: int, dep_type: str):
        node["head"] = head_id
        node["dep_type"] = dep_type

if __name__ == '__main__':
    # 単体テスト
    from src.morph_analyzer.morph_analyzer import MorphAnalyzer
    m_analyzer = MorphAnalyzer()
    s_analyzer = SyntacticAnalyzer()
    
    text = "価格が100より大きいユーザーを抽出する"
    context = {"original_text": text}
    context = m_analyzer.analyze(context)
    context = s_analyzer.analyze(context)
    
    print(f"Text: {text}")
    for node in context["analysis"]["syntax_tree"]:
        head_text = context["analysis"]["syntax_tree"][node["head"]]["surface"] if node["head"] != -1 else "NONE"
        print(f" [{node['id']}] {node['surface']} ({node['dep_type']}) -> {head_text}")
