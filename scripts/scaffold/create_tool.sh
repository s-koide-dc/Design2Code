#!/bin/bash

# Script to create a new language-specific tool project within the 'tools/' directory.
# Usage: ./create_tool.sh <tool_name> <language> [tool_type]

tool_name=$1
language=$2
tool_type=$3 # Optional, e.g., console_app, library

if [ -z "$tool_name" ] || [ -z "$language" ]; then
  echo "Usage: $0 <tool_name> <language> [tool_type]"
  echo "Example: $0 MyRoslynAnalyzer csharp console_app"
  exit 1
fi

tool_dir="tools/${language}/${tool_name}"

echo "Creating tool directory: ${tool_dir}"
mkdir -p "$tool_dir"

if [ $? -ne 0 ]; then
  echo "Error: Failed to create directory ${tool_dir}"
  exit 1
fi

echo "Initializing basic project for ${tool_name} (${language}, type: ${tool_type:-default})..."

case "$language" in
  "csharp")
    if [ "$tool_type" == "library" ]; then
      dotnet new classlib -n "$tool_name" -o "$tool_dir"
    else # Default to console app
      dotnet new console -n "$tool_name" -o "$tool_dir"
    fi
    ;;
  "python")
    # Basic Python project: create main.py and requirements.txt
    mkdir -p "$tool_dir"
    touch "$tool_dir/__init__.py"
    echo "# Main script for ${tool_name}" > "$tool_dir/main.py"
    echo "# Add Python dependencies here" > "$tool_dir/requirements.txt"
    ;;
  # Add more language support here
  *)
    echo "Warning: No specific project initialization for language '$language'. Creating empty directory."
    ;;
esac

if [ $? -ne 0 ]; then
  echo "Error: Failed to initialize project for ${language} in ${tool_dir}"
  exit 1
fi

echo "Generating README.md for ${tool_name}..."
cat << EOF > "$tool_dir/README.md"
# ${tool_name} (${language})

## Purpose
[Purpose of this tool, e.g., "Roslynを活用したC#コードの静的解析ツール"]

## Build Instructions
[How to build this tool, e.g., "cd tools/csharp/${tool_name} && dotnet build"]

## Usage
[How to use this tool, e.g., "dotnet run --project . <path_to_csharp_file>"]

## Integration with AI Core
This tool is intended to be invoked by the AI's 
 module.
Input: [Expected input format, e.g., JSON via stdin]
Output: [Expected output format, e.g., JSON via stdout]

## Configuration
[Describe any configuration options, e.g., "config.json"]

## Important Note
After running 
, you **must manually update 
 to include details of this new tool.
Also, ensure its build step is integrated into the main project's overall build process (e.g., in CI/CD).
EOF

echo "Tool ${tool_name} created successfully in ${tool_dir}!"
echo "Remember to manually update ai_project_map.json and integrate its build process."
