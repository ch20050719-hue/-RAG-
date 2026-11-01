param(
    [string]$AppRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Stm32Source,
    [string]$BuildRoot,
    [string]$VcVars = 'E:\vs\VC\Auxiliary\Build\vcvars64.bat'
)
$ErrorActionPreference = 'Stop'
$AppRoot = (Resolve-Path -LiteralPath $AppRoot).Path
if (!$BuildRoot) { $BuildRoot = Join-Path $AppRoot '.local\tmp\stm32-control-tests' }
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
$testSource = Join-Path $PSScriptRoot 'stm32_control_protocol_test.cc'
$arguments = @('/nologo', '/std:c++17', '/EHsc', '/W4', '/WX', '/utf-8',
    ('/I' + (Join-Path $AppRoot 'main')), $testSource,
    ('/Fe:' + (Join-Path $BuildRoot 'stm32_control_protocol_test.exe')))
if ($Stm32Source) {
    $Stm32Source = (Resolve-Path -LiteralPath $Stm32Source).Path
    $receiverDirectory = Join-Path $Stm32Source 'SYSTEM\usart'
    $receiverSource = Join-Path $receiverDirectory 'voice_command.c'
    if (!(Test-Path -LiteralPath $receiverSource)) { throw "Missing STM32 receiver: $receiverSource" }
    $arguments += @('/DWITH_STM32_RECEIVER', ('/I' + $receiverDirectory),
        (Join-Path $BuildRoot 'voice_command.obj'))
}
Push-Location -LiteralPath $BuildRoot
try {
    if ($Stm32Source) {
        & $compilerExecutable /nologo /W4 /WX /utf-8 /TC /c $receiverSource
        if ($LASTEXITCODE -ne 0) { throw "STM32 receiver compilation failed: $LASTEXITCODE" }
    }
    & $compilerExecutable @arguments
    if ($LASTEXITCODE -ne 0) { throw "Test compilation failed: $LASTEXITCODE" }
    & (Join-Path $BuildRoot 'stm32_control_protocol_test.exe')
    if ($LASTEXITCODE -ne 0) { throw "Runtime tests failed: $LASTEXITCODE" }
    $uartArguments = @('/nologo', '/std:c++17', '/EHsc', '/W4', '/WX', '/utf-8',
        ('/I' + (Join-Path $PSScriptRoot 'stubs')), ('/I' + (Join-Path $AppRoot 'main')),
        (Join-Path $PSScriptRoot 'stm32_uart_device_test.cc'),
        ('/Fe:' + (Join-Path $BuildRoot 'stm32_uart_device_test.exe')))
    & $compilerExecutable @uartArguments
    if ($LASTEXITCODE -ne 0) { throw "UART test compilation failed: $LASTEXITCODE" }
    & (Join-Path $BuildRoot 'stm32_uart_device_test.exe')
    if ($LASTEXITCODE -ne 0) { throw "UART runtime tests failed: $LASTEXITCODE" }
    $environmentArguments = @('/nologo', '/std:c++17', '/EHsc', '/W4', '/WX', '/utf-8',
        ('/I' + (Join-Path $AppRoot 'main')),
        (Join-Path $PSScriptRoot 'stm32_environment_test.cc'),
        ('/Fe:' + (Join-Path $BuildRoot 'stm32_environment_test.exe')))
    if ($Stm32Source) {
        $environmentArguments += @('/DWITH_STM32_ENV_ENCODER',
            ('/I' + (Join-Path $Stm32Source 'SYSTEM\usart')))
    }
    & $compilerExecutable @environmentArguments
    if ($LASTEXITCODE -ne 0) { throw "Environment test compilation failed: $LASTEXITCODE" }
    & (Join-Path $BuildRoot 'stm32_environment_test.exe')
    if ($LASTEXITCODE -ne 0) { throw "Environment runtime tests failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}
