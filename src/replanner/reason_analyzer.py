# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
from src.utils.logic_auditor import LogicAuditor

class ReasonAnalyzer:
    """分析失敗理由を特定し、再計画のヒントを生成するクラス"""

    def __init__(self, logic_auditor: Optional[LogicAuditor] = None):
        self.logic_auditor = logic_auditor or LogicAuditor(knowledge_base=None)

    def analyze(self, synthesis_result: Dict[str, Any], verification_result: Dict[str, Any], semantic_issues: List[str]) -> List[Dict[str, Any]]:
        hints = []
        code = synthesis_result.get("code", "")

        # 1. コンパイルエラーの分析
        if not verification_result.get("valid", True):
            errors = verification_result.get("errors", [])
            for err in errors:
                hint = self._analyze_compilation_error(err, code)
                if hint: hints.append(hint)

        # 2. セマンティック（契約）違反の分析
        for issue in semantic_issues:
            hint = self._analyze_semantic_issue(issue, synthesis_result)
            if hint: hints.append(hint)

        return hints

    def _analyze_compilation_error(self, error: Dict[str, Any], full_code: str) -> Optional[Dict[str, Any]]:
        err_code = error.get("code", "")
        msg = error.get("message", "")
        line_num = error.get("line", 0)

        # MSBuild エラーメッセージからシングルクォートで囲まれたシンボルを抽出
        symbol = self._extract_single_quoted_value(msg)

        # エラー発生行の直近上部にある Node ID コメントを探索
        target_node_id = None
        if full_code and line_num > 0:
            lines = full_code.split('\n')
            for i in range(min(line_num - 1, len(lines) - 1), -1, -1):
                node_id = self._parse_node_comment(lines[i])
                if node_id:
                    target_node_id = node_id
                    break

        patch = {}
        if err_code == "CS0103":
            patch = {"type": "ENSURE_FIELD_OR_LOCAL", "name": symbol}
        elif err_code == "CS1061":
            entity_name, member_name = self._extract_missing_member_details(msg)
            member_type = error.get("member_type") or error.get("property_type")
            if not all(
                isinstance(value, str) and value.strip()
                for value in (entity_name, member_name, member_type)
            ):
                return None
            patch = {
                "type": "ADD_POCO_PROPERTY",
                "entity": entity_name,
                "member": member_name,
                "member_type": member_type,
            }
        elif err_code == "CS0120":
            patch = {"type": "INSTANCE_REQUIRED", "name": symbol}
        else:
            patch = {"type": "FIX_LOGIC_GAPS", "failed_texts": [target_node_id] if target_node_id else []}

        if target_node_id:
            patch["target_node_id"] = target_node_id

        reason = f"COMPILATION_ERROR_{err_code}"
        if err_code == "CS0103":
            reason = "MISSING_DECLARATION"
        return {
            "reason": reason,
            "detail": f"{msg} (at Node: {target_node_id or 'unknown'})",
            "patch": patch
        }

    def _analyze_semantic_issue(self, issue: str, synthesis_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if isinstance(issue, dict):
            issue_type = issue.get("type")
        else:
            issue_type = issue

        if issue == "GENERATED_CODE_CONTAINS_TODOS":
            trace = synthesis_result.get("trace", {})
            blueprint = trace.get("blueprint", {})
            failed_node_ids = []

            def _find_todos(body):
                for s in body:
                    if s.get("type") == "comment" and "TODO: Step failed" in s.get("text", ""):
                        failed_node_id = self._parse_step_failed_comment(s["text"])
                        if failed_node_id:
                            failed_node_ids.append(failed_node_id)
                    if "body" in s: _find_todos(s["body"])
                    if "else_body" in s: _find_todos(s["else_body"])

            for m in blueprint.get("methods", []):
                _find_todos(m.get("body", []))

            return {
                "reason": "LOGIC_GAP_DETECTED",
                "detail": f"Generated code contains TODOs for: {', '.join(failed_node_ids[:3])}",
                "patch": {"type": "FIX_LOGIC_GAPS", "failed_texts": failed_node_ids}
            }

        if isinstance(issue_type, str) and issue_type.startswith("SPEC_STEP_NOT_EMITTED"):
            parts = issue_type.split("|")
            step_id = parts[1] if len(parts) > 1 else None
            return {
                "reason": "SPEC_STEP_NOT_EMITTED",
                "detail": issue_type,
                "patch": {"type": "FIX_LOGIC_GAPS", "failed_texts": [step_id] if step_id else []}
            }

        if isinstance(issue_type, str) and issue_type.startswith("SPEC_SIDE_EFFECT_MISSING"):
            parts = issue_type.split("|")
            step_id = parts[1] if len(parts) > 1 else None
            return {
                "reason": "SPEC_SIDE_EFFECT_MISSING",
                "detail": issue_type,
                "patch": {"type": "FIX_LOGIC_GAPS", "failed_texts": [step_id] if step_id else []}
            }

        if isinstance(issue_type, str) and issue_type.startswith("SPEC_OUTPUT_TYPE_MISMATCH"):
            parts = issue_type.split("|")
            step_id = parts[1] if len(parts) > 1 else None
            return {
                "reason": "SPEC_OUTPUT_TYPE_MISMATCH",
                "detail": issue_type,
                "patch": {"type": "FIX_LOGIC_GAPS", "failed_texts": [step_id] if step_id else []}
            }

        if isinstance(issue_type, str) and issue_type.startswith("SPEC_INTENT_NOT_EMITTED"):
            parts = issue_type.split("|")
            step_id = parts[1] if len(parts) > 1 else None
            intent = parts[2] if len(parts) > 2 else None
            patch = {"type": "FIX_LOGIC_GAPS"}
            if step_id:
                patch["failed_texts"] = [step_id]
            if intent:
                patch["intent"] = intent
            return {
                "reason": "SPEC_INTENT_NOT_EMITTED",
                "detail": issue_type,
                "patch": patch
            }

        if isinstance(issue_type, str) and issue_type.startswith("SPEC_INPUT_LINK_UNUSED"):
            parts = issue_type.split("|")
            step_id = parts[1] if len(parts) > 1 else None
            input_link = parts[2] if len(parts) > 2 else None
            intent = parts[3] if len(parts) > 3 else None
            target = parts[4] if len(parts) > 4 else None
            vars_detail = parts[5] if len(parts) > 5 else None
            recommend = parts[6] if len(parts) > 6 else None
            drop_hint = parts[7] if len(parts) > 7 else None
            patch = {"type": "FIX_LOGIC_GAPS"}
            if step_id:
                patch["failed_texts"] = [step_id]
            if input_link:
                patch["input_link"] = input_link
            if intent:
                patch["intent"] = intent
            if target:
                patch["target_entity"] = target
            if vars_detail:
                patch["upstream_vars"] = vars_detail.split(",") if isinstance(vars_detail, str) else vars_detail
            if recommend and isinstance(recommend, str) and recommend.startswith("RECOMMEND=use:"):
                patch["recommend_var"] = recommend.split(":", 1)[1]
            if drop_hint and isinstance(drop_hint, str) and drop_hint.startswith("DROP_AT="):
                patch["drop_at"] = drop_hint.split("=", 1)[1]
            return {
                "reason": "SPEC_INPUT_LINK_UNUSED",
                "detail": issue_type,
                "patch": patch
            }

        if isinstance(issue_type, str) and issue_type.startswith("SPEC_INPUT_REF_UNUSED"):
            parts = issue_type.split("|")
            step_id = parts[1] if len(parts) > 1 else None
            input_ref = parts[2] if len(parts) > 2 else None
            vars_detail = parts[3] if len(parts) > 3 else None
            recommend = parts[4] if len(parts) > 4 else None
            drop_hint = parts[5] if len(parts) > 5 else None
            patch = {"type": "FIX_LOGIC_GAPS"}
            if step_id:
                patch["failed_texts"] = [step_id]
            if input_ref:
                patch["input_ref"] = input_ref
            if vars_detail:
                patch["upstream_vars"] = vars_detail.split(",") if isinstance(vars_detail, str) else vars_detail
            if recommend and isinstance(recommend, str) and recommend.startswith("RECOMMEND=use:"):
                patch["recommend_var"] = recommend.split(":", 1)[1]
            if drop_hint and isinstance(drop_hint, str) and drop_hint.startswith("DROP_AT="):
                patch["drop_at"] = drop_hint.split("=", 1)[1]
            return {
                "reason": "SPEC_INPUT_REF_UNUSED",
                "detail": issue_type,
                "patch": patch
            }

        # Legacy semantic issues
        missing_call = self._parse_required_call_missing(issue)
        if missing_call:
            method = missing_call.get("method")
            target_id = missing_call.get("target_id")
            return {
                "reason": "SEMANTIC_CALL_MISSING",
                "detail": issue,
                "patch": {"type": "FORCE_INTENT_RESOLUTION", "method": method, "target_id": target_id}
            }

        disconnected = self._parse_data_flow_disconnection(issue)
        if disconnected:
            source_id = disconnected.get("source_id")
            target_id = disconnected.get("target_id")
            return {
                "reason": "DATA_FLOW_DISCONNECTION",
                "detail": issue,
                "patch": {"type": "REBIND_INPUT_LINK", "source_id": source_id, "target_id": target_id}
            }

        return None

    @staticmethod
    def _extract_single_quoted_value(text: str) -> str:
        value = str(text)
        start = value.find("'")
        if start == -1:
            return ""
        end = value.find("'", start + 1)
        if end == -1:
            return ""
        return value[start + 1:end]

    @staticmethod
    def _extract_missing_member_details(message: str) -> tuple[str, str]:
        """Read the type and member from the fixed CS1061 diagnostic shape."""
        values = []
        remaining = str(message)
        while len(values) < 2:
            start = remaining.find("'")
            if start == -1:
                break
            end = remaining.find("'", start + 1)
            if end == -1:
                break
            values.append(remaining[start + 1:end])
            remaining = remaining[end + 1:]
        if len(values) != 2:
            return "", ""
        return values[0], values[1]

    @staticmethod
    def _is_identifier_token(value: str) -> bool:
        if not value:
            return False
        for ch in value:
            if not (ch.isalnum() or ch == "_"):
                return False
        return True

    @classmethod
    def _parse_node_comment(cls, line: str) -> str:
        marker = "// Node:"
        text = str(line).strip()
        if not text.startswith(marker):
            return ""
        node_id = text[len(marker):].strip()
        return node_id if cls._is_identifier_token(node_id) else ""

    @classmethod
    def _parse_step_failed_comment(cls, text: str) -> str:
        marker = "TODO: Step failed - "
        value = str(text)
        index = value.find(marker)
        if index == -1:
            return ""
        node_id = value[index + len(marker):].strip()
        return node_id if cls._is_identifier_token(node_id) else ""

    @classmethod
    def _parse_required_call_missing(cls, issue: str) -> Optional[Dict[str, str]]:
        prefix = "required call is missing: "
        text = str(issue)
        if not text.startswith(prefix):
            return None
        remainder = text[len(prefix):].strip()
        if not remainder:
            return None
        method = remainder
        target_id = None
        bracket_start = remainder.find(" [")
        if bracket_start != -1 and remainder.endswith("]"):
            method = remainder[:bracket_start].strip()
            target_id = remainder[bracket_start + 2:-1].strip()
        if not cls._is_identifier_token(method):
            return None
        if target_id is not None and not cls._is_identifier_token(target_id):
            return None
        return {"method": method, "target_id": target_id}

    @classmethod
    def _parse_data_flow_disconnection(cls, issue: str) -> Optional[Dict[str, str]]:
        prefix = "node '"
        separator = "' is not consumed by node '"
        suffix = "'"
        text = str(issue)
        if not text.startswith(prefix) or not text.endswith(suffix):
            return None
        body = text[len(prefix):-len(suffix)]
        sep_index = body.find(separator)
        if sep_index == -1:
            return None
        source_id = body[:sep_index]
        target_id = body[sep_index + len(separator):]
        if not cls._is_identifier_token(source_id) or not cls._is_identifier_token(target_id):
            return None
        return {"source_id": source_id, "target_id": target_id}

    def analyze_logic_mismatch(self, ir_tree: Dict[str, Any], synthesis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        合成結果のコードと IR ツリーを比較し、不適切なリテラルバインド（妄想的リテラル）や
        論理的な制約（数値、比較演算子など）の不一致を検出する。
        """
        hints = []
        code = synthesis_result.get("code", "")
        if not code: return hints

        trace = synthesis_result.get("trace", {})
        blueprint = trace.get("blueprint", {})

        flat_nodes = []
        def _flatten(nodes):
            for n in nodes:
                flat_nodes.append(n)
                if n.get("children"): _flatten(n["children"])
                if n.get("else_children"): _flatten(n["else_children"])
        _flatten(ir_tree.get("logic_tree", []))

        # 1. 妄想的リテラル（デバッグ表示などへの誤バインド）の検出
        def _check_delusional_literals(body):
            for s in body:
                if s.get("type") == "call" and s.get("method", "").endswith("WriteLine"):
                    args = s.get("args", [])
                    if args:
                        arg_val = str(args[0]).strip('"')
                        target_node = None
                        s_node_id = s.get("node_id")
                        if s_node_id:
                            target_node = next((n for n in flat_nodes if n["id"] == s_node_id), None)

                        if target_node:
                            if target_node.get("target_entity") == "Item" or target_node.get("output_type") == "string":
                                continue
                            s_map = target_node.get("semantic_map", {})
                            semantic_roles = s_map.get("semantic_roles", {})
                            if "content" in semantic_roles:
                                continue

                            hints.append({
                                "reason": "DELUSIONAL_LITERAL_DETECTED",
                                "detail": f"Step '{target_node['id']}' bound to descriptive text instead of data: {arg_val}",
                                "patch": {"type": "FORCE_VARIABLE_BINDING", "node_id": target_node["id"]}
                            })
                if "body" in s: _check_delusional_literals(s["body"])
                if "else_body" in s: _check_delusional_literals(s["else_body"])

        for m in blueprint.get("methods", []):
            _check_delusional_literals(m.get("body", []))

        # 2. Logic Goals (数値、演算子、文字列制約) の検証
        for node in flat_nodes:
            s_map = node.get("semantic_map", {})
            goals = s_map.get("logic", [])
            if not goals: continue

            node_findings = self.logic_auditor.verify_logic_goals(goals, code)
            for f in node_findings:
                hints.append({
                    "reason": f["reason"],
                    "detail": f"{f['detail']} (at Node '{node['id']}')",
                    "patch": {"type": "FIX_LOGIC_GAPS", "failed_texts": [node["id"]]}
                })

        return hints
