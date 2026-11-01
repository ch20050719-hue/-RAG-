param([string]$VcVars = 'E:\vs\VC\Auxiliary\Build\vcvars64.bat', [string]$ProductSource, [string]$Python = 'F:\Espressif\tools\python\v6.0.2\venv\Scripts\python.exe')
$ErrorActionPreference = 'Stop'
$firmwareRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$output = Join-Path $projectRoot '.local\tmp\remote-fix-20261028\mode'
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
$driver = Join-Path $PSScriptRoot 'test_remote_mode.c'
if ($ProductSource) {
    $source = (Resolve-Path $ProductSource).Path.Replace('\','/')
    $fixture = $driver.Replace('\','/')
    $driver = Join-Path $output 'remote_mode_driver.c'
    [IO.File]::WriteAllText($driver, "#define REMOTE_PRODUCT_SOURCE `"$source`"`n#include `"$fixture`"`n")
}
Push-Location $output
try {
    & $compiler /nologo /std:c11 /utf-8 /W3 /wd4819 /wd4005 /Gy /LD `
        ('/I' + (Join-Path $firmwareRoot 'Gizwits')) ('/I' + $timer) `
        ('/I' + (Join-Path $PSScriptRoot 'home_control_stub')) `
        ('/I' + (Join-Path $firmwareRoot 'Utils')) `
        ('/I' + (Join-Path $firmwareRoot 'HARDWARE\Servo')) `
        $driver (Join-Path $timer 'TIM2.c') /Fe:remote_mode_test.dll `
        /link /OPT:REF /EXPORT:main
    if ($LASTEXITCODE -ne 0) { throw "Remote mode compile failed: $LASTEXITCODE" }
    & $Python -c 'import ctypes; lib=ctypes.CDLL("./remote_mode_test.dll"); raise SystemExit(lib.main())'
    if ($LASTEXITCODE -ne 0) { throw "Remote mode failed: $LASTEXITCODE" }
} finally { Pop-Location }