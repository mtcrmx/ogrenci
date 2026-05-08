# PowerShell baslatic - Python'u otomatik bulur ve web sunucuyu baslatir
$Host.UI.RawUI.WindowTitle = "Erenler Cumhuriyet Ortaokulu - Web Sunucu"

Write-Host ""
Write-Host "  ========================================================" -ForegroundColor Cyan
Write-Host "   Erenler Cumhuriyet Ortaokulu - Web Uygulamasi" -ForegroundColor White
Write-Host "  ========================================================" -ForegroundColor Cyan
Write-Host ""

# Python'u bul - once PATH'de ara
$python = $null

foreach ($cmd in @("py", "python", "python3")) {
    try {
        $null = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0) { $python = $cmd; break }
    } catch {}
}

# PATH'de yoksa klasorleri tara
if (-not $python) {
    $aramaYerleri = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python39\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe"
    )
    foreach ($yol in $aramaYerleri) {
        if (Test-Path $yol) { $python = $yol; break }
    }
}

if (-not $python) {
    Write-Host "  HATA: Python bulunamadi!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Cozum: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "  Kurulumda 'Add Python to PATH' secenegini isaretleyin." -ForegroundColor Yellow
    Read-Host "  Cikmak icin Enter'a basin"
    exit 1
}

Write-Host "  [OK] Python: $python" -ForegroundColor Green
Write-Host ""

# Paketleri kur
Write-Host "  [1/2] Paketler yukleniyor..." -ForegroundColor Yellow
& $python -m pip install flask openpyxl --quiet --disable-pip-version-check
Write-Host "  [1/2] Tamamlandi." -ForegroundColor Green
Write-Host ""

# IP'yi goster
try {
    $ip = (Get-NetIPAddress -AddressFamily IPv4 |
           Where-Object { $_.IPAddress -notmatch "^127\." -and $_.PrefixOrigin -ne "WellKnown" } |
           Select-Object -First 1).IPAddress
} catch { $ip = $null }

Write-Host "  --------------------------------------------------------" -ForegroundColor Cyan
Write-Host "   TARAYICIDAN ACIN:" -ForegroundColor White
Write-Host "     Bu bilgisayar  : http://localhost:5000" -ForegroundColor Green
if ($ip) {
    Write-Host "     Telefon / Tahta: http://${ip}:5000" -ForegroundColor Green
}
Write-Host "  --------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Bu pencereyi KAPATMAYIN - sunucu calisiyor..." -ForegroundColor Yellow
Write-Host ""

Set-Location $PSScriptRoot
& $python web_app.py
