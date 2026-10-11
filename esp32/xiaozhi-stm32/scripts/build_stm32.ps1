param(
    [switch]$UseLocalComponents,
    [string]$SdkRoot = $env:IDF_PATH
)
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($SdkRoot)) { $SdkRoot = 'F:\esp\v6.0.2\esp-idf-2' }
if (!(Test-Path -LiteralPath (Join-Path $SdkRoot 'tools\idf.py'))) {
    throw 'Provide -SdkRoot pointing to an installed ESP-IDF 6.0.2 SDK.'
}
$sdkRoot = (Resolve-Path -LiteralPath $SdkRoot).Path
$pythonExe = 'F:\Espressif\tools\python\v6.0.2\venv\Scripts\python.exe'
$localComponents = 'F:\esp32\xiaozhi-esp32-main\xiaozhi-esp32-main\managed_components'
if (!(Test-Path -LiteralPath $pythonExe)) { throw 'Set pythonExe to your installed ESP-IDF Python environment.' }
$env:TEMP = Join-Path $appRoot '.local\tmp'
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
$env:IDF_COMPONENT_CACHE_PATH = Join-Path $appRoot '.local\cache\components'
$env:PIP_CACHE_DIR = Join-Path $appRoot '.local\cache\pip'
$env:CCACHE_DIR = Join-Path $appRoot '.local\cache\ccache'
$env:PYTHONPYCACHEPREFIX = Join-Path $appRoot '.local\cache\pycache'
$env:IDF_PATH = $sdkRoot
$env:IDF_TOOLS_PATH = 'F:\Espressif'
$env:IDF_PYTHON_ENV_PATH = Split-Path -Parent (Split-Path -Parent $pythonExe)
$env:PATH = (Split-Path -Parent $pythonExe) + ';' + $env:PATH
foreach ($dir in @($env:TEMP, $env:IDF_COMPONENT_CACHE_PATH, $env:PIP_CACHE_DIR, $env:CCACHE_DIR)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}
Push-Location $appRoot
try {
    # Tool discovery is read-only; the script does not install or update the SDK.
    $exports = & $pythonExe (Join-Path $sdkRoot 'tools\idf_tools.py') export --format key-value
    if ($LASTEXITCODE -ne 0) { throw 'ESP-IDF tool export failed.' }
    foreach ($line in $exports) {
        if ($line -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
            $value = $Matches[2].Replace('%PATH%', $env:PATH).Replace('$PATH', $env:PATH)
            [Environment]::SetEnvironmentVariable($Matches[1], $value, 'Process')
        }
    }
    # This installation keeps its Python constraints in the tools directory.
    # Executable paths have already been exported above; do not relocate tools.
    $env:IDF_TOOLS_PATH = 'F:\Espressif\tools'
    if ($UseLocalComponents) {
        if (!(Test-Path -LiteralPath $localComponents)) { throw 'Local components directory is unavailable.' }
        $destination = Join-Path $appRoot 'managed_components'
        if (!(Test-Path -LiteralPath $destination)) {
            # Seed with unchanged installed packages; the component manager validates them.
            Copy-Item -LiteralPath $localComponents -Destination $destination -Recurse
        }
    }
    $env:IDF_COMPONENT_MANAGER = '1'
    Remove-Item Env:STM32_LOCAL_COMPONENTS -ErrorAction SilentlyContinue
    & $pythonExe scripts/build.py bread-compact-stm32-lcd --name bread-compact-stm32-lcd
    if ($LASTEXITCODE -ne 0) { throw "Build failed (exit $LASTEXITCODE)." }
} finally {
    Pop-Location
}
