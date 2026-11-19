@echo off
rem Nitor — встановлення / оновлення вручну. Подробиці в install.ps1
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 pause
