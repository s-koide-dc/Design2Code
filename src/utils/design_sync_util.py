# -*- coding: utf-8 -*-
import os
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

class DesignSyncUtil:
    """コードと設計書の双方向同期を支援するユーティリティ"""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)

    def _load_sync_config(self) -> Dict[str, Any]:
        config_path = self.workspace_root / "resources" / "canonical_knowledge.json"
        if not config_path.exists():
            return {}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cfg = data.get("design_sync_util", {})
            return cfg if isinstance(cfg, dict) else {}
        except Exception:
            return {}

    def sync_code_to_design(self, design_path: str, code_structure: Dict[str, Any]) -> bool:
        """
        コードの構造（AST解析結果）を設計書のメタデータセクションに書き戻す。
        現在は Interface (Input/Output) の同期にフォーカス。
        """
        try:
            design_file = Path(design_path)
            if not design_file.exists():
                return False

            with open(design_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Input/Output のメタデータ部分を特定し更新を試みる
            # (設計書が JSON ブロックまたは特定のマーカーを持っている前提)
            new_content = self._update_interface_metadata(content, code_structure)
            
            if new_content != content:
                with open(design_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                return True
            return False

        except Exception as e:
            print(f"Sync error: {e}")
            return False

    def _update_interface_metadata(self, content: str, structure: Dict[str, Any]) -> str:
        """設計書内の Interface 定義をコードの実態に合わせて更新"""
        methods = []
        for cls in structure.get("classes", []):
            methods.extend(cls.get("methods", []))
        methods.extend(structure.get("functions", []))

        if not methods:
            return content

        target = methods[0]
        params = []
        if "args" in target:
            params = [f"`{p}`" for p in target["args"] if p not in ['self', 'cls']]
        elif "parameters" in target:
             # C# parameter string
             p_str = target["parameters"]
             params = [f"`{p.strip().split()[-1]}`" for p in p_str.split(',') if p.strip()]

        param_str = ", ".join(params)

        cfg = self._load_sync_config()
        input_metadata_template = cfg.get("input_metadata_template", "Arguments: {params} (Synced from code)")
        template_text = input_metadata_template.format(params=param_str)
        return self._replace_input_description(content, template_text)

    def update_logic_step(self, design_path: str, step_idx: int, new_step_content: str) -> bool:
        """特定のロジックステップを更新"""
        try:
            design_file = Path(design_path)
            if not design_file.exists(): return False

            with open(design_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            cfg = self._load_sync_config()
            core_logic_markers = cfg.get("core_logic_markers", ["core_logic:", "core logic"])
            section_end_pattern = cfg.get("section_end_pattern")
            append_suffix = cfg.get("update_suffix", " (Synced from code)")

            # "Core Logic:" セクションを探す
            in_logic = False
            current_step = 0
            for i, line in enumerate(lines):
                if any(marker in line.lower() for marker in core_logic_markers):
                    in_logic = True
                    continue
                
                if in_logic:
                    # ステップ（箇条書き）を探す
                    if self._is_list_item(line):
                        current_step += 1
                        if current_step == step_idx:
                            # インデントを保持しつつ置換
                            indent = self._list_indent(line)
                            lines[i] = f"{indent}{new_step_content}{append_suffix}\n"
                            break
                    elif line.strip() == "" or (line.strip().endswith(':') and 'logic' not in line.lower()) or (section_end_pattern and section_end_pattern in line):
                        # セクション終了
                        if current_step > 0: break

            with open(design_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            return True

        except Exception as e:
            print(f"Logic update error: {e}")
            return False

    def collect_user_feedback(self, finding_id: str, feedback: str):
        """ユーザーからの修正フィードバックを記録"""
        feedback_file = self.workspace_root / 'logs' / 'user_feedback.jsonl'
        feedback_file.parent.mkdir(parents=True, exist_ok=True)
        
        record = {
            "timestamp": "now", # 本来は datetime
            "finding_id": finding_id,
            "feedback": feedback,
            "status": "pending_analysis"
        }
        
        with open(feedback_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _replace_input_description(self, content: str, new_desc: str) -> str:
        lines = content.splitlines()
        in_input = False
        for i, line in enumerate(lines):
            lower = line.lower().strip()
            if lower.startswith("input") or lower.startswith("### input") or lower.startswith("## input"):
                in_input = True
                continue
            if in_input:
                if lower.startswith("##") and "input" not in lower:
                    break
                if "- description:" in lower:
                    prefix = line.split(":", 1)[0]
                    lines[i] = f"{prefix}: {new_desc}"
                    break
        return "\n".join(lines)

    def _is_list_item(self, line: str) -> bool:
        stripped = line.lstrip()
        if not stripped:
            return False
        if stripped.startswith("- ") or stripped.startswith("* "):
            return True
        i = 0
        while i < len(stripped) and stripped[i].isdigit():
            i += 1
        return i > 0 and i < len(stripped) and stripped[i] == "."

    def _list_indent(self, line: str) -> str:
        indent = ""
        i = 0
        while i < len(line) and line[i].isspace():
            indent += line[i]
            i += 1
        if i < len(line) and line[i] in ["-", "*"]:
            return indent + line[i] + " "
        if i < len(line) and line[i].isdigit():
            while i < len(line) and line[i].isdigit():
                indent += line[i]
                i += 1
            if i < len(line) and line[i] == ".":
                indent += ". "
            return indent
        return indent
