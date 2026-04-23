import os
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime

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
        all_known_entities = set()

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
    print("--- Project Consistency Validation ---")
    if not errors and not warnings:
        print("OK: All checks passed. Project is consistent.")
    else:
        if errors:
            print("\nERRORS (must be fixed):")
            for error in errors:
                print(f" - {error}")
        if warnings:
            print("\nWARNINGS (should be reviewed):")
            for warning in warnings:
                print(f" - {warning}")
        print("\n--- End of Validation ---")
        exit(1)

if __name__ == '__main__':
    main()