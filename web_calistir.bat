@echo off
chcp 65001 >nul
title Erenler Cumhuriyet Ortaokulu — Web Sunucu

echo.
echo  ========================================================
echo   Erenler Cumhuriyet Ortaokulu — Web Uygulaması
echo  ========================================================
echo.

:: ── Python komutunu bul (PATH + yaygın kurulum klasörleri) ───────────────
set PYCMD=

for %%C in (py python python3) do (
    %%C --version >nul 2>&1
    if !errorlevel!==0 (
        set PYCMD=%%C
        goto :found_py
    )
)

:: PATH'de yok — yaygın kurulum konumlarını tara
for %%D in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "%APPDATA%\Python\Scripts\python.exe"
) do (
    if exist %%D (
        set PYCMD=%%D
        goto :found_py
    )
)

:: Microsoft Store Python
for /d %%D in ("%LOCALAPPDATA%\Microsoft\WindowsApps") do (
    if exist "%%D\python3.exe" ( set PYCMD=%%D\python3.exe & goto :found_py )
    if exist "%%D\python.exe"  ( set PYCMD=%%D\python.exe  & goto :found_py )
)

goto :not_found

:found_py
echo  [OK] Python bulundu: %PYCMD%
echo.

:: ── Flask ve openpyxl kur ────────────────────────────────────────────────
echo  [1/2] Gerekli paketler yukleniyor (sadece 1. sefer biraz bekleyin)...
"%PYCMD%" -m pip install flask openpyxl --quiet --disable-pip-version-check 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  Paket yukleme basarisiz olabilir.
    echo  Devam etmek icin bir tusa basin...
    pause >nul
)
echo  [1/2] Tamamlandi.
echo.

:: ── Sunucuyu başlat ──────────────────────────────────────────────────────
echo  [2/2] Web sunucu baslatiliyor...
echo.

:: IP adresini göster
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /i "IPv4"') do (
    set RAW=%%A
    setlocal enabledelayedexpansion
    set IP=!RAW: =!
    echo  --------------------------------------------------------
    echo   TARAYICIDAN ACIN:
    echo     Bu bilgisayar  : http://localhost:5000
    echo     Telefon / Tahta: http://!IP!:5000
    echo  --------------------------------------------------------
    endlocal
    goto :show_done
)
:show_done

echo.
echo  Bu pencereyi KAPATMAYIN — sunucu calisiyor...
echo.

cd /d "%~dp0"
"%PYCMD%" web_app.py
goto :end

:: ── Python bulunamadı ────────────────────────────────────────────────────
:not_found
echo.
echo  ============================================================
echo   HATA: Python bulunamadi!
echo  ============================================================
echo.
echo   COZUM ADIMLARI:
echo.
echo   1. Asagidaki adresten Python indirin:
echo      https://www.python.org/downloads/
echo.
echo   2. Kurulum penceresinde (cok onemli!):
echo      [X] Add Python to PATH  kutusunu ISARETLEYIN
echo.
echo   3. Kurulumu tamamlayip bu bat dosyasini tekrar calistirin.
echo  ============================================================
echo.
pause
exit /b 1

:end
echo.
echo  Sunucu durdu.
pause
