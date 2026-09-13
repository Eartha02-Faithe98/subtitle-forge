[CmdletBinding()]
param(
    [ValidateSet("", "backend", "frontend", "security", "browser", "openspec")]
    [string]$InduceFailure = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $projectRoot "backend"
$frontendDirectory = Join-Path $projectRoot "frontend"
$runtimeDirectory = [System.IO.Path]::GetFullPath((Join-Path $projectRoot "runtime"))

function Invoke-VerificationStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [ValidateSet("backend", "frontend", "security", "browser", "openspec")]
        [string]$Group,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Host "`n==> $Name"
    if ($InduceFailure -and $Group -eq $InduceFailure) {
        & powershell.exe -NoProfile -Command "exit 91"
        exit $LASTEXITCODE
    }
    $global:LASTEXITCODE = 0
    & $Action
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        [Console]::Error.WriteLine("$Name failed with exit code $exitCode")
        exit $exitCode
    }
}

function Assert-NoSecretSignatures {
    $matches = & rg `
        --glob "!*.test.*" `
        --glob "!node_modules/**" `
        --glob "!.venv/**" `
        --glob "!.next/**" `
        --glob "!runtime/**" `
        --ignore-case `
        '(sk-[A-Za-z0-9]{16,}|api[_-]?key\s*[:=]\s*[^\s"]{8,}|bearer\s+[A-Za-z0-9._-]{16,})' `
        backend/src frontend/src scripts .env.example
    if ($LASTEXITCODE -eq 0) {
        $matches | Write-Host
        throw "Potential secret material was found in shipped source."
    }
    if ($LASTEXITCODE -ne 1) {
        throw "Secret signature scan could not complete."
    }
    $global:LASTEXITCODE = 0
}

function Invoke-BackendPytest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [string[]]$Tests = @()
    )

    $baseTemp = [System.IO.Path]::GetFullPath((Join-Path $runtimeDirectory "pytest-$Name"))
    if (-not $baseTemp.StartsWith($runtimeDirectory + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Pytest temporary path must stay inside runtime."
    }
    New-Item -ItemType Directory -Force -Path $runtimeDirectory | Out-Null
    if (Test-Path -LiteralPath $baseTemp) {
        Remove-Item -LiteralPath $baseTemp -Recurse -Force
    }
    try {
        & ".venv\Scripts\python.exe" -m pytest -q -p no:cacheprovider --basetemp $baseTemp @Tests
        $pytestExitCode = $LASTEXITCODE
    }
    finally {
        if (Test-Path -LiteralPath $baseTemp) {
            Remove-Item -LiteralPath $baseTemp -Recurse -Force
        }
    }
    $global:LASTEXITCODE = $pytestExitCode
}

function Invoke-BackendMypy {
    $mypyCache = [System.IO.Path]::GetFullPath((Join-Path $runtimeDirectory "mypy-cache"))
    if (-not $mypyCache.StartsWith($runtimeDirectory + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Mypy cache path must stay inside runtime."
    }
    New-Item -ItemType Directory -Force -Path $runtimeDirectory | Out-Null
    if (Test-Path -LiteralPath $mypyCache) {
        Remove-Item -LiteralPath $mypyCache -Recurse -Force
    }
    $mypyExitCode = 1
    try {
        & ".venv\Scripts\python.exe" -m mypy --no-incremental --cache-dir $mypyCache
        $mypyExitCode = $LASTEXITCODE
    }
    finally {
        if (Test-Path -LiteralPath $mypyCache) {
            Remove-Item -LiteralPath $mypyCache -Recurse -Force
        }
    }
    $global:LASTEXITCODE = $mypyExitCode
}

Push-Location $backendDirectory
try {
    Invoke-VerificationStep "Backend format" -Group "backend" { & ".venv\Scripts\ruff.exe" format --check --no-cache . "..\scripts\transcode_fixture.py" }
    Invoke-VerificationStep "Backend lint" -Group "backend" { & ".venv\Scripts\ruff.exe" check --no-cache . "..\scripts\transcode_fixture.py" }
    Invoke-VerificationStep "Backend types" -Group "backend" { Invoke-BackendMypy }
    Invoke-VerificationStep "Backend tests" -Group "backend" { Invoke-BackendPytest -Name "backend-full" }
    Invoke-VerificationStep "Phase 1 API and artifact integration" -Group "backend" { Invoke-BackendPytest -Name "phase1-integration" -Tests @("tests\test_phase1_api_integration.py", "tests\test_artifact_download_api.py") }
}
finally {
    Pop-Location
}

Push-Location $frontendDirectory
try {
    Remove-Item Env:NO_COLOR -ErrorAction SilentlyContinue
    Invoke-VerificationStep "Frontend format" -Group "frontend" { & npm.cmd run format:check }
    Invoke-VerificationStep "Frontend lint" -Group "frontend" { & npm.cmd run lint }
    Invoke-VerificationStep "Frontend types" -Group "frontend" { & npm.cmd run typecheck }
    Invoke-VerificationStep "Frontend tests" -Group "frontend" { & npm.cmd test }
    Invoke-VerificationStep "Frontend build" -Group "frontend" { & npm.cmd run build }
    Invoke-VerificationStep "Browser smoke test" -Group "browser" { & npm.cmd run smoke }
}
finally {
    Pop-Location
}

Push-Location $projectRoot
try {
    Invoke-VerificationStep "Secret signature scan" -Group "security" { Assert-NoSecretSignatures }
    Invoke-VerificationStep "OpenSpec strict validation" -Group "openspec" { & openspec validate establish-phase-1-local-web-ui-mvp --strict }
}
finally {
    Pop-Location
}

Write-Host "`nAll Subtitle Forge Phase 1 deterministic verification steps passed."
