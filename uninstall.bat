@echo off
chcp 65001 >nul
echo Видалення SC DMX (налаштування теж буде видалено).
set /p ANS=Продовжити? [y/N] 
if /i not "%ANS%"=="y" exit /b 0
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "if (Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -match 'dmxctl|sc-dmx\.pyw' }) { Write-Host 'Спочатку закрийте вікно SC DMX.'; exit 1 };" ^
  "Remove-Item ([Environment]::GetFolderPath('Desktop') + '\SC DMX.lnk') -ErrorAction SilentlyContinue;" ^
  "Remove-Item ([Environment]::GetFolderPath('Programs') + '\SC DMX.lnk') -ErrorAction SilentlyContinue;" ^
  "Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\SC-DMX' -Recurse -ErrorAction SilentlyContinue;" ^
  "Remove-Item \"$env:LOCALAPPDATA\SC-DMX\" -Recurse -Force -ErrorAction SilentlyContinue; Write-Host 'Готово.'"
pause
