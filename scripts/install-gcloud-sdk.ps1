# Install Google Cloud SDK and add gcloud to User PATH (no gcloud init).
# Run: powershell -ExecutionPolicy Bypass -File scripts\install-gcloud-sdk.ps1

$ErrorActionPreference = 'Stop'
$sdkUrl = 'https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-windows-x86_64.zip'
$installBase = Join-Path $env:LOCALAPPDATA 'Google'
$zipPath = Join-Path $env:TEMP 'google-cloud-cli-windows.zip'
$extractParent = Join-Path $installBase 'cloud-sdk-extract'

if (-not (Test-Path $installBase)) { New-Item -ItemType Directory -Path $installBase -Force | Out-Null }

Write-Host 'Downloading Google Cloud SDK (about 81 MB)...'
Invoke-WebRequest -Uri $sdkUrl -OutFile $zipPath -UseBasicParsing

if (Test-Path $extractParent) { Remove-Item $extractParent -Recurse -Force }
New-Item -ItemType Directory -Path $extractParent -Force | Out-Null

Write-Host 'Extracting...'
Expand-Archive -Path $zipPath -DestinationPath $extractParent -Force
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue

$sdkFolder = Get-ChildItem $extractParent -Directory | Select-Object -First 1
if (-not $sdkFolder) { throw "No folder in archive" }
$finalRoot = Join-Path $installBase 'google-cloud-sdk'
if (Test-Path $finalRoot) { Remove-Item $finalRoot -Recurse -Force }
Move-Item $sdkFolder.FullName $finalRoot
Remove-Item $extractParent -Recurse -Force -ErrorAction SilentlyContinue

$binPath = Join-Path $finalRoot 'bin'
if (-not (Test-Path (Join-Path $binPath 'gcloud.cmd'))) { throw "gcloud.cmd not found under $finalRoot" }

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -notlike "*$binPath*") {
  [Environment]::SetEnvironmentVariable('Path', $userPath.TrimEnd(';') + ';' + $binPath, 'User')
  Write-Host "Added to User PATH: $binPath"
} else {
  Write-Host "Already in User PATH: $binPath"
}

Write-Host "Google Cloud SDK installed at: $finalRoot"
Write-Host "Close and reopen your terminal, then run: gcloud init"
