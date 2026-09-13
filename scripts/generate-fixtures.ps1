[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendPython = Join-Path $projectRoot "backend\.venv\Scripts\python.exe"
$fixtureDirectory = [System.IO.Path]::GetFullPath((Join-Path $projectRoot "backend\tests\fixtures\media"))
$expectedRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot "backend\tests\fixtures"))

if (-not $fixtureDirectory.StartsWith($expectedRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Fixture output must stay inside backend/tests/fixtures."
}
if (-not (Test-Path -LiteralPath $backendPython -PathType Leaf)) {
    throw "Backend environment is missing. Follow the README setup steps first."
}

Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force -Path $fixtureDirectory | Out-Null
$temporaryWave = Join-Path ([System.IO.Path]::GetTempPath()) ("subtitle-forge-" + [guid]::NewGuid().ToString("N") + ".wav")
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voice.SetOutputToWaveFile($temporaryWave)
    $voice.Speak("Subtitle Forge local transcription test. The timestamps should remain in order.")
    $voice.SetOutputToNull()
    & $backendPython (Join-Path $PSScriptRoot "transcode_fixture.py") $temporaryWave $fixtureDirectory
    if ($LASTEXITCODE -ne 0) {
        throw "Fixture transcoding failed with exit code $LASTEXITCODE."
    }
}
finally {
    $voice.Dispose()
    if (Test-Path -LiteralPath $temporaryWave -PathType Leaf) {
        Remove-Item -LiteralPath $temporaryWave -Force
    }
}

Write-Host "Generated public-domain synthetic speech fixtures in $fixtureDirectory"
