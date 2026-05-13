@echo off
chcp 65001 >nul
title Erenler Cumhuriyet Ortaokulu - INTERNET Modu

echo.
echo  ========================================================
echo   INTERNET MODU - Her yerden erisim
echo   (Cloudflare Tunnel - ucretsiz, hesap gerekmez)
echo  ========================================================
echo.

cd /d "%~dp0"

:: ── Python bul ───────────────────────────────────────────────────────────
set PYCMD=
for %%C in (py python python3) do (
    %%C --version >nul 2>&1 && set PYCMD=%%C && goto :py_ok
)
for %%D in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
) do (if exist %%D set PYCMD=%%D && goto :py_ok)
echo  HATA: Python bulunamadi! Once WEB_BASLAT.bat calistirin.
pause & exit /b 1
:py_ok
echo  [OK] Python: %PYCMD%

:: ── Cloudflared indir (yoksa) ────────────────────────────────────────────
if exist "%~dp0cloudflared.exe" goto :cf_ok

echo.
echo  [1/3] cloudflared.exe indiriliyor (Cloudflare Tunnel)...
echo        (Sadece 1. sefer indirilir, ~35 MB)
echo.

powershell -Command "& { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%~dp0cloudflared.exe' }"

if not exist "%~dp0cloudflared.exe" (
    echo  HATA: cloudflared indirilemedi. Internete bagli misiniz?
    pause & exit /b 1
)
echo  [1/3] cloudflared indirildi.

:cf_ok
echo  [OK] cloudflared hazir.
echo.

:: ── Flask paketleri ──────────────────────────────────────────────────────
echo  [2/3] Paketler kontrol ediliyor...
"%PYCMD%" -m pip install flask openpyxl --quiet --disable-pip-version-check
echo  [2/3] Tamamlandi.
echo.

:: ── Flask'i arka planda başlat ───────────────────────────────────────────
echo  [3/3] Sunucu ve internet tuneli baslatiliyor...
echo.

start "Flask Sunucu" /min "%PYCMD%" "%~dp0web_app.py"
timeout /t 3 /nobreak >nul

:: ── Cloudflare tüneli ────────────────────────────────────────────────────
echo  ============================================================
echo.
echo   Asagida gorunen https://xxxx.trycloudflare.com adresini
echo   kopyalayip butun ogretmenlerle paylasin.
echo.
echo   Adres her seferinde degisir. Sabitleme icin render.com
echo   kullanin (BULUT_KURULUM.txt dosyasina bakin).
echo.
echo  ============================================================
echo.

"%~dp0cloudflared.exe" tunnel --url http://localhost:5000

echo.
echo  Tunel kapandi. Sunucu hala calisiyor olabilir.
pause
