# -*- coding: utf-8 -*-
import os
import json
from typing import Dict, List, Any, Optional
from src.advanced_tdd.ast_analyzer import ASTAnalyzer
from src.utils.logic_auditor import LogicAuditor
from src.utils.design_doc_parser import DesignDocParser

class DesignDocRefiner:
    """実装（コード）から設計書（.design.md）を洗練・同期させるクラス"""

    def __init__(self, config_manager=None, vector_engine=None, morph_analyzer=None, knowledge_base=None):
        self.config_manager = config_manager
        self.ast_analyzer = ASTAnalyzer()
        self.ukb = knowledge_base
        self.auditor = LogicAuditor(
            config_manager=config_manager,
            morph_analyzer=morph_analyzer,
            vector_engine=vector_engine,
            knowledge_base=self.ukb
        )
        self.parser = DesignDocParser(knowledge_base=self.ukb)

    def _load_refiner_config(self) -> Dict[str, Any]:
        if self.ukb and hasattr(self.ukb, "get"):
            data = self.ukb.get("design_doc_refiner", {})
            if isinstance(data, dict):
                return data
        return {}

    def sync_from_code(self, design_path: str, source_path: str) -> Dict[str, Any]:
        """コードの構造を解析し、設計書の Input/Output/Core Logic を同期させる"""
        if not os.path.exists(design_path) or not os.path.exists(source_path):
            return {"status": "error", "message": "ファイルが見つかりません。"}

        try:
            # 1. 現状の解析
            with open(design_path, 'r', encoding='utf-8') as f:
                design_content = f.read()
            
            with open(source_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            source_structure = self.ast_analyzer.analyze_file(source_path)
            design_data = self.parser.parse_content(design_content)
            print(f"[DEBUG] design_data type: {type(design_data)}")

            # 2. 整合性チェック (監査)
            audit_result = self.auditor.audit(design_data, source_structure, source_code)
            
            # 3. 同期ロジック
            new_content = design_content
            
            # A. Input/Output の同期 (最初のクラス/関数を対象)
            new_content = self._sync_interface(new_content, source_structure)
            
            # B. Core Logic の TODO 補完
            new_content = self._refine_logic_placeholders(new_content, source_structure)

            # 4. 書き込み
            if new_content != design_content:
                with open(design_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                return {
                    "status": "success", 
                    "message": "設計書を実装と同期しました。",
                    "audit_score": audit_result.get("consistency_score"),
                    "findings": audit_result.get("findings")
                }
            
            return {"status": "no_change", "message": "設計書は既に実装と整合しています。"}

        except Exception as e:
            return {"status": "error", "message": f"同期中にエラーが発生しました: {e}"}

    def audit_only(self, design_content: str, source_path: str, source_code: Optional[str] = None) -> Dict[str, Any]:
        """設計書と実装の整合性を監査する（書き換えはしない）"""
        if not os.path.exists(source_path):
            return {"status": "error", "message": "ソースファイルが見つかりません。"}
        if not design_content or not isinstance(design_content, str):
            return {"status": "skipped", "message": "設計書内容が空です。"}
        try:
            if source_code is None:
                with open(source_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            design_data = self.parser.parse_content(design_content)
            core_logic = []
            if isinstance(design_data, dict):
                core_logic = design_data.get("specification", {}).get("core_logic", []) or []

            # Avoid keyword/regex-based coverage checks; use assertion-based audit only.
            normalized_steps = []
            for step in core_logic:
                text = str(step or "").strip()
                text = self._strip_leading_numbering(text)
                if text:
                    normalized_steps.append(text)
            goals = self.auditor.extract_assertion_goals(normalized_steps)
            if not goals:
                return {"status": "consistent", "consistency_score": 1.0, "findings": []}
            method_name = ""
            if isinstance(design_data, dict):
                module_name = str(design_data.get("module_name", "")).strip()
                if module_name:
                    method_name = module_name.split(".")[-1]
            code_for_audit = self._extract_method_body(source_code, method_name) if method_name else source_code
            findings = self.auditor.verify_logic_goals(goals, code_for_audit)
            normalized = [
                {"type": f.get("reason", "logic_gap"), "detail": f.get("detail", "")}
                for f in findings
            ]
            return {
                "status": "consistent" if not normalized else "inconsistent",
                "consistency_score": 1.0 if not normalized else 0.0,
                "findings": normalized
            }
        except Exception as e:
            return {"status": "error", "message": f"監査中にエラーが発生しました: {e}"}

    def _extract_method_body(self, source_code: str, method_name: str) -> str:
        if not source_code or not method_name:
            return source_code
        try:
            structure = self.ast_analyzer.analyze_code_structure(source_code, language="csharp")
            methods = structure.get("structure", {}).get("methods", []) if isinstance(structure, dict) else []
            method_line = None
            for m in methods:
                if isinstance(m, dict) and m.get("name") == method_name:
                    method_line = m.get("line")
                    break
            if not method_line:
                return source_code
            lines = source_code.splitlines()
            start_idx = max(0, int(method_line) - 1)
            brace_count = 0
            started = False
            end_idx = None
            for i in range(start_idx, len(lines)):
                line = lines[i]
                if not started:
                    if "{" in line:
                        started = True
                        brace_count += line.count("{") - line.count("}")
                        if brace_count == 0:
                            end_idx = i
                            break
                else:
                    brace_count += line.count("{") - line.count("}")
                    if brace_count == 0:
                        end_idx = i
                        break
            if end_idx is None:
                return "\n".join(lines[start_idx:])
            return "\n".join(lines[start_idx:end_idx + 1])
        except Exception:
            return source_code

    def _sync_interface(self, content: str, structure: Dict[str, Any]) -> str:
        """Input / Output セクションを実装のシグネチャに合わせる"""
        target = None
        if structure.get('classes'):
            for cls in structure['classes']:
                if cls.get('methods'):
                    target = cls['methods'][0]
                    break
        if not target and structure.get('functions'):
            target = structure['functions'][0]

        if not target:
            return content

        params = []
        if 'parameters' in target: # C#
            params = [p.strip() for p in target['parameters'].split(',') if p.strip()]
        elif 'args' in target: # Python
            params = [arg for arg in target['args'] if arg not in ['self', 'cls']]

        params_str = ", ".join([f"`{p.split()[-1] if ' ' in p else p}`" for p in params])
        ret_type = target.get('return_type') or target.get('returns') or 'void'

        cfg = self._load_refiner_config()
        input_header = cfg.get("input_header_pattern", r"(###?\s*Input\s*)")
        output_header = cfg.get("output_header_pattern", r"(###?\s*Output\s*)")
        desc_label = cfg.get("description_label", "Description")
        input_template = cfg.get("input_description_template", "{params} を入力として受け取ります。")
        output_template = cfg.get("output_description_template", "`{return_type}` 型の値を返します。")

        content = self._replace_section_description(content, "Input", desc_label, input_template.format(params=params_str))
        content = self._replace_section_description(content, "Output", desc_label, output_template.format(return_type=ret_type))

        return content

    def _refine_logic_placeholders(self, content: str, structure: Dict[str, Any]) -> str:
        """TODO や プレースホルダーを実際のメソッド呼び出し等から推論して埋める"""
        cfg = self._load_refiner_config()
        placeholder = cfg.get("logic_placeholder_pattern", "ロジックの詳細をここに記述してください。")
        if placeholder not in content:
            return content

        methods = []
        for cls in structure.get('classes', []):
            methods.extend([m['name'] if isinstance(m, dict) else str(m) for m in cls.get('methods', [])])
        
        max_methods = cfg.get("logic_placeholder_max_methods", 5)
        line_template = cfg.get("logic_placeholder_line_template", "{index}. `{method}` メソッドを呼び出し、必要な処理を実行します。")
        fallback_line = cfg.get("logic_placeholder_fallback", "1. モジュール内の定義済み関数を呼び出し、処理を実行します。")

        new_logic = ""
        if methods:
            for i, m in enumerate(methods[:max_methods], 1):
                new_logic += line_template.format(index=i, method=m) + "\n"
        else:
            new_logic = fallback_line + "\n"

        return content.replace(placeholder, new_logic)

    def _strip_leading_numbering(self, text: str) -> str:
        s = text.strip()
        i = 0
        while i < len(s) and (s[i].isdigit() or s[i] in [".", ")", " "]):
            i += 1
        return s[i:].strip()

    def _replace_section_description(self, content: str, section_name: str, label: str, new_desc: str) -> str:
        lines = content.splitlines()
        in_section = False
        for i, line in enumerate(lines):
            lower = line.lower().strip()
            if lower.startswith("###") or lower.startswith("##") or lower.startswith("#"):
                in_section = section_name.lower() in lower
                continue
            if in_section and lower.startswith(f"- **{label.lower()}**:"):
                prefix = line.split(":", 1)[0]
                lines[i] = f"{prefix}: {new_desc}"
                break
        return "\n".join(lines)
