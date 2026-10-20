#Requires -Version 5.1
<#
.SYNOPSIS
  บิลด์ GenJab installer แบบออฟไลน์: pyinstaller -> staging -> iscc
  รันจาก repo root:  powershell -ExecutionPolicy Bypass -File installer\build.ps1
  ผลลัพธ์: installer\Output\GenJab-Setup-<ver>.exe
#>
[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"

$installerDir = $PSScriptRoot
$root = Split-Path $installerDir -Parent
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) { throw "ไม่พบ venv python ที่ $venvPython" }

# 1. PyInstaller
& $venvPython -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "ติดตั้ง pyinstaller..."
  & $venvPython -m pip install pyinstaller
}
Write-Host "== pyinstaller =="
Push-Location $root
try {
  & (Join-Path $root ".venv\Scripts\pyinstaller.exe") --noconfirm --onedir --windowed --name GenJab app.py
  if ($LASTEXITCODE -ne 0) { throw "pyinstaller ล้มเหลว" }
} finally { Pop-Location }

# 2. staging
$staging = Join-Path $installerDir "staging"
$appStage = Join-Path $staging "app"
$modelsStage = Join-Path $staging "models"
Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory $appStage, $modelsStage, (Join-Path $appStage "runtime") -Force | Out-Null

Write-Host "== staging app =="
Copy-Item (Join-Path $root "dist\GenJab\*") $appStage -Recurse -Force

Write-Host "== staging runtime =="
$runtimeSrc = Join-Path $env:LOCALAPPDATA "Amuse\RuntimeStableDiffusionCpp\vulkan"
if (-not (Test-Path (Join-Path $runtimeSrc "sd-cli.exe"))) { throw "ไม่พบ sd-cli.exe ที่ $runtimeSrc (ต้องลงแอป Amuse ในเครื่องบิลด์ก่อน)" }
Copy-Item (Join-Path $runtimeSrc "*") (Join-Path $appStage "runtime") -Recurse -Force

Write-Host "== staging models =="
$weights = Get-ChildItem (Join-Path $env:USERPROFILE ".cache\huggingface\hub\models--stabilityai--sd-turbo\snapshots") -Recurse -Filter "sd_turbo.safetensors" -File -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $weights) { throw "ไม่พบ sd_turbo.safetensors ใน HF cache (โหลดมาก่อนบิลด์)" }
Copy-Item $weights.FullName (Join-Path $modelsStage "sd_turbo.safetensors") -Force

foreach ($f in @((Join-Path $appStage "GenJab.exe"),
                (Join-Path $appStage "runtime\sd-cli.exe"),
                (Join-Path $modelsStage "sd_turbo.safetensors"))) {
  if (-not (Test-Path $f)) { throw "staging ไม่ครบ ขาด $f" }
}

# 3. iscc
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
          "C:\Program Files (x86)\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
  $cmd = Get-Command iscc -ErrorAction SilentlyContinue
  if ($cmd) { $iscc = $cmd.Source }
}
if (-not $iscc) { throw "ไม่พบ Inno Setup (iscc) — ติดตั้งก่อน: winget install JRSoftware.InnoSetup" }
Write-Host "== iscc ($iscc) =="
Push-Location $installerDir
try {
  & $iscc "GenJab.iss"
  if ($LASTEXITCODE -ne 0) { throw "iscc ล้มเหลว" }
} finally { Pop-Location }

$setupFiles = @((Get-ChildItem (Join-Path $installerDir "Output\*") -File))
$totalGB = ($setupFiles | Measure-Object Length -Sum).Sum / 1GB
Write-Host ("เสร็จ: {0} ({1} ไฟล์, {2:N1} GB รวม) — ก๊อปทั้งโฟลเดอร์ไปติดตั้ง" -f $setupFiles[0].DirectoryName, $setupFiles.Count, $totalGB)
