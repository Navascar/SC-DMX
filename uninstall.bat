@echo off
chcp 65001 >nul
echo Видалення SC DMX (налаштування теж буде видалено).
set /p ANS=Продовжити? [y/N] 
if /i not "%ANS%"=="y" exit /b 0
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { Invoke-WebRequest http://127.0.0.1:8080/ -UseBasicParsing -TimeoutSec 2 | Out-Null; Write-Host 'Спочатку вимкніть програму (Налаштування - Про програму - Вимкнути).'; exit 1 } catch { };" ^
  "Remove-Item ([Environment]::GetFolderPath('Desktop') + '\SC DMX.lnk') -ErrorAction SilentlyContinue;" ^
  "Remove-Item ([Environment]::GetFolderPath('Programs') + '\SC DMX.lnk') -ErrorAction SilentlyContinue;" ^
  "Remove-Item \"$env:LOCALAPPDATA\SC-DMX\" -Recurse -Force -ErrorAction SilentlyContinue; Write-Host 'Готово.'"
pause
