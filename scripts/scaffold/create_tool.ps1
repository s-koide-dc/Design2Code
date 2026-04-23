# PowerShell script to create a new language-specific tool project within the 'tools/' directory.
# Usage: ./create_tool.ps1 -ToolName <tool_name> -Language <language> [-ToolType <tool_type>]

param(
    [Parameter(Mandatory=$true)]
    [string]$ToolName,

    [Parameter(Mandatory=$true)]
    [string]$Language,

    [string]$ToolType = "console_app" # Default to console_app if not specified
)

$ToolDir = "tools\$Language\$ToolName"

Write-Host "Creating tool directory: $ToolDir"
New-Item -Path $ToolDir -ItemType Directory -Force | Out-Null

if (-not $?) {
    Write-Error "Failed to create directory $ToolDir"
    exit 1
}

Write-Host "Initializing basic project for $ToolName ($Language, type: $ToolType)..."

switch ($Language) {
    "csharp" {
        if ($ToolType -eq "library") {
            dotnet new classlib -n $ToolName -o $ToolDir
        } else { # Default to console app
            dotnet new console -n $ToolName -o $ToolDir
        }
    }
    "python" {
        # Basic Python project: create main.py and requirements.txt
        New-Item -Path "$ToolDir\__init__.py" -ItemType File -Force | Out-Null
        Set-Content -Path "$ToolDir\main.py" -Value "# Main script for $ToolName" -Force
        Set-Content -Path "$ToolDir\requirements.txt" -Value "# Add Python dependencies here" -Force
    }
    # Add more language support here
    default {
        Write-Warning "No specific project initialization for language '$Language'. Creating empty directory."
    }
}

if (-not $?) {
    Write-Error "Failed to initialize project for $Language in $ToolDir"
    exit 1
}

Write-Host "Generating README.md for $ToolName..."
$ReadmeContent = @"
# $ToolName ($Language)

## Purpose
[Purpose of this tool, e.g., "Roslynを活用したC#コードの静的解析ツール"]

## Build Instructions
[How to build this tool, e.g., "cd tools/csharp/$ToolName `&`& dotnet build"]

## Usage
[How to use this tool, e.g., "dotnet run --project . <path_to_csharp_file>"]

## Integration with AI Core
This tool is intended to be invoked by the AI's 
`action_executor` module.
Input: [Expected input format, e.g., JSON via stdin]
Output: [Expected output format, e.g., JSON via stdout]

## Configuration
[Describe any configuration options, e.g., "config.json"]

## Important Note
After running 
`create_tool`,
 you **must manually update 
`ai_project_map.json`** to include details of this new tool.
Also, ensure its build step is integrated into the main project's overall build process (e.g., in CI/CD).
"@
Set-Content -Path "$ToolDir\README.md" -Value $ReadmeContent -Force

Write-Host "Tool $ToolName created successfully in $ToolDir!"
Write-Host "Remember to manually update ai_project_map.json and integrate its build process."
