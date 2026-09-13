[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $projectRoot "backend"
$frontendDirectory = Join-Path $projectRoot "frontend"

function Invoke-VerificationStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Host "`n==> $Name"
    & $Action
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        [Console]::Error.WriteLine("$Name failed with exit code $exitCode")
        exit $exitCode
    }
}

Push-Location $backendDirectory
try {
    Invoke-VerificationStep "Backend format" { & ".venv\Scripts\ruff.exe" format --check . }
    Invoke-VerificationStep "Backend lint" { & ".venv\Scripts\ruff.exe" check . }
    Invoke-VerificationStep "Backend types" { & ".venv\Scripts\mypy.exe" }
    Invoke-VerificationStep "Backend tests" { & ".venv\Scripts\python.exe" -m pytest -q }
}
finally {
    Pop-Location
}

Push-Location $frontendDirectory
try {
    Remove-Item Env:NO_COLOR -ErrorAction SilentlyContinue
    Invoke-VerificationStep "Frontend format" { & npm.cmd run format:check }
    Invoke-VerificationStep "Frontend lint" { & npm.cmd run lint }
    Invoke-VerificationStep "Frontend types" { & npm.cmd run typecheck }
    Invoke-VerificationStep "Frontend tests" { & npm.cmd test }
    Invoke-VerificationStep "Frontend build" { & npm.cmd run build }
    Invoke-VerificationStep "Browser smoke test" { & npm.cmd run smoke }
}
finally {
    Pop-Location
}

Write-Host "`nAll Subtitle Forge Phase 0 verification steps passed."
