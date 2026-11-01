[CmdletBinding()]
param(
    [ValidateSet('Start', 'Stop', 'Restart', 'Status')]
    [string]$Action = 'Start',
    [switch]$NoBrowser,
    [switch]$DryRun,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5500
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $ProjectRoot 'rag_backend'
$FrontendRoot = Join-Path $ProjectRoot 'rag_frontend'
$PythonExe = Join-Path $BackendRoot '.venv\Scripts\python.exe'
$ViteCli = Join-Path $FrontendRoot 'node_modules\vite\bin\vite.js'
$StateRoot = Join-Path $ProjectRoot '.demo'
$StateFile = Join-Path $StateRoot 'processes.json'

function Read-DemoState {
    if (-not (Test-Path -LiteralPath $StateFile)) {
        return $null
    }

    try {
        return Get-Content -LiteralPath $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        Write-Warning "Could not read state file; treating the demo as stopped: $StateFile"
        return $null
    }
}

function Remove-DemoState {
    if (Test-Path -LiteralPath $StateFile) {
        Remove-Item -LiteralPath $StateFile -Force
    }
}

function Stop-TrackedProcess {
    param(
        [Parameter(Mandatory)][int]$ProcessId,
        [Parameter(Mandatory)][string]$Name
    )

    if ($ProcessId -le 0) {
        return
    }

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Write-Host "$Name is already stopped (PID $ProcessId does not exist)." -ForegroundColor DarkGray
        return
    }

    Write-Host "Stopping $Name (PID $ProcessId)..."
    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
    }
    catch {
        Write-Warning "$Name could not be stopped directly: $($_.Exception.Message)"
    }

    $stillRunning = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -ne $stillRunning) {
        & taskkill.exe /PID $ProcessId /T /F > $null 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "$Name stop command returned code $LASTEXITCODE."
        }
    }
}

function Stop-Demo {
    $state = Read-DemoState
    if ($null -eq $state) {
        Write-Host 'No tracked demo services found.'
        return
    }

    Stop-TrackedProcess -ProcessId ([int]$state.backend.pid) -Name 'backend'
    Stop-TrackedProcess -ProcessId ([int]$state.frontend.pid) -Name 'frontend'
    Remove-DemoState
    Write-Host 'Local backend and frontend stopped.' -ForegroundColor Green
}

function Start-DemoProcess {
    param(
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string]$Executable,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    return Start-Process `
        -FilePath $Executable `
        -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Normal `
        -PassThru
}

function Test-LocalEndpoint {
    param([Parameter(Mandatory)][string]$Url)

    try {
        $null = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $true
    }
    catch {
        return $false
    }
}

function Test-PortInUse {
    param([Parameter(Mandatory)][int]$Port)

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connection = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $connection.AsyncWaitHandle.WaitOne(500)) {
            return $false
        }
        $client.EndConnect($connection)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Wait-LocalEndpoint {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Url,
        [Parameter(Mandatory)][int]$ProcessId,
        [int]$TimeoutSeconds = 15
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($null -eq $process) {
            Write-Warning "$Name process stopped before becoming ready: PID $ProcessId"
            return $false
        }
        if (Test-LocalEndpoint -Url $Url) {
            Write-Host "$Name is ready: $Url" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Milliseconds 500
    }

    Write-Warning "$Name did not respond: $Url. Check its service window."
    return $false
}

function Show-DemoStatus {
    $state = Read-DemoState
    if ($null -eq $state) {
        Write-Host 'Status: stopped.'
        return
    }

    foreach ($service in @($state.backend, $state.frontend)) {
        $process = Get-Process -Id ([int]$service.pid) -ErrorAction SilentlyContinue
        $processStatus = if ($null -eq $process) { 'process stopped' } else { "process running (PID $($service.pid))" }
        $healthStatus = if (Test-LocalEndpoint -Url $service.healthUrl) { 'service reachable' } else { 'service not responding' }
        Write-Host "$($service.name): $processStatus, $healthStatus, $($service.url)"
    }
}

function Start-Demo {
    if (-not (Test-Path -LiteralPath $PythonExe)) {
        throw "Backend virtual environment not found: $PythonExe"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot 'package.json'))) {
        throw "Frontend package.json not found: $FrontendRoot"
    }
    if (-not (Test-Path -LiteralPath $ViteCli)) {
        throw "Vite CLI not found: $ViteCli. Run npm install in rag_frontend first."
    }

    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($null -eq $node) {
        throw 'node.exe was not found. Install Node.js and add node to PATH.'
    }

    $state = Read-DemoState
    if ($null -ne $state) {
        $backendProcess = Get-Process -Id ([int]$state.backend.pid) -ErrorAction SilentlyContinue
        $frontendProcess = Get-Process -Id ([int]$state.frontend.pid) -ErrorAction SilentlyContinue
        if ($null -ne $backendProcess -or $null -ne $frontendProcess) {
            Write-Host 'The demo appears to be running. To reload configuration, run:' -ForegroundColor Yellow
            Write-Host '.\scripts\start-demo.cmd -Restart'
            return
        }
        Remove-DemoState
    }

    $backendArguments = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort")
    $frontendArguments = @("`"$ViteCli`"", '--host', '127.0.0.1', '--port', "$FrontendPort")

    if ($DryRun) {
        Write-Output "Backend directory: $BackendRoot"
        Write-Output "Backend command: $PythonExe $($backendArguments -join ' ')"
        Write-Output "Frontend directory: $FrontendRoot"
        Write-Output "Frontend command: $($node.Source) $($frontendArguments -join ' ')"
        Write-Output "URL: http://127.0.0.1:$FrontendPort"
        return
    }

    foreach ($port in @($BackendPort, $FrontendPort)) {
        if (Test-PortInUse -Port $port) {
            throw "Port $port is already in use. Stop the existing service or choose another port."
        }
    }

    if (-not (Test-Path -LiteralPath $StateRoot)) {
        New-Item -ItemType Directory -Path $StateRoot | Out-Null
    }

    $backendProcess = $null
    $frontendProcess = $null
    try {
        $backendProcess = Start-DemoProcess `
            -WorkingDirectory $BackendRoot `
            -Executable $PythonExe `
            -Arguments $backendArguments

        $frontendProcess = Start-DemoProcess `
            -WorkingDirectory $FrontendRoot `
            -Executable $node.Source `
            -Arguments $frontendArguments

        $newState = [ordered]@{
            startedAt = (Get-Date).ToString('o')
            backend = [ordered]@{
                name = 'backend'
                pid = $backendProcess.Id
                url = "http://127.0.0.1:$BackendPort"
                healthUrl = "http://127.0.0.1:$BackendPort/api/health"
            }
            frontend = [ordered]@{
                name = 'frontend'
                pid = $frontendProcess.Id
                url = "http://127.0.0.1:$FrontendPort"
                healthUrl = "http://127.0.0.1:$FrontendPort"
            }
        }
        $newState | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StateFile -Encoding UTF8
    }
    catch {
        if ($null -ne $backendProcess) {
            Stop-TrackedProcess -ProcessId $backendProcess.Id -Name 'backend'
        }
        if ($null -ne $frontendProcess) {
            Stop-TrackedProcess -ProcessId $frontendProcess.Id -Name 'frontend'
        }
        throw
    }

    Write-Host "Backend and frontend launch commands started. State file: $StateFile" -ForegroundColor Green
    Write-Host 'Two service windows stay open. After code/config changes, run .\scripts\start-demo.cmd -Restart.'
    $null = Wait-LocalEndpoint -Name 'backend' -Url "http://127.0.0.1:$BackendPort/api/health" -ProcessId $backendProcess.Id
    $null = Wait-LocalEndpoint -Name 'frontend' -Url "http://127.0.0.1:$FrontendPort" -ProcessId $frontendProcess.Id

    if (-not $NoBrowser) {
        Start-Process "http://127.0.0.1:$FrontendPort"
    }
}

switch ($Action) {
    'Start' { Start-Demo }
    'Stop' { Stop-Demo }
    'Restart' {
        Stop-Demo
        Start-Demo
    }
    'Status' { Show-DemoStatus }
}
