param([string]$VcVars = 'E:\vs\VC\Auxiliary\Build\vcvars64.bat')
$ErrorActionPreference = 'Stop'
$firmwareRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$output = Join-Path $projectRoot '.local\tmp\usart-control-tests'
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
$usart = Join-Path $firmwareRoot 'SYSTEM\usart'
Push-Location $output
try {
    # Legacy Keil stdio has an ARM-only pragma and an intentionally unused FILE argument.
    # Rename firmware fputc only in this host build to avoid the host CRT symbol.
    & $compiler /nologo /std:c11 /W4 /WX /wd4068 /wd4100 /wd4819 /Dfputc=Firmware_fputc `
        ('/I' + (Join-Path $PSScriptRoot 'usart_stub')) ('/I' + $usart) `
        (Join-Path $PSScriptRoot 'test_usart_control.c') `
        (Join-Path $usart 'usart.c') (Join-Path $usart 'voice_command.c') /Fe:usart_control_test.exe
    if ($LASTEXITCODE -ne 0) { throw "USART integration compile failed: $LASTEXITCODE" }
    & (Join-Path $output 'usart_control_test.exe')
    if ($LASTEXITCODE -ne 0) { throw "USART integration failed: $LASTEXITCODE" }
    & $compiler /nologo /std:c11 /W4 /WX ('/I' + $usart) `
        (Join-Path $PSScriptRoot 'test_voice_command.c') (Join-Path $usart 'voice_command.c') /Fe:voice_command_test.exe
    if ($LASTEXITCODE -ne 0) { throw "Parser regression compile failed: $LASTEXITCODE" }
    & (Join-Path $output 'voice_command_test.exe')
    if ($LASTEXITCODE -ne 0) { throw "Parser regression failed: $LASTEXITCODE" }
} finally { Pop-Location }
