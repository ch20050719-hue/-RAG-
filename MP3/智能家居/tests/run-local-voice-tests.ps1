param(
    [string]$VcVars = 'E:\vs\VC\Auxiliary\Build\vcvars64.bat',
    [string]$Python = 'F:\Espressif\tools\python\v6.0.2\venv\Scripts\python.exe'
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$output = Join-Path $projectRoot '.local\tmp\local-voice-tests'
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
$receiver = Join-Path $projectRoot 'stm32\程序\SYSTEM\usart'
Push-Location $output
try {
    # Use the same runtime assertions through a DLL on hosts restricting EXE startup.
    & (Join-Path $bin 'cl.exe') /nologo /std:c11 /W4 /WX /utf-8 /LD `
        ('/I' + $receiver) (Join-Path $PSScriptRoot 'command-word-map-test.c') `
        (Join-Path $receiver 'voice_command.c') /Fe:local_voice_test.dll /link /EXPORT:main
    if ($LASTEXITCODE -ne 0) { throw 'Local voice test compilation failed' }
    & $Python -c 'import ctypes; library=ctypes.CDLL("./local_voice_test.dll"); result=library.main(); print("local voice test exit:", result); raise SystemExit(result)'
    if ($LASTEXITCODE -ne 0) { throw 'Local voice runtime tests failed' }
} finally { Pop-Location }
