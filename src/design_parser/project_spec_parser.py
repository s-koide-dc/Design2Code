# -*- coding: utf-8 -*-
import json
from typing import Dict, List, Any, Optional


class ProjectSpecParser:
    """Parse project-level design specs for multi-file generation."""

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.parse_content(content)

    def parse_content(self, content: str) -> Dict[str, Any]:
        sections = self._split_sections(content)
        project_name = self._extract_project_name(content)
        project_spec = self._find_section(sections, ["Project Spec", "1. Project Spec"])
        if project_spec:
            sub = self._split_subsections(project_spec)
        else:
            # Fallback: treat top-level sections as project spec parts
            sub = sections
        tech = self._parse_kv_block(self._find_section(sub, ["Tech"]))
        architecture = self._parse_kv_block(self._find_section(sub, ["Architecture"]))
        data_access = self._parse_kv_block(self._find_section(sub, ["Data Access"]))
        modules = self._parse_modules_block(self._find_section(sub, ["Modules"]))
        entities, dtos = self._parse_entities_block(self._find_section(sub, ["Entities / DTO", "Entities/DTO"]))
        infra = self._parse_kv_block(self._find_section(sub, ["Infrastructure"]))
        validation = self._parse_validation_block(self._find_section(sub, ["Validation"]))
        method_specs = self._parse_method_specs(sections, sections.get("Method Specs", ""))
        generation_hints = self._parse_generation_hints(sections, self._find_section(sections, ["Generation Hints (Reusable)", "Generation Hints"]))

        return {
            "project_name": project_name,
            "spec": {
                "tech": tech,
                "architecture": architecture,
                "data_access": data_access,
                "modules": modules,
                "entities": entities,
                "dtos": dtos,
                "infrastructure": infra,
                "validation": validation,
                "method_specs": method_specs,
                "generation_hints": generation_hints,
            },
            "raw_sections": sections,
        }

    def _extract_project_name(self, content: str) -> str:
        for line in content.splitlines():
            if line.strip().startswith("# "):
                return line.strip()[2:].strip()
        return "UnknownProject"

    def _split_sections(self, content: str) -> Dict[str, str]:
        sections: Dict[str, str] = {}
        current_header: Optional[str] = None
        current_content: List[str] = []

        def save_current():
            if current_header is None:
                return
            value = "\n".join(current_content).strip()
            if current_header in sections:
                sections[current_header] += "\n\n" + value
            else:
                sections[current_header] = value
            simple = self._normalize_header(current_header)
            if simple != current_header:
                if simple in sections:
                    sections[simple] += "\n\n" + value
                else:
                    sections[simple] = value

        for line in content.splitlines():
            line_strip = line.strip()
            if line_strip.startswith("#"):
                # header line
                header_text = line_strip.lstrip("#").strip()
                if header_text:
                    save_current()
                    current_header = header_text
                    current_content = []
                    continue
            if current_header is not None:
                current_content.append(line)
        save_current()
        return sections

    def _split_subsections(self, content: str) -> Dict[str, str]:
        sections: Dict[str, str] = {}
        current_header: Optional[str] = None
        current_content: List[str] = []

        def save_current():
            if current_header is None:
                return
            value = "\n".join(current_content).strip()
            if current_header in sections:
                sections[current_header] += "\n\n" + value
            else:
                sections[current_header] = value
            simple = self._normalize_header(current_header)
            if simple != current_header:
                if simple in sections:
                    sections[simple] += "\n\n" + value
                else:
                    sections[simple] = value

        for line in content.splitlines():
            line_strip = line.strip()
            if line_strip.startswith("### ") or line_strip.startswith("#### "):
                header_text = line_strip.lstrip("#").strip()
                if header_text:
                    save_current()
                    current_header = header_text
                    current_content = []
                    continue
            if current_header is not None:
                current_content.append(line)
        save_current()
        return sections

    def _normalize_header(self, header: str) -> str:
        # Remove numeric prefix like "1. " or "1.2. "
        h = header.strip()
        while h and h[0].isdigit():
            i = 0
            while i < len(h) and (h[i].isdigit() or h[i] in [".", " "]):
                i += 1
            h = h[i:].strip()
        return h

    def _find_section(self, sections: Dict[str, str], keys: List[str]) -> str:
        for k in keys:
            if k in sections and sections[k]:
                return sections[k]
            simple = self._normalize_header(k)
            if simple in sections and sections[simple]:
                return sections[simple]
        return ""

    def _parse_kv_block(self, content: str) -> Dict[str, str]:
        result: Dict[str, str] = {}
        if not content:
            return result
        for line in content.splitlines():
            text = line.strip()
            if not text.startswith("- **"):
                continue
            # Expect: - **Key**: Value
            start = text.find("**")
            mid = text.find("**:", start + 2)
            if start == -1 or mid == -1:
                continue
            key = text[start + 2:mid].strip()
            value = text[mid + 3:].strip()
            if key:
                result[key] = value
        return result

    def _parse_modules_block(self, content: str) -> List[Dict[str, Any]]:
        modules: List[Dict[str, Any]] = []
        if not content:
            return modules
        current: Optional[Dict[str, Any]] = None
        current_list: Optional[str] = None
        for line in content.splitlines():
            text = line.strip()
            if not text:
                continue
            if text.startswith("- **") and "**:" in text:
                start = text.find("**")
                mid = text.find("**:", start + 2)
                role = text[start + 2:mid].strip()
                name = text[mid + 3:].strip()
                current = {"type": role, "name": name}
                modules.append(current)
                current_list = None
                continue
            if text.startswith("- ") and text.endswith(":") and current:
                current_list = text[2:-1].strip().lower()
                current.setdefault(current_list, [])
                continue
            if text.startswith("- ") and current and current_list:
                item = text[2:].strip()
                current.setdefault(current_list, []).append(item)
        return modules

    def _parse_entities_block(self, content: str) -> (List[Dict[str, Any]], List[Dict[str, Any]]):
        entities: List[Dict[str, Any]] = []
        dtos: List[Dict[str, Any]] = []
        if not content:
            return entities, dtos

        current_type = None
        current: Optional[Dict[str, Any]] = None
        for line in content.splitlines():
            text = line.strip()
            if not text:
                continue
            if text.startswith("- **") and "**:" in text:
                start = text.find("**")
                mid = text.find("**:", start + 2)
                label = text[start + 2:mid].strip()
                name = text[mid + 3:].strip()
                if label.lower() == "entity":
                    current_type = "entity"
                    current = {"name": name, "properties": []}
                    entities.append(current)
                elif label.lower() == "dto":
                    current_type = "dto"
                    current = {"name": name, "properties": []}
                    dtos.append(current)
                else:
                    current_type = None
                    current = None
                continue
            if text.startswith("- ") and current:
                item = text[2:].strip()
                if item:
                    current.setdefault("properties", []).append(item)
        return entities, dtos

    def _parse_method_specs(self, sections: Dict[str, str], content: str) -> Dict[str, Dict[str, Any]]:
        specs: Dict[str, Dict[str, Any]] = {}
        if content:
            specs.update(self._parse_method_specs_from_block(content))
        if sections:
            for key, value in sections.items():
                if "." in key and value:
                    specs.update(self._parse_method_specs_from_block(f"### {key}\n{value}"))
        return specs

    def _parse_method_specs_from_block(self, content: str) -> Dict[str, Dict[str, Any]]:
        specs: Dict[str, Dict[str, Any]] = {}
        current_name: Optional[str] = None
        current: Optional[Dict[str, Any]] = None
        section: Optional[str] = None

        for line in content.splitlines():
            text = line.strip()
            if not text:
                continue
            if text.startswith("### "):
                current_name = text[4:].strip()
                if current_name:
                    current = {
                        "input": "",
                        "output": "",
                        "core_logic": [],
                        "test_cases": [],
                        "steps": [],
                    }
                    specs[current_name] = current
                section = None
                continue
            if current is None:
                continue
            if text.startswith("- **Input**"):
                section = "input"
                parts = text.split(":", 1)
                if len(parts) > 1:
                    current["input"] = parts[1].strip()
                continue
            if text.startswith("- **Output**"):
                section = "output"
                parts = text.split(":", 1)
                if len(parts) > 1:
                    current["output"] = parts[1].strip()
                continue
            if text.startswith("- **Core Logic**"):
                section = "core_logic"
                continue
            if text.startswith("- **Steps**"):
                section = "steps"
                continue
            if text.startswith("- **Test Cases**"):
                section = "test_cases"
                continue
            if section == "steps":
                if text.startswith("- op:"):
                    current.setdefault("steps", []).append(text[5:].strip())
                continue
            if section == "core_logic":
                if text.startswith("- "):
                    current.setdefault("core_logic", []).append(text[2:].strip())
                    continue
                if text[0].isdigit() and "." in text:
                    current.setdefault("core_logic", []).append(text)
                continue
            if section == "test_cases":
                if text.startswith("- "):
                    raw = text[2:].strip()
                    if raw.startswith("{") and raw.endswith("}"):
                        try:
                            current.setdefault("test_cases", []).append(json.loads(raw))
                            continue
                        except Exception:
                            pass
                    if raw.startswith("**Happy Path**:"):
                        scenario = raw.split(":", 1)[1].strip() if ":" in raw else ""
                        current.setdefault("test_cases", []).append({
                            "type": "happy_path",
                            "scenario": scenario,
                            "method": current_name.split(".", 1)[1] if current_name and "." in current_name else current_name,
                        })
                        continue
                    if raw.startswith("**Edge Case**:"):
                        scenario = raw.split(":", 1)[1].strip() if ":" in raw else ""
                        current.setdefault("test_cases", []).append({
                            "type": "edge_case",
                            "scenario": scenario,
                            "method": current_name.split(".", 1)[1] if current_name and "." in current_name else current_name,
                        })
                        continue
                    current.setdefault("test_cases", []).append(raw)
                continue
        return specs

    def _parse_validation_block(self, content: str) -> Dict[str, List[str]]:
        rules: Dict[str, List[str]] = {}
        if not content:
            return rules
        kv = self._parse_kv_block(content)
        for key, value in kv.items():
            parts = [p.strip() for p in value.split(",") if p.strip()]
            rules[key] = parts
        return rules

    def _parse_generation_hints(self, sections: Dict[str, str], content: str) -> Dict[str, Any]:
        hints: Dict[str, Any] = {}
        sub = self._split_subsections(content) if content else sections
        hints["entities"] = self._parse_kv_block(self._find_section(sub, ["Entities"]))
        hints["sql_template"] = self._parse_kv_block(self._find_section(sub, ["SQL Template"]))
        hints["validation_template"] = self._parse_kv_block(self._find_section(sub, ["Validation Template"]))
        hints["dto_mapping"] = self._parse_dto_mapping(self._find_section(sub, ["DTO Mapping"]))
        hints["crud_template"] = self._parse_crud_template(self._find_section(sub, ["CRUD Method Template"]))
        hints["entity_specs"] = self._parse_entity_specs(self._find_section(sub, ["Entity Specs"]))
        return hints

    def _parse_dto_mapping(self, content: str) -> Dict[str, List[Dict[str, str]]]:
        mapping = {"create_to_entity": [], "entity_to_response": []}
        if not content:
            return mapping
        current = None
        for line in content.splitlines():
            text = line.strip()
            if not text:
                continue
            if text.startswith("- **CreateRequest -> Entity**"):
                current = "create_to_entity"
                continue
            if text.startswith("- **Entity -> Response**"):
                current = "entity_to_response"
                continue
            if text.startswith("- ") and "->" in text and current:
                item = text[2:].strip()
                parts = [p.strip() for p in item.split("->", 1)]
                if len(parts) == 2:
                    mapping[current].append({"from": parts[0], "to": parts[1]})
        return mapping

    def _parse_crud_template(self, content: str) -> Dict[str, Dict[str, str]]:
        template: Dict[str, Dict[str, str]] = {}
        if not content:
            return template
        current = None
        for line in content.splitlines():
            text = line.strip()
            if not text:
                continue
            if text.startswith("- **") and text.endswith("**:"):
                current = text[4:-3].strip()
                template.setdefault(current, {})
                continue
            if text.startswith("- ") and ":" in text and current:
                item = text[2:].strip()
                key, value = [p.strip() for p in item.split(":", 1)]
                template[current][key] = value
        return template

    def _parse_entity_specs(self, content: str) -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []
        if not content:
            return specs
        current: Optional[Dict[str, Any]] = None
        section: Optional[str] = None
        for line in content.splitlines():
            text = line.strip()
            if not text:
                continue
            if text.startswith("- **Entity**:"):
                name = text.split(":", 1)[1].strip()
                current = {"name": name, "routes": [], "create_mapping": [], "response_mapping": []}
                specs.append(current)
                section = None
                continue
            if current is None:
                continue
            if text.startswith("- Routes:"):
                section = "routes"
                continue
            if text.startswith("- Create Mapping:"):
                section = "create_mapping"
                continue
            if text.startswith("- Response Mapping:"):
                section = "response_mapping"
                continue
            if text.startswith("- ") and ":" in text:
                item = text[2:].strip()
                key, value = [p.strip() for p in item.split(":", 1)]
                if key and value:
                    current[key.lower().replace(" ", "_")] = value
                continue
            if text.startswith("- ") and section == "routes":
                current["routes"].append(text[2:].strip())
                continue
            if text.startswith("- ") and section in ["create_mapping", "response_mapping"] and "->" in text:
                item = text[2:].strip()
                src, dest = [p.strip() for p in item.split("->", 1)]
                current[section].append({"from": src, "to": dest})
                continue
        return specs
