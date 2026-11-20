# Build VideoDownloader.exe using PyInstaller without wiping output/
$ErrorActionPreference = "Stop"

$stagingDist = Join-Path $PSScriptRoot "dist\_staging"
if (Test-Path $stagingDist) {
    Remove-Item -Path $stagingDist -Recurse -Force
}

Write-Host "Building VideoDownloader.exe..." -ForegroundColor Cyan
pyinstaller --noconfirm --clean --windowed --distpath $stagingDist --name "VideoDownloader" app.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

$distDir = Join-Path $PSScriptRoot "dist\VideoDownloader"
New-Item -ItemType Directory -Force -Path $distDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $distDir "bin") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $distDir "output") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $distDir "temp") | Out-Null

# Copy built app files into dist\VideoDownloader without touching output/ or temp/
Copy-Item -Path (Join-Path $stagingDist "VideoDownloader\*") -Destination $distDir -Recurse -Force
Remove-Item -Path $stagingDist -Recurse -Force

$localBin = Join-Path $PSScriptRoot "bin\*"
if (Test-Path (Join-Path $PSScriptRoot "bin")) {
    Copy-Item -Path $localBin -Destination (Join-Path $distDir "bin") -Force -ErrorAction SilentlyContinue
}

Write-Host "Build completed: $distDir\VideoDownloader.exe" -ForegroundColor Green
