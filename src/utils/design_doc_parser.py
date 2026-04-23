# -*- coding: utf-8 -*-
import os
from typing import Dict, List, Any, Optional

class DesignDocParser:
    """設計書(.design.md)を構造化データに変換するクラス"""

    def __init__(self, knowledge_base=None):
        self.ukb = knowledge_base

    def _load_parser_config(self) -> Dict[str, Any]:
        if self.ukb and hasattr(self.ukb, "get"):
            data = self.ukb.get("design_doc_parser", {})
            if isinstance(data, dict):
                return data
        return {}

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """ファイルを読み込んでパースする"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Design document not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.parse_content(content)

    def parse_content(self, content: str) -> Dict[str, Any]:
        """文字列としての設計書内容をパースする"""
        # セクションごとに分割
        sections = self._split_sections(content)
        
        cfg = self._load_parser_config()
        aliases = cfg.get("section_aliases", {}) if isinstance(cfg.get("section_aliases"), dict) else {}

        def _resolve_section(keys: List[str]) -> str:
            for k in keys:
                val = sections.get(k)
                if val:
                    return val
            return ""

        # 名前寄せ
        purpose = _resolve_section(aliases.get("purpose", ["Purpose", "1. Purpose"]))
        input_info = _resolve_section(aliases.get("input", ["Input", "### Input"]))
        output_info = _resolve_section(aliases.get("output", ["Output", "### Output"]))
        logic_info = _resolve_section(aliases.get("core_logic", ["Core Logic", "### Core Logic"]))
        test_info = _resolve_section(aliases.get("test_cases", ["Test Cases", "### Test Cases"]))

        result = {
            "module_name": self._extract_module_name(content),
            "purpose": purpose.strip(),
            "specification": {
                "input": self._parse_io_info(input_info),
                "output": self._parse_io_info(output_info),
                "core_logic": self._parse_list_items(logic_info)
            },
            "test_cases": self._parse_test_cases(test_info)
        }
        
        return result

    def _split_sections(self, content: str) -> Dict[str, str]:
        """Markdownの見出しに基づいて内容を辞書に分割 (重複見出しの統合をサポート)"""
        sections = {}
        lines = content.splitlines()
        
        current_header = None
        current_content = []
        
        def save_current():
            if current_header:
                val = "\n".join(current_content).strip()
                # 簡略化名 (e.g. "1. Purpose" -> "Purpose")
                simple_name = self._strip_leading_numbering(current_header)
                
                # 完全な見出し名
                if current_header in sections:
                    sections[current_header] += "\n\n" + val
                else:
                    sections[current_header] = val
                
                # 簡略化名 (重複時は統合)
                if simple_name != current_header:
                    if simple_name in sections:
                        sections[simple_name] += "\n\n" + val
                    else:
                        sections[simple_name] = val

        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("#"):
                i = 0
                while i < len(stripped) and stripped[i] == "#":
                    i += 1
                if 1 <= i <= 4 and i < len(stripped) and stripped[i] == " ":
                    save_current()
                    current_header = stripped[i+1:].strip()
                    current_content = []
                    continue
            if current_header is not None:
                current_content.append(line)
        
        save_current()
        return sections

    def _extract_module_name(self, content: str) -> str:
        """H1ヘッダーからモジュール名を取得 (より柔軟なパース)"""
        # 行頭の # から始まる最初の行をモジュール名とする
        for line in content.splitlines():
            if line.startswith("# "):
                name = line[2:].strip()
                if name.endswith("Design Document"):
                    name = name[:-len("Design Document")].strip()
                return name
        # 予備のパターン: 行頭に関わらず最初の # を探す
        for line in content.splitlines():
            if "#" in line:
                idx = line.find("#")
                name = line[idx+1:].strip()
                return name if name else "UnknownModule"
        return "UnknownModule"

    def _parse_io_info(self, content: str) -> Any:
        """Input/Outputセクションの箇条書きから情報を抽出"""
        if not content:
            return {"description": "", "format": "", "example": ""}
        cfg = self._load_parser_config()
        io_labels = cfg.get("io_labels", {}) if isinstance(cfg.get("io_labels"), dict) else {}
        desc_labels = io_labels.get("description", ["Description"])
        fmt_labels = io_labels.get("type_format", ["Type/Format"])
        example_labels = io_labels.get("example", ["Example"])

        # Multi-entry format: - `name`: `type`
        multi_matches = []
        for line in content.splitlines():
            line = line.strip()
            if not line.startswith("-"):
                continue
            if "`" in line and ":" in line:
                parts = line.split("`")
                if len(parts) >= 4:
                    name = parts[1].strip()
                    fmt = parts[3].strip()
                    if name and fmt:
                        multi_matches.append((name, fmt))
        if len(multi_matches) >= 2:
            items = []
            for name, fmt in multi_matches:
                items.append({
                    "name": name,
                    "description": f"Variable {name}",
                    "format": fmt.strip(),
                    "example": ""
                })
            return items
            
        # Description / Format / Example (simple line scan)
        desc_val = ""
        fmt_val = ""
        example = ""
        in_code = False
        for line in content.splitlines():
            l = line.strip()
            if l.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                example += (l + "\n")
                continue
            lower = l.lower()
            for label in desc_labels:
                if lower.startswith(f"- **{label.lower()}**:") or lower.startswith(f"{label.lower()}:"):
                    desc_val = l.split(":", 1)[1].strip() if ":" in l else desc_val
            for label in fmt_labels:
                if lower.startswith(f"- **{label.lower()}**:") or lower.startswith(f"{label.lower()}:"):
                    fmt_val = l.split(":", 1)[1].strip() if ":" in l else fmt_val
            for label in example_labels:
                if lower.startswith(f"- **{label.lower()}**:") or lower.startswith(f"{label.lower()}:"):
                    example = l.split(":", 1)[1].strip() if ":" in l else example

        # Support for simple `- `name`: `type`` format
        if not desc_val:
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("-") and "`" in line and ":" in line:
                    parts = line.split("`")
                    if len(parts) >= 4:
                        name = parts[1].strip()
                        fmt = parts[3].strip()
                        if name and fmt:
                            return {
                                "name": name,
                                "description": f"Variable {name}",
                                "format": fmt,
                                "example": ""
                            }

        return {
            "description": desc_val.strip() if desc_val else "",
            "format": fmt_val.strip() if fmt_val else "",
            "example": example.strip()
        }

    def _parse_list_items(self, content: str) -> List[str]:
        """Core Logicなどのリスト項目を抽出 (階層や複数のリストを考慮)"""
        if not content: return []
        
        items = []
        # 行ごとに見て、リストマーカー(1. or -)で始まるものを全て抽出
        for line in content.splitlines():
            stripped = line.lstrip()
            if not stripped:
                continue
            if stripped[0] in ["-", "*"] and len(stripped) > 1 and stripped[1].isspace():
                item_text = stripped[2:].strip()
                if item_text:
                    items.append(item_text)
                continue
            # Numbered list
            i = 0
            while i < len(stripped) and stripped[i].isdigit():
                i += 1
            if i > 0 and i < len(stripped) and stripped[i] == ".":
                if i + 1 < len(stripped) and stripped[i+1].isspace():
                    marker = stripped[:i+1]
                    item_text = stripped[i+2:].strip()
                    items.append(f"{marker} {item_text}")
        
        # もしリストが見つからなかったがテキストがある場合は、段落ごとに分割して返す
        if not items and content.strip():
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            return paragraphs
            
        return items

    def _parse_test_cases(self, content: str) -> List[Dict[str, Any]]:
        """Test Casesセクションを構造化"""
        if not content: return []
        
        cases = []
        cfg = self._load_parser_config()
        type_map = cfg.get("test_case_types", {"happy_path": ["Happy Path"], "edge_case": ["Edge Case"]})
        labels_cfg = cfg.get("test_case_labels", {})
        scenario_labels = labels_cfg.get("scenario", ["Scenario"])
        input_labels = labels_cfg.get("input", ["Input"])
        expected_labels = labels_cfg.get("expected", ["Expected"])
        reserved_titles = set(t.lower() for t in labels_cfg.get("reserved_titles", ["input", "expected", "scenario"]))
        current_type = "general"
        lines = content.splitlines()
        current_case = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Type header detection (non-list lines only)
            if not line.startswith(("-", "*")):
                for t_key, t_labels in type_map.items():
                    for lbl in t_labels:
                        if lbl in line:
                            current_type = t_key
                            break
                if current_type != "general":
                    continue

            # Inline parsing for Input/Expected under current case
            if current_case:
                for lbl in input_labels:
                    token = f"**{lbl}**:"
                    if token in line:
                        val = line.split(token, 1)[1].strip()
                        current_case["input"] = val
                        break
                for lbl in expected_labels:
                    token = f"**{lbl}**:"
                    if token in line:
                        val = line.split(token, 1)[1].strip()
                        current_case["expected"] = val
                        break

            # Scenario start
            for lbl in scenario_labels:
                token = f"**{lbl}**:"
                if token in line:
                    if current_case:
                        cases.append(current_case)
                    scenario = line.split(token, 1)[1].strip()
                    current_case = {"type": current_type, "scenario": scenario, "input": "", "expected": ""}
                    break
            else:
                # Simple bullet: - **Title**: value
                if line.startswith(("-", "*")) and "**" in line and ":" in line:
                    parts = line.split("**")
                    if len(parts) >= 3:
                        title = parts[1].strip()
                        if title.lower() in reserved_titles:
                            continue
                        rest = line.split("**:", 1)
                        value = rest[1].strip() if len(rest) > 1 else ""
                        if current_case:
                            cases.append(current_case)
                        current_case = {"type": current_type, "scenario": title, "input": "", "expected": value}
        
        if current_case: cases.append(current_case)
        return cases

    def _strip_leading_numbering(self, header: str) -> str:
        s = header.strip()
        i = 0
        while i < len(s) and (s[i].isdigit() or s[i] in [".", " "]):
            i += 1
        return s[i:].strip()

if __name__ == "__main__":
    parser = DesignDocParser()
    sample = "# Test Design Document\n## 1. Purpose\nCheck\n## 2. Structured Specification\n### Input\n- **Description**: Data\n### Core Logic\n1. Step A\n### Test Cases\n- **Case 1**: Result"
    import json
    print(json.dumps(parser.parse_content(sample), indent=2, ensure_ascii=False))
