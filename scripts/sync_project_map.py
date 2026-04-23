#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import hashlib
import re
from datetime import datetime

# This script synchronizes the ai_project_map.json with the filesystem.
# Updated to support recursive module discovery and submodules.

def get_file_hash(path):
    """Calculate SHA256 hash of a file."""
    if not os.path.exists(path):
        return None
    sha256 = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
    except IOError:
        return None
    return sha256.hexdigest()

def get_mtime_iso(path):
    """Get last modified time of a file/directory in ISO format."""
    if not os.path.exists(path):
        return None
    return datetime.fromtimestamp(os.path.getmtime(path)).isoformat()

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
    # Filter to look for internal dependencies block
    internal_block_match = re.search(r'-\s*\*?\*?(?:Internal|内部)\*?\*?\s*:\s*([\s\S]*?)(?:\n\s*-\s*\*?\*?(?:External|外部)|\n#|\Z)', section_content, re.IGNORECASE)
    if not internal_block_match:
        internal_block_match = re.search(r'-\s*\*?\*?(?:Internal|内部)\*?\*?\s*:\s*(.*)', section_content, re.IGNORECASE)
    
    if not internal_block_match:
        return []
    
    block_text = internal_block_match.group(1).strip()
    
    # Extract dependencies
    dependencies = []
    bullets = re.findall(r'-?\s*`?([a-zA-Z0-9_]+)`?(?::|\s|\Z)', block_text)
    if bullets:
        dependencies = [b for b in bullets if b and b.lower() not in ['internal', '内部', 'external', '外部', 'none', 'なし']]
    else:
        dependencies = [dep.strip().replace('`', '').replace('"', '').replace("'", "") for dep in block_text.split(',') if dep.strip()]
    
    dependencies = [d for d in dependencies if d and d.strip(' .').lower() not in ['internal', '内部', 'external', '外部', 'none', 'なし']]
    return dependencies

def find_modules_recursive(base_dir):
    """
    Recursively scans for modules defined by .design.md files.
    """
    modules = []
    for root, dirs, files in os.walk(base_dir):
        # Ignore __pycache__ and hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        
        for file in files:
            if file.endswith('.design.md'):
                module_name = file.replace('.design.md', '')
                design_path = os.path.join(root, file)
                
                # Find source file (same name, different extension)
                source_path = None
                for ext in ['.py', '.cs', '.js', '.ts']:
                    potential_source = os.path.join(root, module_name + ext)
                    if os.path.exists(potential_source):
                        source_path = potential_source
                        break
                
                # Find test file (heuristics)
                test_path = None
                # 1. tests/test_{module_name}.py
                potential_test = os.path.join('tests', f'test_{module_name}.py')
                if os.path.exists(potential_test):
                    test_path = potential_test
                # 2. tests/unit/test_{module_name}.py
                elif os.path.exists(os.path.join('tests', 'unit', f'test_{module_name}.py')):
                    test_path = os.path.join('tests', 'unit', f'test_{module_name}.py')
                # 3. Same directory (e.g. for tools or specialized structures)
                elif os.path.exists(os.path.join(root, f'test_{module_name}.py')):
                    test_path = os.path.join(root, f'test_{module_name}.py')

                modules.append({
                    "name": module_name,
                    "design_path": design_path,
                    "source_path": source_path,
                    "test_path": test_path
                })
    return modules

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

def main():
    print("Synchronizing 'ai_project_map.json'...")
    
    map_path = 'ai_project_map.json'
    
    if not os.path.exists(map_path):
        print(f"Error: {map_path} not found.")
        return

    with open(map_path, 'r', encoding='utf-8') as f:
        project_map = json.load(f)

    # --- Sync src/ modules (Recursive) ---
    found_modules = find_modules_recursive('src')
    mapped_modules = {m['name']: m for m in project_map.get('modules', [])}
    updated_modules = []
    seen_names = {}
    
    for mod in found_modules:
        module_name = mod['name']
        
        # Check for name collisions
        if module_name in seen_names:
            print(f"Warning: Module name collision detected for '{module_name}'.")
            print(f"  Existing: {seen_names[module_name]}")
            print(f"  New:      {mod['design_path']}")
            # Skip duplicate for now to avoid map pollution
            continue
        
        seen_names[module_name] = mod['design_path']
        
        module_info = mapped_modules.get(module_name, {
            "name": module_name,
            "summary": "Auto-discovered module.",
            "status": "discovered",
            "dependencies": []
        })
        
        # Update paths and hashes
        if mod['source_path']:
            module_info['source_file'] = {
                "path": mod['source_path'],
                "last_modified": get_mtime_iso(mod['source_path']),
                "hash": get_file_hash(mod['source_path'])
            }
        else:
            module_info['source_file'] = None

        if mod['design_path']:
            module_info['design_document'] = {
                "path": mod['design_path'],
                "last_modified": get_mtime_iso(mod['design_path']),
                "hash": get_file_hash(mod['design_path'])
            }
            # Update dependencies from design doc
            extracted_deps = extract_dependencies(mod['design_path'])
            if extracted_deps:
                module_info['dependencies'] = extracted_deps
        else:
            module_info['design_document'] = None

        module_info['test_file'] = mod['test_path']
        
        updated_modules.append(module_info)
    
    # Identify removed modules
    updated_names = {m['name'] for m in updated_modules}
    removed_modules = [name for name in mapped_modules if name not in updated_names]
    if removed_modules:
        print(f"Removing old modules from map: {', '.join(removed_modules)}")

    # Sort modules by name for consistency
    updated_modules.sort(key=lambda x: x['name'])
    project_map['modules'] = updated_modules

    # --- Sync tools/ catalog ---
    tool_projects = find_tool_projects('tools')
    mapped_tools = {f"{t['language']}/{t['name']}": t for t in project_map.get('tools_catalog', [])}
    updated_tools_catalog = []

    for tool_proj in tool_projects:
        tool_full_name = f"{tool_proj['language']}/{tool_proj['name']}"
        tool_info = mapped_tools.get(tool_full_name, {
            "name": tool_proj['name'],
            "language": tool_proj['language'],
            "summary": "Auto-discovered tool.",
            "status": "discovered",
            "dependencies": []
        })

        tool_info['path'] = tool_proj['path']
        tool_info['last_modified'] = get_mtime_iso(tool_proj['path'])

        readme_path = os.path.join(tool_proj['path'], 'README.md')
        tool_info['readme_file'] = {
            "path": readme_path,
            "last_modified": get_mtime_iso(readme_path),
            "hash": get_file_hash(readme_path)
        } if os.path.exists(readme_path) else None

        config_path = os.path.join(tool_proj['path'], 'config.json')
        tool_info['config_file'] = {
            "path": config_path,
            "last_modified": get_mtime_iso(config_path),
            "hash": get_file_hash(config_path)
        } if os.path.exists(config_path) else None
        
        # Also look for a design doc in the tool folder
        design_path = os.path.join(tool_proj['path'], f"{tool_proj['name']}.design.md")
        if os.path.exists(design_path):
             tool_info['design_document'] = {
                "path": design_path,
                "last_modified": get_mtime_iso(design_path),
                "hash": get_file_hash(design_path)
            }

        updated_tools_catalog.append(tool_info)
    
    project_map['tools_catalog'] = updated_tools_catalog
    project_map['last_updated_by_ai'] = datetime.now().isoformat()
    
    with open(map_path, 'w', encoding='utf-8') as f:
        json.dump(project_map, f, indent=2, ensure_ascii=False)
        
    print("Synchronization complete.")

if __name__ == '__main__':
    main()