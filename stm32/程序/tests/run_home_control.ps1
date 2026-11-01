param([string]$VcVars = 'E:\vs\VC\Auxiliary\Build\vcvars64.bat')
$ErrorActionPreference = 'Stop'
$firmwareRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$output = Join-Path $projectRoot '.local\tmp\home-control-tests'
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
$timer = Join-Path $firmwareRoot 'SYSTEM\TIM2'
Push-Location $output
try {
    & $compiler /nologo /std:c11 /W4 /WX /source-charset:.936 /wd4819 `
        ('/I' + (Join-Path $PSScriptRoot 'home_control_stub')) ('/I' + $timer) `
        ('/I' + (Join-Path $firmwareRoot 'HARDWARE\Servo')) `
        (Join-Path $PSScriptRoot 'test_home_control.c') `
        (Join-Path $timer 'TIM2.c') /Fe:home_control_test.exe
    if ($LASTEXITCODE -ne 0) { throw "Home control compile failed: $LASTEXITCODE" }
    & (Join-Path $output 'home_control_test.exe')
    if ($LASTEXITCODE -ne 0) { throw "Home control failed: $LASTEXITCODE" }
} finally { Pop-Location }

