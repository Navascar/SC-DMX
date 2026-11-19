@echo off
rem Запуск з консоллю (для діагностики). Звичайний запуск — ярлик «Nitor».
chcp 65001 >nul
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Програму ще не встановлено — запускаю інсталятор...
  call "%~dp0install.bat"
  exit /b
)
"%PY%" -m dmxctl --open
pause
