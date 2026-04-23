# -*- coding: utf-8 -*-
import os
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from src.utils.text_parser import extract_quoted_literals

class LogicAuditor:
    """仕様(DesignDoc)と実装(SourceStructure)の整合性を監査するクラス"""

    def __init__(self, config_manager=None, morph_analyzer=None, vector_engine=None, knowledge_base=None):
        self.config = config_manager
        self.morph_analyzer = morph_analyzer
        self.vector_engine = vector_engine
        self.ukb = knowledge_base

    def _load_logic_audit_config(self) -> Dict[str, Any]:
        if self.ukb and hasattr(self.ukb, "get"):
            data = self.ukb.get("logic_audit", {})
            if isinstance(data, dict):
                return data
        return {}

    def extract_assertion_goals(self, design_steps: List[str]) -> List[Dict[str, Any]]:
        """設計ステップから論理制約を抽出し、正規化された演算子を返す (セマンティック解析版)"""
        goals: List[Dict[str, Any]] = []
        
        audit_cfg = self._load_logic_audit_config()
        # 演算子概念を代表するセマンティック・アンカー (Vector空間での重心)
        operator_anchors = audit_cfg.get("operator_anchors") if isinstance(audit_cfg.get("operator_anchors"), dict) else {
            "GreaterEqual": ["以上", "下回らない", "最低"],
            "LessEqual": ["以下", "超えない", "上限"],
            "Greater": ["より大きい", "超える", "上回る", "超過", "より多い"],
            "Less": ["より小さい", "未満", "下回る", "不足", "より少ない"],
            "NotEqual": ["以外", "異なり", "不一致", "除外"],
            "Equal": ["等しい", "一致", "同じ", "である", "タイプが"],
            "Contains": ["包含", "含む", "含める", "contains"],
            "StartsWith": ["始まり", "始まる", "前方一致", "starts"]
        }
        operator_direct_map = audit_cfg.get("operator_direct_map") if isinstance(audit_cfg.get("operator_direct_map"), dict) else {}

        for step in design_steps:
            step_text = self._strip_bracket_tags(str(step))
            tokens = []
            if self.morph_analyzer:
                res = self.morph_analyzer.analyze({"original_text": step_text})
                tokens = res.get("analysis", {}).get("tokens", [])
            matches: List[Tuple[int, Dict[str, Any]]] = []

            # Numeric literals (no regex)
            for start, end, val in self._extract_numeric_literals(step_text):
                var_hint, op_candidate, target_hint = self._resolve_semantic_context(step_text, start, end, tokens)
                found_op = self._match_operator_semantically(op_candidate, operator_anchors, operator_direct_map)
                matches.append((start, {
                    "type": "numeric", "operator": found_op, "expected_value": val,
                    "variable_hint": var_hint, "target_hint": target_hint, "original_step": step_text
                }))

            # Quoted literals (no regex)
            for start, end, val in self._extract_quoted_literals_with_spans(step_text):
                if not val:
                    continue
                var_hint, op_candidate, target_hint = self._resolve_semantic_context(step_text, start, end, tokens)
                found_op = self._match_operator_semantically(op_candidate, operator_anchors, operator_direct_map)
                matches.append((start, {
                    "type": "string", "operator": found_op, "expected_value": val,
                    "variable_hint": var_hint, "target_hint": target_hint, "original_step": step_text
                }))

            matches.sort(key=lambda x: x[0])
            for _, m in matches:
                goals.append(m)

        return goals

    def _strip_bracket_tags(self, text: str) -> str:
        if not text:
            return ""
        result = []
        depth = 0
        for ch in str(text):
            if ch == "[":
                depth += 1
                continue
            if ch == "]":
                if depth > 0:
                    depth -= 1
                    continue
            if depth == 0:
                result.append(ch)
        return "".join(result).strip()

    # Backward-compatible entry used by aligners and refiners
    def audit(self, design_data: Any, source_structure: Any = None, code: str = "", *args, **kwargs) -> Any:
        # If a plain list of steps is provided, keep legacy behavior.
        if isinstance(design_data, list):
            goals = self.extract_assertion_goals(design_data)
            return self.verify_logic_goals(goals, code)

        # Structured design doc path: return an audit report dict.
        design_steps = []
        if isinstance(design_data, dict):
            design_steps = design_data.get("specification", {}).get("core_logic", []) or []

        findings = []
        total = len(design_steps)
        missing = 0

        def _normalize_step(step: str) -> str:
            text = (step or "").strip()
            i = 0
            while i < len(text) and (text[i].isdigit() or text[i] in [".", " ", "\t"]):
                i += 1
            return text[i:].strip()

        def _is_step_covered(step: str, code_text: str) -> bool:
            if not step or not code_text:
                return False
            if not self.vector_engine:
                return False
            if self.morph_analyzer:
                step_tokens = self.morph_analyzer.tokenize(step)
                step_tokens = [t["surface"] if isinstance(t, dict) else str(t) for t in step_tokens]
            else:
                step_tokens = self._tokenize_fallback(step)
            code_snippet = code_text[:1000]
            if self.morph_analyzer:
                code_tokens = self.morph_analyzer.tokenize(code_snippet)
                code_tokens = [t["surface"] if isinstance(t, dict) else str(t) for t in code_tokens]
            else:
                code_tokens = self._tokenize_fallback(code_snippet)
            step_vec = self.vector_engine.get_sentence_vector(step_tokens)
            code_vec = self.vector_engine.get_sentence_vector(code_tokens)
            if step_vec is None or code_vec is None:
                return False
            sim = self.vector_engine.vector_similarity(step_vec, code_vec)
            return sim > 0.35

        for idx, raw_step in enumerate(design_steps, start=1):
            step_text = _normalize_step(str(raw_step))
            if not _is_step_covered(step_text, code):
                missing += 1
                findings.append({
                    "type": "logic_gap",
                    "detail": f"Missing logic for step '{step_text}'",
                    "step_index": idx,
                    "step_text": step_text
                })

        consistency = 1.0 if total == 0 else max(0.0, (total - missing) / total)
        status = "consistent" if not findings else "inconsistent"
        return {
            "status": status,
            "consistency_score": consistency,
            "findings": findings
        }

    def verify_logic_goals(self, goals: List[Dict[Any, Any]], code: str) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        if not goals:
            return findings
        if not isinstance(code, str) or not code:
            for goal in goals:
                findings.append({
                    "reason": "logic_gap",
                    "detail": f"Goal not verified (empty code). expected={goal.get('expected_value')}",
                    "goal": goal
                })
            return findings

        goal_hits: List[Tuple[int, int]] = []
        for g_idx, goal in enumerate(goals, start=1):
            g_type = goal.get("type")
            expected = str(goal.get("expected_value") or "")
            if g_type == "numeric":
                if expected == "{input}":
                    if not self._code_has_input_var(code):
                        findings.append({
                            "reason": "LOGIC_VALUE_MISMATCH",
                            "detail": "Expected input placeholder but no input variable found in code.",
                            "goal": goal
                        })
                        continue
                    goal_hits.append((g_idx, 0))
                    continue
                elif not expected or not self._is_number_literal(expected):
                    continue
                if self._numeric_goal_uses_string_op(code, expected):
                    findings.append({
                        "reason": "LOGIC_OPERATOR_MISMATCH",
                        "detail": f"Numeric goal uses string operator for value {expected}.",
                        "goal": goal
                    })
                    continue
                hit = self._numeric_goal_hit(goal, code)
                if hit is None:
                    findings.append({
                        "reason": "numeric_goal_missing",
                        "detail": f"Numeric goal not found: {goal.get('operator')} {expected}",
                        "goal": goal
                    })
                else:
                    goal_hits.append((g_idx, hit))
            elif g_type == "string":
                if not expected:
                    continue
                hit = self._string_goal_hit(goal, code)
                if hit is None:
                    findings.append({
                        "reason": "string_goal_missing",
                        "detail": f"String goal not found: {goal.get('operator')} \"{expected}\"",
                        "goal": goal
                    })
                else:
                    goal_hits.append((g_idx, hit))
        if len(goal_hits) >= 2:
            last_pos = goal_hits[0][1]
            for idx, pos in goal_hits[1:]:
                if pos < last_pos:
                    findings.append({
                        "reason": "order_mismatch",
                        "detail": f"Goal order mismatch at goal index {idx} (pos {pos} < {last_pos})",
                        "goal_index": idx
                    })
                    break
                last_pos = pos
        return findings

    def _code_has_input_var(self, code: str) -> bool:
        tokens = self._simple_tokenize(code)
        if "input" in tokens:
            return True
        for tok in tokens:
            if tok.startswith("input_"):
                return True
        return False

    def _numeric_goal_uses_string_op(self, code: str, expected: str) -> bool:
        if not expected:
            return False
        # Detect StartsWith/Contains usage with numeric literal
        val = str(expected)
        if f".StartsWith(\"{val}\")" in code or f".StartsWith('{val}')" in code:
            return True
        if f".Contains(\"{val}\")" in code or f".Contains('{val}')" in code:
            return True
        return False

    def _numeric_goal_hit(self, goal: Dict[str, Any], code: str) -> int | None:
        val = str(goal.get("expected_value") or "")
        if not val:
            return 0
        op = str(goal.get("operator") or "")
        tokens = self._simple_tokenize(code)
        hit = self._find_numeric_op_index(tokens, op, val, goal)
        if hit is not None:
            return hit
        matches = self._find_numeric_matches(code, val)
        if matches:
            return matches[0][0]
        if self._is_equivalent_numeric(goal, code):
            return code.find(val) if val in code else 0
        return None

    def _string_goal_hit(self, goal: Dict[str, Any], code: str) -> int | None:
        val = str(goal.get("expected_value") or "")
        if not val:
            return 0
        op = str(goal.get("operator") or "")
        tokens = self._simple_tokenize(code)
        hit = self._find_string_op_index(tokens, op, val, goal)
        if hit is not None:
            return hit
        idx = code.find(val)
        if idx != -1:
            return idx
        if self._has_string_op_for_value(code, val):
            return code.find(val) if val in code else 0
        return None

    def _simple_tokenize(self, code: str) -> List[str]:
        if not isinstance(code, str) or not code:
            return []
        tokens: List[str] = []
        buf = ""
        i = 0
        specials = set("(){}[],;")
        two_char = {"==", "!=", ">=", "<="}
        while i < len(code):
            ch = code[i]
            if ch.isspace():
                if buf:
                    tokens.append(buf)
                    buf = ""
                i += 1
                continue
            if i + 1 < len(code):
                pair = ch + code[i + 1]
                if pair in two_char:
                    if buf:
                        tokens.append(buf)
                        buf = ""
                    tokens.append(pair)
                    i += 2
                    continue
            if ch in "<>=":
                if buf:
                    tokens.append(buf)
                    buf = ""
                tokens.append(ch)
                i += 1
                continue
            if ch in specials:
                if buf:
                    tokens.append(buf)
                    buf = ""
                tokens.append(ch)
                i += 1
                continue
            buf += ch
            i += 1
        if buf:
            tokens.append(buf)
        return tokens

    def _tokenize_fallback(self, text: str) -> List[str]:
        if not isinstance(text, str) or not text:
            return []
        tokens: List[str] = []
        buf = []
        for ch in text:
            if ch.isalnum() or ch == "_":
                buf.append(ch.lower())
            else:
                if buf:
                    tokens.append("".join(buf))
                    buf = []
        if buf:
            tokens.append("".join(buf))
        return tokens

    def _find_numeric_op_index(self, tokens: List[str], op: str, val: str, goal: Dict[str, Any]) -> int | None:
        op_map = {
            "GreaterEqual": ">=",
            "Greater": ">",
            "LessEqual": "<=",
            "Less": "<",
            "Equal": "==",
            "NotEqual": "!=",
        }
        symbol = op_map.get(op) or op
        if symbol not in [">=", ">", "<=", "<", "==", "!="]:
            return None
        var_hint = str(goal.get("variable_hint") or "")
        for i, tok in enumerate(tokens):
            if tok != symbol:
                continue
            left = tokens[i - 1] if i - 1 >= 0 else ""
            right = tokens[i + 1] if i + 1 < len(tokens) else ""
            if right != val and left != val:
                continue
            if var_hint:
                if left == var_hint or right == var_hint:
                    return i
                continue
            return i
        return None

    def _find_string_op_index(self, tokens: List[str], op: str, val: str, goal: Dict[str, Any]) -> int | None:
        var_hint = str(goal.get("variable_hint") or "")
        if op in ["Equal", "NotEqual"]:
            symbol = "==" if op == "Equal" else "!="
            for i, tok in enumerate(tokens):
                if tok != symbol:
                    continue
                left = tokens[i - 1] if i - 1 >= 0 else ""
                right = tokens[i + 1] if i + 1 < len(tokens) else ""
                if right != f"\"{val}\"" and left != f"\"{val}\"" and right != f"'{val}'" and left != f"'{val}'":
                    continue
                if var_hint:
                    if left == var_hint or right == var_hint:
                        return i
                    continue
                return i
            return None
        if op in ["Contains", "StartsWith"]:
            call = f".{op}("
            joined = "".join(tokens)
            if call in joined and val in joined:
                if not var_hint:
                    return joined.find(call)
                return joined.find(call) if var_hint in joined else None
        return None

    def _find_numeric_matches(self, code: str, value: str):
        matches = []
        if not isinstance(value, str) or not value:
            return matches
        start = 0
        while True:
            idx = code.find(value, start)
            if idx == -1:
                break
            matches.append((idx, idx + len(value)))
            start = idx + len(value)
        return matches

    def _is_equivalent_numeric(self, goal: Dict[str, Any], code: str) -> bool:
        op = goal.get("operator")
        val = str(goal.get("expected_value") or goal.get("value", ""))
        if not op or not val or not self._is_number_literal(val):
            return False
        try:
            num = float(val)
        except ValueError:
            return False
        if op == "GreaterEqual" and num == 1:
            return ">0" in code.replace(" ", "")
        if op == "Greater" and num == 0:
            return ">=1" in code.replace(" ", "")
        return False

    def _match_operator_semantically(self, op_text: str, anchors: Dict[str, List[str]], direct_map: Dict[str, str] | None = None) -> str:
        if not op_text: return "Equal"
        if direct_map:
            for key, op in direct_map.items():
                if key and key in op_text:
                    return op
        if ">=" in op_text:
            return "GreaterEqual"
        if "<=" in op_text:
            return "LessEqual"
        if ">" in op_text:
            return "Greater"
        if "<" in op_text:
            return "Less"
        for op, phrases in anchors.items():
            for phrase in phrases:
                if phrase and phrase in op_text:
                    return op
        if self.morph_analyzer and not self.vector_engine:
            try:
                op_tokens = self.morph_analyzer.tokenize(op_text)
                op_terms = set()
                for t in op_tokens:
                    base = t.get("base") or t.get("base_form")
                    surface = t.get("surface")
                    if base:
                        op_terms.add(str(base))
                    if surface:
                        op_terms.add(str(surface))
                if op_terms:
                    for op, phrases in anchors.items():
                        for phrase in phrases:
                            if not phrase:
                                continue
                            phrase_tokens = self.morph_analyzer.tokenize(phrase)
                            phrase_terms = []
                            for pt in phrase_tokens:
                                base = pt.get("base") or pt.get("base_form")
                                surface = pt.get("surface")
                                if base:
                                    phrase_terms.append(str(base))
                                if surface and surface != base:
                                    phrase_terms.append(str(surface))
                            if phrase_terms and all(term in op_terms for term in phrase_terms):
                                return op
            except Exception:
                pass
        if self.vector_engine:
            # ... (rest of vector logic) ...
            query_vec = self.vector_engine.get_sentence_vector([op_text])
            if query_vec is not None:
                max_sim, best_op = 0.0, "Equal"
                for op, phrases in anchors.items():
                    for p in phrases:
                        sim = self.vector_engine.vector_similarity(query_vec, self.vector_engine.get_sentence_vector([p]))
                        if sim > max_sim: max_sim = sim; best_op = op
                if max_sim > 0.6: return best_op
        return "Equal"

    def _has_string_op_for_value(self, code: str, value: str) -> bool:
        if not isinstance(code, str) or not isinstance(value, str):
            return False
        if not value or value == "{input}":
            return False
        val = value
        if f".StartsWith(\"{val}\")" in code or f".StartsWith('{val}')" in code:
            return True
        if f".Contains(\"{val}\")" in code or f".Contains('{val}')" in code:
            return True
        return False

    def _resolve_semantic_context(self, step: str, start: int, end: int, tokens: List[Dict]) -> Tuple[str, str, Optional[str]]:
        var_hint, op_candidate, target_hint = "", "", None
        audit_cfg = self._load_logic_audit_config()
        
        current_pos = 0
        token_with_pos = []
        for t in tokens:
            t_pos = step.find(t["surface"], current_pos)
            if t_pos != -1:
                token_with_pos.append({"token": t, "start": t_pos, "end": t_pos + len(t["surface"])})
                current_pos = t_pos + len(t["surface"])

        # 1. 前方の名詞（変数ヒント）を探す
        for i in range(len(token_with_pos) - 1, -1, -1):
            twp = token_with_pos[i]
            if twp["end"] <= start:
                if (start - twp["end"]) < 15 and twp["token"]["pos"].startswith("名詞"):
                    # 連続する名詞は結合して複合名詞として扱う
                    parts = [twp]
                    j = i - 1
                    while j >= 0:
                        prev = token_with_pos[j]
                        if not prev["token"]["pos"].startswith("名詞"):
                            break
                        # ほぼ隣接している場合のみ結合対象にする
                        if prev["end"] <= parts[0]["start"] and (parts[0]["start"] - prev["end"]) <= 1:
                            parts.insert(0, prev)
                            j -= 1
                            continue
                        break

                    # surface を優先し、なければ base
                    combined = "".join(p["token"].get("surface") or p["token"].get("base", "") for p in parts)
                    if combined and combined not in ["%", "％", "の", "を", "は", "が"]:
                        var_hint = combined
                        break

        # 2. 後方の述語（演算子候補）を探す
        for twp in token_with_pos:
            if twp["start"] >= end:
                if (twp["start"] - end) < 20:
                    op_candidate += twp["token"]["surface"]
                else:
                    break

        # 3. 構文的な役割判定: 「〜として」「〜に」「〜へ」を伴う名詞をターゲットとして特定
        # 27.205: Abduction of target property from syntactic role (Case marking)
        role_markers = audit_cfg.get("role_markers", ["として", "に", "へ"])
        for i in range(len(token_with_pos) - 1):
            curr = token_with_pos[i]; nxt = token_with_pos[i+1]
            if curr["token"]["pos"].startswith("名詞") and nxt["token"]["surface"] in role_markers:
                # 直前の「を」などの目的格を除外した純粋な名詞を抽出
                target_hint = curr["token"]["base"]
                break

        if not op_candidate:
            op_candidate = step[end:min(len(step), end+20)]
        if op_candidate:
            for sep in ["、", "かつ", "または", "及び", "そして", "and", "or"]:
                idx = op_candidate.find(sep)
                if idx != -1:
                    op_candidate = op_candidate[:idx]
                    break
        return var_hint, op_candidate, target_hint

    def _extract_numeric_literals(self, text: str) -> List[Tuple[int, int, str]]:
        results = []
        if not text:
            return results
        i = 0
        s = str(text)
        while i < len(s):
            if s[i].isdigit():
                j = i + 1
                while j < len(s) and s[j].isdigit():
                    j += 1
                if j < len(s) and s[j] == ".":
                    k = j + 1
                    if k < len(s) and s[k].isdigit():
                        while k < len(s) and s[k].isdigit():
                            k += 1
                        results.append((i, k, s[i:k]))
                        i = k
                        continue
                results.append((i, j, s[i:j]))
                i = j
                continue
            i += 1
        return results

    def _extract_quoted_literals_with_spans(self, text: str) -> List[Tuple[int, int, str]]:
        results = []
        if not text:
            return results
        pairs = [("「", "」"), ("『", "』"), ("“", "”"), ("\"", "\""), ("'", "'")]
        s = str(text)
        for open_q, close_q in pairs:
            start = 0
            while True:
                idx = s.find(open_q, start)
                if idx == -1:
                    break
                end = s.find(close_q, idx + len(open_q))
                if end == -1:
                    break
                literal = s[idx + len(open_q):end]
                results.append((idx, end + len(close_q), literal))
                start = end + len(close_q)
        return results

    def _is_number_literal(self, value: str) -> bool:
        if value is None:
            return False
        s = str(value).strip()
        if not s:
            return False
        if s.isdigit():
            return True
        try:
            float(s)
            return True
        except Exception:
            return False

    def _is_role_mismatch(self, actual_role: str, expected_role: str) -> bool:
        if actual_role == expected_role: return False
        role_groups = [["FETCH", "DATABASE_QUERY", "HTTP_REQUEST"], ["PERSIST", "FILE_IO", "EXPORT"]]
        for group in role_groups:
            if actual_role in group and expected_role in group: return False
        return True
