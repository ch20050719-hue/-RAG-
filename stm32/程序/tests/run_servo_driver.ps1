param([string]$VcVars = 'E:\vs\VC\Auxiliary\Build\vcvars64.bat')
$ErrorActionPreference = 'Stop'
$firmwareRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$output = Join-Path $projectRoot '.local\tmp\servo-driver-tests'
New-Item -ItemType Directory -Path $output -Force | Out-Null
$env:TEMP = $output
$env:TMP = $output
$env:TMPDIR = $output
$setup = & cmd.exe /d /s /c "`"`"$VcVars`" >nul && set`""
if ($LASTEXITCODE -ne 0) { throw 'Compiler setup failed' }
$paths = @()
$compilerTools = $null
foreach ($line in $setup) {
    if ($line -match '^([^=]+)=(.*)$') {
        if ($matches[1] -ieq 'Path') { $paths += $matches[2]; continue }
        if ($matches[1] -ieq 'VCToolsInstallDir') { $compilerTools = $matches[2] }
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}
if (!$compilerTools) { throw 'Compiler setup did not return VCToolsInstallDir' }
$bin = Join-Path $compilerTools 'bin\Hostx64\x64'
$configuredPath = $paths | Where-Object {
    ($_ -split ';' | ForEach-Object { $_.TrimEnd('\') }) -contains $bin.TrimEnd('\')
} | Select-Object -First 1
if (!$configuredPath) { throw 'Missing compiler PATH' }
$env:Path = $bin + ';' + $configuredPath
$env:TEMP = $output
$env:TMP = $output
$env:TMPDIR = $output
$compiler = Join-Path $bin 'cl.exe'
$servo = Join-Path $firmwareRoot 'HARDWARE\Servo'
Push-Location $output
try {
    & $compiler /nologo /std:c11 /W4 /WX `
        ('/I' + (Join-Path $PSScriptRoot 'servo_stub')) ('/I' + $servo) `
        (Join-Path $PSScriptRoot 'test_servo_driver.c') `
        (Join-Path $servo 'MG90S.c') (Join-Path $servo 'MG90S_logic.c') /Fe:servo_driver_test.exe
    if ($LASTEXITCODE -ne 0) { throw "Servo driver compile failed: $LASTEXITCODE" }
    & (Join-Path $output 'servo_driver_test.exe')
    if ($LASTEXITCODE -ne 0) { throw "Servo driver failed: $LASTEXITCODE" }
} finally { Pop-Location }
