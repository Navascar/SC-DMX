; SC DMX — інсталятор для Windows (SC-DMX-Setup.exe).
;
; Збирається під час релізу (.github/workflows/release.yml):
;   makensis -DVERSION=1.21.0 -DSRC=<тека з файлами програми> installer/sc-dmx.nsi
;
; Інсталятор містить усю програму. Він розпаковує її в тимчасову теку й запускає install.ps1:
; той знаходить або встановлює Python, копіює програму в %LOCALAPPDATA%\SC-DMX (налаштування
; зберігаються), ставить залежності й створює ярлики. Права адміністратора не потрібні.

Unicode true
SetCompressor /SOLID lzma

!ifndef VERSION
  !define VERSION "0.0.0"
!endif
!ifndef SRC
  !define SRC ".."
!endif
!ifndef OUTFILE
  !define OUTFILE "SC-DMX-Setup.exe"
!endif

!define APP "SC DMX"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\SC-DMX"

Name "${APP}"
Caption "${APP} ${VERSION} — встановлення"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\SC-DMX"
RequestExecutionLevel user
ShowInstDetails show
BrandingText "${APP} ${VERSION}"

VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=1058 "ProductName" "${APP}"
VIAddVersionKey /LANG=1058 "FileDescription" "Встановлення ${APP}"
VIAddVersionKey /LANG=1058 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=1058 "ProductVersion" "${VERSION}"
VIAddVersionKey /LANG=1058 "LegalCopyright" "${APP}"

!include "MUI2.nsh"
!include "LogicLib.nsh"

!define MUI_ICON "${SRC}\dmxctl\static\icon.ico"
!define MUI_UNICON "${SRC}\dmxctl\static\icon.ico"
!define MUI_ABORTWARNING

!define MUI_WELCOMEPAGE_TITLE "Встановлення ${APP} ${VERSION}"
!define MUI_WELCOMEPAGE_TEXT "Програма керує RGB-прожекторами через USB DMX (uDMX) та інші DMX-інтерфейси.$\r$\n$\r$\nІнсталятор встановить програму для поточного користувача. Якщо на комп'ютері немає Python, його буде встановлено автоматично.$\r$\n$\r$\nПід час першого встановлення завантажується близько 250 МБ (вбудоване вікно програми), тож потрібен інтернет. Відкриється вікно з ходом встановлення, не закривайте його.$\r$\n$\r$\nЯкщо SC DMX уже встановлено, програму буде оновлено, а налаштування й сцени збережуться."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_TITLE "${APP} встановлено"
!define MUI_FINISHPAGE_TEXT "Надалі запускайте програму ярликом «SC DMX» на робочому столі або в меню «Пуск». Оновлення програма пропонує сама."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Запустити SC DMX"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchApp
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Ukrainian"

Function LaunchApp
  SetOutPath "$INSTDIR"
  Exec '"$INSTDIR\.venv\Scripts\pythonw.exe" -m dmxctl --open'
FunctionEnd

Section "SC DMX"
  InitPluginsDir
  DetailPrint "Розпакування програми…"
  SetOutPath "$PLUGINSDIR\app"
  File /r /x ".git" /x "__pycache__" /x ".venv" /x "installer" "${SRC}\*.*"

  DetailPrint "Встановлення: Python, залежності, ярлики (окреме вікно)…"
  ; інсталятор 32-бітний: на 64-бітній Windows беремо 64-бітний PowerShell
  StrCpy $1 "$WINDIR\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
  ${IfNot} ${FileExists} "$1"
    StrCpy $1 "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe"
  ${EndIf}
  ExecWait '"$1" -NoProfile -ExecutionPolicy Bypass -File "$PLUGINSDIR\app\install.ps1" -NoLaunch' $0
  ${If} $0 != 0
    SetOutPath "$TEMP"
    MessageBox MB_ICONSTOP "Встановлення не завершено (код $0). Подробиці були у вікні встановлення.$\r$\nПеревірте інтернет і запустіть інсталятор ще раз."
    Abort "Встановлення не завершено"
  ${EndIf}
  ${IfNot} ${FileExists} "$INSTDIR\.venv\Scripts\pythonw.exe"
    SetOutPath "$TEMP"
    MessageBox MB_ICONSTOP "Встановлення не завершено: не знайдено середовище Python програми."
    Abort "Встановлення не завершено"
  ${EndIf}

  ; тимчасові файли більше не потрібні
  SetOutPath "$TEMP"
  RMDir /r "$PLUGINSDIR\app"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${APP}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "${APP}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\dmxctl\static\icon.ico"
  WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegStr HKCU "${UNINST_KEY}" "URLInfoAbout" "https://github.com/Navascar/SC-DMX"
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
SectionEnd

Function un.onInit
  MessageBox MB_YESNO|MB_ICONQUESTION "Видалити SC DMX разом із налаштуваннями, приладами й сценами?$\r$\nЩоб зберегти сцени, спершу збережіть їх у файли (меню сцени → «Зберегти у файл»)." /SD IDYES IDYES +2
  Abort
FunctionEnd

Section "Uninstall"
  ; програма має бути закрита, інакше файли зайняті
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "try { Invoke-WebRequest http://127.0.0.1:8080/ -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 1 } catch { exit 0 }"'
  Pop $0
  ${If} $0 == 1
    MessageBox MB_ICONEXCLAMATION "SC DMX зараз відкрито. Закрийте вікно програми й запустіть видалення ще раз." /SD IDOK
    Abort
  ${EndIf}
  Delete "$DESKTOP\SC DMX.lnk"
  Delete "$SMPROGRAMS\SC DMX.lnk"
  SetOutPath "$TEMP"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${UNINST_KEY}"
SectionEnd
