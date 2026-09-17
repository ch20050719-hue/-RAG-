[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$launcher = Join-Path $PSScriptRoot 'start-demo.ps1'
$output = & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $launcher -Action Start -DryRun -NoBrowser
if ($LASTEXITCODE -ne 0) {
    throw "Launcher DryRun failed with exit code: $LASTEXITCODE"
}

$text = $output -join "`n"
foreach ($expected in @('Backend command:', 'Frontend command:', 'http://127.0.0.1:5500', 'app.main:app', 'vite.js')) {
    if ($text -notlike "*$expected*") {
        throw "DryRun output is missing: $expected"
    }
}

Write-Host 'start-demo.ps1 DryRun test passed.' -ForegroundColor Green
