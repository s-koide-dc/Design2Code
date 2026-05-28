import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.utils.cli_output import emit_error, emit_progress

SKIP_DIR_NAMES = {".git", "cache", "node_modules"}


def sync_dependencies(root_dir: str) -> int:
    dependencies = {
        "packages": set(),
        "assemblies": set(),
        "projects": []
    }
    
    # 常に利用可能とみなす標準名前空間
    dependencies["packages"].add("System")
    dependencies["packages"].add("System.Linq")
    dependencies["packages"].add("System.IO")
    dependencies["packages"].add("System.Threading.Tasks")
    dependencies["packages"].add("System.Text.Json")

    csproj_files = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [directory for directory in dirs if directory.lower() not in SKIP_DIR_NAMES]
        for file in files:
            if file.endswith(".csproj"):
                csproj_files.append(os.path.join(root, file))

    for csproj in csproj_files:
        try:
            tree = ET.parse(csproj)
            root = tree.getroot()
            
            # PackageReference
            for pkg in root.findall(".//PackageReference"):
                name = pkg.get("Include")
                if name:
                    dependencies["packages"].add(name)
            
            # Reference
            for ref in root.findall(".//Reference"):
                name = ref.get("Include")
                if name:
                    dependencies["assemblies"].add(name.split(',')[0])
                    
            dependencies["projects"].append(os.path.relpath(csproj, root_dir))
        except Exception as e:
            emit_error(f"警告: csproj の解析に失敗しました: {csproj}: {e}")

    # Convert sets to lists for JSON serialization
    output = {
        "packages": sorted(list(dependencies["packages"])),
        "assemblies": sorted(list(dependencies["assemblies"])),
        "projects": dependencies["projects"]
    }
    
    output_path = os.path.join(root_dir, "config", "current_project_context.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    emit_progress(f"Project context synced to {output_path}")
    emit_progress(f"Found {len(output['packages'])} packages across {len(output['projects'])} projects.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync current project dependencies into config/current_project_context.json")
    parser.add_argument(
        "--root",
        default=os.getcwd(),
        help="Project root to scan (default: current working directory)",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(sync_dependencies(os.path.abspath(args.root)))
