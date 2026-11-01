param(
    [string]$ApplicationRoot = 'F:\esp\v6.0.2\esp-idf-2\xiaozhi-stm32',
    [string]$VsDevCmd = 'E:\vs\Common7\Tools\VsDevCmd.bat',
    [string]$Python = 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$decoder = Join-Path $ApplicationRoot 'main\display\lvgl_display\gif'
$assets = Join-Path $projectRoot 'img\character-animation'
$buildRoot = Join-Path $projectRoot '.local\tmp\avatar-decoder-tests'
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
$lines = @()
Push-Location $buildRoot
try {
    foreach ($cache in @(0, 1)) {
        $command = '"{0}" -arch=x64 && cl /nologo /TC /W3 /DLV_GIF_CACHE_DECODE_DATA={1} /I"{2}" /I"{3}" "{2}\decode_test.c" "{3}\gifdec.c" /Fe:decode_cache{1}.exe' -f $VsDevCmd, $cache, $PSScriptRoot, $decoder
        & cmd /c $command
        if ($LASTEXITCODE -ne 0) { throw "Compilation failed for cache $cache" }
        foreach ($case in @(@('character_idle', 'idle', 2), @('character_talking', 'talking', 4))) {
            # Narrow fopen uses ASCII filenames inside the current build directory.
            Copy-Item -LiteralPath (Join-Path $assets ($case[0] + '.gif')) -Destination ($case[0] + '.gif')
            $result = & ".\decode_cache$cache.exe" ($case[0] + '.gif') ($case[1] + $cache + '.bgra') $case[2]
            if ($LASTEXITCODE -ne 0) { throw "Decode failed for $($case[0]), cache $cache" }
            $lines += $result
            $result | Write-Output
        }
    }
    & $Python (Join-Path $PSScriptRoot 'compare_frames.py') $buildRoot $assets
    if ($LASTEXITCODE -ne 0) { throw 'Pillow comparison failed' }
    $lines | Set-Content -Encoding utf8 (Join-Path $buildRoot 'decoder-results.txt')
} finally { Pop-Location }
