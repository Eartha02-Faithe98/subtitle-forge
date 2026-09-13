[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $projectRoot "backend"
$frontendDirectory = Join-Path $projectRoot "frontend"
$backendPython = Join-Path $backendDirectory ".venv\Scripts\python.exe"
$runtimeDirectory = Join-Path $projectRoot "runtime"
$defaultDataRoot = Join-Path $runtimeDirectory "data\jobs"

if (-not (Test-Path -LiteralPath $backendPython)) {
    throw "Backend environment is missing. Follow the README setup steps first."
}

$npmCommand = (Get-Command npm.cmd -ErrorAction Stop).Source
$frontendPort = if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 3000 }
$backendPort = if ($env:SUBTITLE_FORGE_PORT) { [int]$env:SUBTITLE_FORGE_PORT } else { 8000 }
$backendHost = if ($env:SUBTITLE_FORGE_HOST) { $env:SUBTITLE_FORGE_HOST } else { "127.0.0.1" }
$frontendUrl = "http://127.0.0.1:$frontendPort"
$backendUrl = "http://${backendHost}:$backendPort"

if (-not $env:SUBTITLE_FORGE_ALLOWED_ORIGINS) {
    $env:SUBTITLE_FORGE_ALLOWED_ORIGINS = "[`"http://localhost:$frontendPort`",`"$frontendUrl`"]"
}
if (-not $env:NEXT_PUBLIC_API_BASE_URL) {
    $env:NEXT_PUBLIC_API_BASE_URL = $backendUrl
}
if (-not $env:SUBTITLE_FORGE_DATA_ROOT) {
    $env:SUBTITLE_FORGE_DATA_ROOT = $defaultDataRoot
}

$resolvedRuntime = [System.IO.Path]::GetFullPath($runtimeDirectory)
$resolvedDefaultData = [System.IO.Path]::GetFullPath($defaultDataRoot)
if (-not $resolvedDefaultData.StartsWith($resolvedRuntime + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "The managed data directory must stay inside runtime."
}
New-Item -ItemType Directory -Force -Path $resolvedRuntime | Out-Null
if ($env:SUBTITLE_FORGE_DATA_ROOT -eq $defaultDataRoot) {
    New-Item -ItemType Directory -Force -Path $resolvedDefaultData | Out-Null
}

function Wait-ForUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    throw "Timed out waiting for $Url"
}

$backendProcess = $null
$frontendProcess = $null

try {
    $backendProcess = Start-Process `
        -FilePath $backendPython `
        -ArgumentList @("-m", "uvicorn", "subtitle_forge_api.app:app", "--host", $backendHost, "--port", $backendPort) `
        -WorkingDirectory $backendDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeDirectory "backend.stdout.log") `
        -RedirectStandardError (Join-Path $runtimeDirectory "backend.stderr.log") `
        -PassThru

    $frontendProcess = Start-Process `
        -FilePath $npmCommand `
        -ArgumentList @("run", "dev", "--", "--hostname", "127.0.0.1", "--port", $frontendPort) `
        -WorkingDirectory $frontendDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeDirectory "frontend.stdout.log") `
        -RedirectStandardError (Join-Path $runtimeDirectory "frontend.stderr.log") `
        -PassThru

    Wait-ForUrl -Url "$backendUrl/health"
    Wait-ForUrl -Url $frontendUrl

    $readiness = Invoke-RestMethod -Uri "$backendUrl/readiness" -TimeoutSec 10
    Write-Host "Processing readiness: $($readiness.status)"
    foreach ($dependency in $readiness.dependencies.PSObject.Properties) {
        $state = if ($dependency.Value.available) { "ready" } else { "needs setup" }
        Write-Host "  $($dependency.Name): $state - $($dependency.Value.message)"
    }

    $databasePath = Join-Path (Split-Path -Parent $env:SUBTITLE_FORGE_DATA_ROOT) "jobs.sqlite3"
    if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) {
        throw "SQLite initialization did not create the managed job database."
    }

    if ($backendProcess.HasExited -or $frontendProcess.HasExited) {
        throw "A Subtitle Forge development process exited during startup. Check runtime logs."
    }

    Write-Host "Subtitle Forge is running."
    Write-Host "Frontend: $frontendUrl"
    Write-Host "Backend:  $backendUrl"
    Write-Host "Data:     $env:SUBTITLE_FORGE_DATA_ROOT"
    Write-Host "Press Ctrl+C to stop both processes."

    while (-not $backendProcess.HasExited -and -not $frontendProcess.HasExited) {
        Start-Sleep -Seconds 1
        $backendProcess.Refresh()
        $frontendProcess.Refresh()
    }

    throw "A Subtitle Forge development process exited unexpectedly. Check runtime logs."
}
finally {
    foreach ($process in @($frontendProcess, $backendProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            Wait-Process -Id $process.Id -Timeout 10 -ErrorAction SilentlyContinue
        }
    }
}
