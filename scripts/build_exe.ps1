param(
    [switch]$CleanOutput
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$specPath = Join-Path $repoRoot "AirDropPlus.spec"
$distDir = Join-Path $repoRoot "dist\AirDropPlus"
$buildDir = Join-Path $repoRoot "build\AirDropPlus"

if (-not (Test-Path $specPath)) {
    throw "PyInstaller spec not found: $specPath"
}

if ($CleanOutput) {
    if (Test-Path $distDir) {
        Remove-Item -Path $distDir -Recurse -Force
    }
    if (Test-Path $buildDir) {
        Remove-Item -Path $buildDir -Recurse -Force
    }
}

Write-Host "Building executable from spec: $specPath"
& python -m PyInstaller --noconfirm --clean $specPath
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

Write-Host ""
Write-Host "Build completed."
Write-Host "Output: $distDir"
