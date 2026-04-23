# create_module.ps1
# This script automates the creation of a new module in a Windows PowerShell environment.

[CmdletBinding()]
param (
    [Parameter(Mandatory=$true, Position=0)]
    [string]$ModuleName,

    [Parameter(Mandatory=$true, Position=1)]
    [ValidateSet("js", "py", "cs")]
    [string]$Language,

    [Parameter(Mandatory=$false, Position=2)]
    [string]$SourceFileName
)

Write-Host "Creating new module: $ModuleName ($Language)"

# 1. Create directory
$moduleDir = "src\$ModuleName"
New-Item -ItemType Directory -Path $moduleDir -ErrorAction Stop

# 2. Create source and test files based on language
$sourceFile = ""
$testFile = ""

switch ($Language) {
    "js" {
        $fileName = if ([string]::IsNullOrEmpty($SourceFileName)) { "$ModuleName.js" } else { $SourceFileName }
        $sourceFile = Join-Path $moduleDir $fileName
        $testFile = "tests\test_$ModuleName.js"
    }
    "py" {
        $fileName = if ([string]::IsNullOrEmpty($SourceFileName)) { "$ModuleName.py" } else { $SourceFileName }
        $sourceFile = Join-Path $moduleDir $fileName
        $testFile = "tests\test_$ModuleName.py"
    }
    "cs" {
        $fileName = if ([string]::IsNullOrEmpty($SourceFileName)) { "$ModuleName.cs" } else { $SourceFileName }
        $sourceFile = Join-Path $moduleDir $fileName
        $testFile = "tests\test_$ModuleName.cs"
    }
}

New-Item -ItemType File -Path $sourceFile -ErrorAction Stop
New-Item -ItemType File -Path $testFile -ErrorAction Stop

# 3. Create design document from template
$templatePath = "AIFiles\templates\design_document.md"
$newDesignDocPath = Join-Path $moduleDir "${ModuleName}.design.md"
Copy-Item -Path $templatePath -Destination $newDesignDocPath -ErrorAction Stop

# Replace placeholder in the new design doc
(Get-Content $newDesignDocPath -Raw) -replace '\[Module Name\]', $ModuleName | Set-Content $newDesignDocPath -Encoding UTF8

# 4. Update ai_project_map.json
# This part is complex and is best handled by a dedicated Python script.
Write-Host "IMPORTANT: You must now manually update 'ai_project_map.json' with the new module information." -ForegroundColor Yellow
Write-Host "In a real implementation, this script would call another tool to do this automatically." -ForegroundColor Yellow

Write-Host "Module '$ModuleName' created successfully. Please fill in the file contents." -ForegroundColor Green
