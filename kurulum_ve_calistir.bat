@echo off
chcp 65001 >nul
title Öğrenci Takip Uygulaması - Kurulum

echo ================================================
echo  Erenler Cumhuriyet Ortaokulu
echo  Öğrenci Takip Uygulaması - Kurulum
echo ================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo HATA: Python bulunamadı! Lütfen python.org adresinden Python'u indirin.
    pause
    exit /b 1
)

echo [1/2] Gerekli kütüphaneler kuruluyor...
pip install customtkinter openpyxl --quiet --upgrade

echo.
echo [2/2] Uygulama başlatılıyor...
echo.

python main.py

pause
