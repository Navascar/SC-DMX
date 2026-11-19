@echo off
chcp 65001 >nul
echo Видалення Nitor (налаштування теж буде видалено).
set /p ANS=Продовжити? [y/N] 
if /i not "%ANS%"=="y" exit /b 0
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "if (Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -match 'dmxctl|nitor\.pyw|sc-dmx\.pyw' }) { Write-Host 'Спочатку закрийте вікно Nitor.'; exit 1 };" ^
  "foreach ($n in 'Nitor', 'SC DMX') { foreach ($d in 'Desktop', 'Programs') { Remove-Item ([Environment]::GetFolderPath($d) + '\' + $n + '.lnk') -ErrorAction SilentlyContinue } };" ^
  "foreach ($n in 'Nitor', 'SC-DMX') { Remove-Item ('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\' + $n) -Recurse -ErrorAction SilentlyContinue };" ^
  "Remove-Item (Join-Path $env:LOCALAPPDATA 'Nitor'), (Join-Path $env:LOCALAPPDATA 'SC-DMX') -Recurse -Force -ErrorAction SilentlyContinue; Write-Host 'Готово.'"
pause
