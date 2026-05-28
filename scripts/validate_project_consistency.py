import os
import json
import re
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(os.getcwd())

from src.utils.cli_output import emit_error, emit_progress

MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")
FENCED_CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```", re.MULTILINE)
PATHLIKE_INLINE_PATTERN = re.compile(
    r"^(?:"
    r"[A-Za-z]:[\\/].+"
    r"|/?[A-Za-z0-9_.\-]+(?:[\\/][A-Za-z0-9_.\-]+)*[\\/][A-Za-z0-9_.\-]+\.(?:md|json|py|ps1|sh|cs|xml)"
    r")$"
)

def get_last_modified_time(file_path):
    """Gets the last modified time of a file/directory."""
    if not file_path or not os.path.exists(file_path):
        return None
    return datetime.fromtimestamp(os.path.getmtime(file_path))

def extract_dependencies(design_file_path):
    """Extracts internal dependencies from a design document."""
    if not design_file_path or not os.path.exists(design_file_path):
        return []
        
    try:
        with open(design_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except IOError:
        return []

    # Find the section starting from 'Dependencies'
    section_match = re.search(r'##\s*3\.\s*Dependencies[\s\S]*', content, re.IGNORECASE)
    if not section_match:
        return []
    
    section_content = section_match.group(0)
    internal_block_match = re.search(r'-\s*\*?\*?(?:Internal|内部)\*?\*?\s*:\s*([\s\S]*?)(?:\n\s*-\s*\*?\*?(?:External|外部)|\n#|\Z)', section_content, re.IGNORECASE)
    if not internal_block_match:
        internal_block_match = re.search(r'-\s*\*?\*?(?:Internal|内部)\*?\*?\s*:\s*(.*)', section_content, re.IGNORECASE)
    
    if not internal_block_match:
        return []
    
    block_text = internal_block_match.group(1).strip()
    
    dependencies = []
    bullets = re.findall(r'-?\s*`?([a-zA-Z0-9_]+)`?(?::|\s|\Z)', block_text)
    if bullets:
        dependencies = [b for b in bullets if b and b.lower() not in ['internal', '内部', 'external', '外部', 'none', 'なし']]
    else:
        dependencies = [dep.strip().replace('`', '').replace('"', '').replace("'", "") for dep in block_text.split(',') if dep.strip()]
    
    dependencies = [d for d in dependencies if d and d.strip(' .').lower() not in ['internal', '内部', 'external', '外部', 'none', 'なし']]
    return dependencies

def find_tool_projects(base_dir="tools"):
    """
    Traverses the 'tools/' directory to identify tool projects.
    """
    tool_projects = []
    if not os.path.exists(base_dir):
        return tool_projects
    
    ignore_dirs = {'bin', 'obj', 'node_modules', '.git', '__pycache__'}
    
    for lang_dir in os.listdir(base_dir):
        lang_path = os.path.join(base_dir, lang_dir)
        if os.path.isdir(lang_path) and lang_dir not in ignore_dirs:
            for tool_name_dir in os.listdir(lang_path):
                tool_path = os.path.join(lang_path, tool_name_dir)
                if os.path.isdir(tool_path) and tool_name_dir not in ignore_dirs:
                    tool_projects.append({
                        "language": lang_dir,
                        "name": tool_name_dir,
                        "path": tool_path
                    })
    return tool_projects

def to_snake_case(name):
    """Converts PascalCase or camelCase to snake_case, handling CSharp as a special case."""
    # Special handling for CSharp to avoid c_sharp
    name = name.replace('CSharp', 'Csharp')
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def strip_fenced_code_blocks(content: str) -> str:
    return FENCED_CODE_BLOCK_PATTERN.sub("", content)

def looks_like_local_reference(raw_reference: str) -> bool:
    candidate = raw_reference.strip()
    if not candidate:
        return False
    lowered = candidate.lower()
    if lowered.startswith(("http://", "https://", "mailto:", "#")):
        return False
    if "://" in candidate:
        return False
    return True

def looks_like_inline_path(raw_reference: str) -> bool:
    candidate = raw_reference.strip()
    if not candidate or " " in candidate:
        return False
    return bool(PATHLIKE_INLINE_PATTERN.match(candidate))

def _resolve_repo_suffix_path(project_root: Path, path_candidate: Path) -> Path | None:
    parts = [part for part in path_candidate.parts if part not in {path_candidate.anchor, "/", "\\"}]
    for start in range(len(parts)):
        suffix = parts[start:]
        if not suffix:
            continue
        resolved = project_root.joinpath(*suffix)
        if resolved.exists():
            return resolved
    return None

def resolve_local_reference(project_root: Path, doc_path: Path, raw_reference: str) -> tuple[Path | None, bool]:
    reference = raw_reference.strip()
    reference = reference.split("#", 1)[0].strip()
    if not reference:
        return doc_path, True

    # App-rendering absolute markdown links appear as `/C:/workspace/...`.
    if reference.startswith("/") and len(reference) >= 4 and reference[2] == ":":
        absolute_path = Path(reference[1:])
        if absolute_path.exists():
            return absolute_path, True
        repo_local = _resolve_repo_suffix_path(project_root, absolute_path)
        if repo_local is not None:
            return repo_local, True
        return None, False

    normalized = Path(reference.replace("/", os.sep).replace("\\", os.sep))
    if normalized.is_absolute():
        if normalized.exists():
            return normalized, True
        repo_local = _resolve_repo_suffix_path(project_root, normalized)
        if repo_local is not None:
            return repo_local, True
        return None, False

    project_relative = project_root / normalized
    if project_relative.exists():
        return project_relative, True
    return doc_path.parent / normalized, True

def _validate_policy_string_list(policy_path: Path, policy: dict, key: str) -> list[str] | None:
    value = policy.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        return None
    return value

def load_document_reference_policy(project_root: Path) -> tuple[list[str], list[str], list[str], list[str]]:
    policy_path = project_root / "config" / "doc_reference_policy.json"
    if not policy_path.exists():
        return [], [], [], [f"Document reference policy not found: {policy_path}"]

    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [], [], [f"Invalid document reference policy '{policy_path}': {exc}"]

    required_docs = _validate_policy_string_list(policy_path, policy, "required_docs")
    if required_docs is None:
        return [], [], [], [f"Invalid document reference policy '{policy_path}': 'required_docs' must be a list of non-empty strings"]

    existence_only_docs = _validate_policy_string_list(policy_path, policy, "existence_only_docs")
    if existence_only_docs is None:
        return [], [], [], [f"Invalid document reference policy '{policy_path}': 'existence_only_docs' must be a list of non-empty strings"]

    optional_reference_docs = _validate_policy_string_list(policy_path, policy, "optional_reference_docs")
    if optional_reference_docs is None:
        optional_reference_docs = _validate_policy_string_list(policy_path, policy, "temporary_docs")
        if optional_reference_docs is None:
            return [], [], [], [f"Invalid document reference policy '{policy_path}': 'optional_reference_docs' must be a list of non-empty strings"]

    return required_docs, existence_only_docs, optional_reference_docs, []

def _format_doc_error(relative_doc_path: str, mode_label: str, detail: str) -> str:
    return f"[doc:{relative_doc_path}][mode:{mode_label}]: {detail}"

def group_errors_by_doc_mode(errors: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    mode_groups = {
        "required": [],
        "existence-only": [],
        "optional-reference": [],
    }
    general_errors = []

    for error in errors:
        matched_mode = None
        for mode_label in mode_groups:
            if f"[mode:{mode_label}]" in error:
                matched_mode = mode_label
                break

        if matched_mode is None:
            general_errors.append(error)
            continue

        mode_groups[matched_mode].append(error)

    return general_errors, mode_groups

def collect_missing_documents(project_root: Path, relative_doc_paths: list[str], mode_label: str) -> list[str]:
    errors = []
    for relative_doc_path in relative_doc_paths:
        doc_path = project_root / relative_doc_path
        if not doc_path.exists():
            errors.append(
                _format_doc_error(
                    relative_doc_path,
                    mode_label,
                    f"検証対象ドキュメントが存在しません: {relative_doc_path}",
                )
            )
    return errors

def collect_missing_document_references(project_root: Path, relative_doc_paths: list[str], mode_label: str) -> list[str]:
    errors = []

    for relative_doc_path in relative_doc_paths:
        doc_path = project_root / relative_doc_path
        if not doc_path.exists():
            continue

        content = doc_path.read_text(encoding="utf-8")
        stripped_content = strip_fenced_code_blocks(content)

        for _, target in MARKDOWN_LINK_PATTERN.findall(stripped_content):
            if not looks_like_local_reference(target):
                continue
            resolved, should_validate = resolve_local_reference(project_root, doc_path, target)
            if not should_validate:
                continue
            if resolved is None or not resolved.exists():
                errors.append(
                    _format_doc_error(
                        relative_doc_path,
                        mode_label,
                        f"ローカル参照が存在しません: {target}",
                    )
                )

        for inline_code in INLINE_CODE_PATTERN.findall(stripped_content):
            if not looks_like_inline_path(inline_code):
                continue
            resolved, should_validate = resolve_local_reference(project_root, doc_path, inline_code)
            if not should_validate:
                continue
            if resolved is None or not resolved.exists():
                errors.append(
                    _format_doc_error(
                        relative_doc_path,
                        mode_label,
                        f"inline code のローカル参照が存在しません: {inline_code}",
                    )
                )

    return errors

def main():
    """
    Main function to validate project consistency.
    """
    project_root = Path(__file__).parent.parent
    src_path = project_root / 'src'
    tools_path = project_root / 'tools'
    project_map_path = project_root / 'ai_project_map.json'
    
    errors = []
    warnings = []
    project_map_modules = set()
    project_map_tools_ids = set()
    project_map_tools_names = set()
    all_known_entities = set()
    required_docs, existence_only_docs, optional_reference_docs, policy_errors = load_document_reference_policy(project_root)
    errors.extend(policy_errors)

    # 1. Load project map
    try:
        with open(project_map_path, 'r', encoding='utf-8') as f:
            project_map = json.load(f)
        project_map_modules = {module['name'] for module in project_map.get('modules', [])}
        
        # Tools matching: use "language/name" as the identifier
        project_map_tools_ids = {f"{tool['language']}/{tool['name']}" for tool in project_map.get('tools_catalog', [])}
        project_map_tools_names = {tool['name'] for tool in project_map.get('tools_catalog', [])}
        
        all_known_entities = project_map_modules | project_map_tools_names

    except (FileNotFoundError, json.JSONDecodeError) as e:
        errors.append(f"Error loading '{project_map_path}': {e}")

    def validate_map_file_reference(owner_label: str, field_label: str, raw_path: str | None):
        if not raw_path:
            return
        resolved = project_root / Path(raw_path)
        if not resolved.exists():
            errors.append(
                f"[{owner_label}]: ai_project_map.json の {field_label} が存在しません: {raw_path}"
            )

    if 'project_map' in locals():
        for module in project_map.get('modules', []):
            if not isinstance(module, dict):
                continue
            module_name = module.get('name', 'unknown')
            owner_label = f"module:{module_name}"

            source_file = module.get('source_file') or {}
            if isinstance(source_file, dict):
                validate_map_file_reference(owner_label, "source_file.path", source_file.get('path'))

            design_document = module.get('design_document') or {}
            if isinstance(design_document, dict):
                validate_map_file_reference(owner_label, "design_document.path", design_document.get('path'))

            validate_map_file_reference(owner_label, "test_file", module.get('test_file'))

        for tool in project_map.get('tools_catalog', []):
            if not isinstance(tool, dict):
                continue
            tool_name = tool.get('name', 'unknown')
            language = tool.get('language', 'unknown')
            owner_label = f"tool:{language}/{tool_name}"

            design_document = tool.get('design_document') or {}
            if isinstance(design_document, dict):
                validate_map_file_reference(owner_label, "design_document.path", design_document.get('path'))

    if required_docs:
        errors.extend(collect_missing_documents(project_root, required_docs, "required"))
        errors.extend(collect_missing_document_references(project_root, required_docs, "required"))
    if existence_only_docs:
        errors.extend(collect_missing_documents(project_root, existence_only_docs, "existence-only"))
    if optional_reference_docs:
        errors.extend(collect_missing_document_references(project_root, optional_reference_docs, "optional-reference"))

    # Standard libraries and common utilities to ignore
    ignore_deps = {'json', 'os', 're', 'sys', 'datetime', 'shutil', 'subprocess', 'retry_with_backoff'}

    # 2. Validate src/ modules
    if not src_path.exists():
        errors.append(f"Source directory '{src_path}' not found.")
    else:
        for module_dir in os.listdir(src_path):
            module_full_path = src_path / module_dir
            if not module_full_path.is_dir() or module_dir.startswith('__'):
                continue
            
            # 規約に基づき、module_name はフォルダ名の snake_case
            module_name = to_snake_case(module_dir)
            
            # a) ai_project_map.json に登録されているか
            if module_name not in project_map_modules:
                warnings.append(f"[module:{module_name}]: Not registered in 'ai_project_map.json'.")
            
            # b) [module_name].design.md または何らかの .design.md が存在するか
            design_doc_name = f"{module_name}.design.md"
            module_design_docs = list(module_full_path.glob("*.design.md"))
            
            primary_design_doc = module_full_path / design_doc_name
            if not primary_design_doc.exists():
                # フォルダ名そのままの可能性も考慮
                primary_design_doc = module_full_path / f"{module_dir}.design.md"
                
            if not primary_design_doc.exists() and not module_design_docs:
                errors.append(f"[module:{module_name}]: Missing any design document (*.design.md).")
                design_mtime = None
            else:
                # 代表的な設計書（あれば primary、なければ最初に見つかったもの）
                actual_design_doc = primary_design_doc if primary_design_doc.exists() else module_design_docs[0]
                
                # c) 鮮度チェック (Freshness Check)
                # 全ての設計書の中で最新のものを基準にする
                design_mtime = max(get_last_modified_time(str(d)) for d in module_design_docs) if module_design_docs else get_last_modified_time(str(actual_design_doc))
                
                outdated = False
                for root, _, files in os.walk(module_full_path):
                    for file in files:
                        if file.endswith(('.py', '.js', '.cs')) and not file.endswith('.design.md'):
                            file_path = os.path.join(root, file)
                            if get_last_modified_time(file_path) > design_mtime:
                                outdated = True
                                break
                    if outdated: break
                
                if outdated:
                    warnings.append(f"[module:{module_name}]: Source files are newer than design documents. Specification might be outdated.")

                # d) 依存関係の整合性チェック (primary があればそれ、なければ全ての設計書から抽出)
                all_deps = set()
                docs_to_scan = [primary_design_doc] if primary_design_doc.exists() else module_design_docs
                for doc in docs_to_scan:
                    all_deps.update(extract_dependencies(str(doc)))
                
                for dep in all_deps:
                    if dep not in all_known_entities and dep not in ignore_deps:
                        # Case insensitive check for ActionExecutor vs action_executor
                        if to_snake_case(dep) not in project_map_modules:
                             warnings.append(f"[module:{module_name}]: Design doc lists unknown dependency '{dep}'.")

    # 3. Validate tools/ catalog
    if not tools_path.exists():
        warnings.append(f"Tools directory '{tools_path}' not found. No tools to validate.")
    else:
        for tool_proj in find_tool_projects(str(tools_path)):
            tool_full_name = f"{tool_proj['language']}/{tool_proj['name']}"
            
            if tool_full_name not in project_map_tools_ids:
                warnings.append(f"[tool:{tool_full_name}]: Not found in 'ai_project_map.json' tools_catalog. Run sync_project_map.py.")
                continue

            design_doc_path = None
            for entry in os.scandir(tool_proj['path']):
                if entry.is_file() and entry.name.endswith('.design.md'):
                    design_doc_path = entry.path
                    break

            if not design_doc_path:
                warnings.append(f"[tool:{tool_full_name}]: Missing design document (*.design.md).")
                continue
            
            tool_folder_mtime = get_last_modified_time(tool_proj['path'])
            design_doc_mtime = get_last_modified_time(design_doc_path)
            if tool_folder_mtime and design_doc_mtime and tool_folder_mtime > design_doc_mtime:
                warnings.append(f"[tool:{tool_full_name}]: Tool folder is newer than its design document. The documentation may be outdated.")

    # 4. Print results
    emit_progress("--- Project Consistency Validation ---")
    if not errors and not warnings:
        emit_progress("OK: All checks passed. Project is consistent.")
        return 0
    else:
        if errors:
            emit_error("")
            emit_error("ERRORS (must be fixed):")
            general_errors, doc_mode_errors = group_errors_by_doc_mode(errors)

            if general_errors:
                emit_error("GENERAL:")
                for error in general_errors:
                    emit_error(f" - {error}")

            doc_section_titles = {
                "required": "DOCS (required):",
                "existence-only": "DOCS (existence-only):",
                "optional-reference": "DOCS (optional-reference):",
            }
            for mode_label, section_title in doc_section_titles.items():
                mode_errors = doc_mode_errors[mode_label]
                if not mode_errors:
                    continue
                emit_error(section_title)
                for error in mode_errors:
                    emit_error(f" - {error}")
        if warnings:
            emit_error("")
            emit_error("WARNINGS (should be reviewed):")
            for warning in warnings:
                emit_error(f" - {warning}")
        emit_error("")
        emit_error("--- End of Validation ---")
        return 1

if __name__ == '__main__':
    sys.exit(main())
