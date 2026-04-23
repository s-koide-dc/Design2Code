import os
import re
import json
import xml.etree.ElementTree as ET

def sync_dependencies(root_dir):
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
        if "node_modules" in root or ".git" in root or "cache" in root:
            continue
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
            print(f"Error parsing {csproj}: {e}")

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
    
    print(f"Project context synced to {output_path}")
    print(f"Found {len(output['packages'])} packages across {len(output['projects'])} projects.")

if __name__ == "__main__":
    sync_dependencies(os.getcwd())
