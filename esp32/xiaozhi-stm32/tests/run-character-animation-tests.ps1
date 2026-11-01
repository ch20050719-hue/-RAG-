param(
    [string]$AppRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Stm32Source,
    [string]$BuildRoot,
    [string]$VcVars = 'E:\vs\VC\Auxiliary\Build\vcvars64.bat'
)
$ErrorActionPreference = 'Stop'
$AppRoot = (Resolve-Path -LiteralPath $AppRoot).Path
if (!$BuildRoot) { $BuildRoot = Join-Path $AppRoot '.local\tmp\character-animation-tests' }
New-Item -ItemType Directory -Path $BuildRoot -Force | Out-Null
$BuildRoot = (Resolve-Path -LiteralPath $BuildRoot).Path
$env:TEMP = $BuildRoot
$env:TMP = $BuildRoot
$env:TMPDIR = $BuildRoot
if (!(Test-Path -LiteralPath $VcVars -PathType Leaf)) { throw "Missing compiler setup: $VcVars" }
# Import the compiler environment; compilation itself uses argument arrays below.
$compilerEnvironment = & cmd.exe /d /s /c "`"`"$VcVars`" >nul && set`""
if ($LASTEXITCODE -ne 0) { throw 'Compiler environment setup failed' }
$compilerPaths = @()
$compilerToolsDirectory = $null
foreach ($entry in $compilerEnvironment) {
    if ($entry -match '^([^=]+)=(.*)$') {
        $variableName = $matches[1]
        $variableValue = $matches[2]
        if ($variableName -ieq 'Path') {
            $compilerPaths += $variableValue
            continue
        }
        if ($variableName -ieq 'VCToolsInstallDir') { $compilerToolsDirectory = $variableValue }
        [Environment]::SetEnvironmentVariable($variableName, $variableValue, 'Process')
    }
}
if (!$compilerToolsDirectory) { throw 'Compiler setup did not return VCToolsInstallDir' }
$compilerBin = Join-Path $compilerToolsDirectory 'bin\Hostx64\x64'
$compilerExecutable = Join-Path $compilerBin 'cl.exe'
if (!(Test-Path -LiteralPath $compilerExecutable -PathType Leaf)) {
    throw "Missing compiler executable: $compilerExecutable"
}
# Some hosts expose both PATH and Path. Select by content, not capitalization.
$configuredPath = $compilerPaths | Where-Object {
    $segments = $_ -split ';' | ForEach-Object { $_.Trim().TrimEnd('\') }
    $segments -contains $compilerBin.TrimEnd('\')
} | Select-Object -First 1
if (!$configuredPath) { throw 'Compiler setup did not return a PATH containing the compiler directory' }
$env:Path = $compilerBin + ';' + $configuredPath
$env:TEMP = $BuildRoot
$env:TMP = $BuildRoot
$env:TMPDIR = $BuildRoot
$testSource = Join-Path $PSScriptRoot 'character_animation_policy_test.cc'
Push-Location -LiteralPath $BuildRoot
try {
    & $compilerExecutable /nologo /std:c++17 /EHsc /W4 /WX /utf-8 ('/I' + (Join-Path $AppRoot 'main')) $testSource /Fe:character_animation_policy_test.exe
    if ($LASTEXITCODE -ne 0) { throw 'Character animation compilation failed' }
    & (Join-Path $BuildRoot 'character_animation_policy_test.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Character animation tests failed' }
} finally { Pop-Location }
