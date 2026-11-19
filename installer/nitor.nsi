; Nitor — інсталятор для Windows (Nitor-Setup.exe).
;
; Збирається під час релізу (.github/workflows/release.yml):
;   makensis -DVERSION=1.21.0 -DSRC=<тека з файлами програми> installer/nitor.nsi
;
; Інсталятор містить усю програму. Він розпаковує її в тимчасову теку й відкриває вікно встановлення
; (installer/setup-gui.ps1), яке у фоні запускає install.ps1: той знаходить або встановлює Python,
; копіює програму в %LOCALAPPDATA%\Nitor (налаштування зберігаються), ставить залежності й
; створює вибрані ярлики. Консоль не показується. Права адміністратора не потрібні.
;
; Uninstall.exe так само відкриває вікно видалення (installer/uninstall-gui.ps1): лише програма або
; програма разом із вибраними даними. Uninstall.exe /S — тихе повне видалення без вікна.

Unicode true
SetCompressor /SOLID lzma

!ifndef VERSION
  !define VERSION "0.0.0"
!endif
!ifndef SRC
  !define SRC ".."
!endif
!ifndef OUTFILE
  !define OUTFILE "Nitor-Setup.exe"
!endif

!define APP "Nitor"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Nitor"

Name "${APP}"
Caption "${APP} ${VERSION} — встановлення"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Nitor"
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

; Власних сторінок у інсталятора немає: він мовчки розпаковує програму й відкриває вікно
; встановлення в стилі Nitor (installer/setup-gui.ps1). Видалення теж має своє вікно
; (installer/uninstall-gui.ps1, див. un.onInit); сторінка NSIS лишається тільки для тихого режиму /S.
SilentInstall silent

!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Ukrainian"

; 64-бітний PowerShell на 64-бітній Windows (інсталятор 32-бітний) — у $1
!macro FindPowerShell
  StrCpy $1 "$WINDIR\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
  ${IfNot} ${FileExists} "$1"
    StrCpy $1 "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe"
  ${EndIf}
!macroend

Section "Nitor"
  InitPluginsDir
  SetOutPath "$PLUGINSDIR\app"
  File /r /x ".git" /x "__pycache__" /x ".venv" /x "installer" "${SRC}\*.*"
  SetOutPath "$PLUGINSDIR\app\installer"
  File "${SRC}\installer\setup-gui.ps1"
  File "${SRC}\installer\ui-common.ps1"

  !insertmacro FindPowerShell
  ; nsExec — без вікна консолі; вікно встановлення показує сам setup-gui.ps1
  nsExec::Exec '"$1" -NoProfile -STA -ExecutionPolicy Bypass -File "$PLUGINSDIR\app\installer\setup-gui.ps1" -Source "$PLUGINSDIR\app" -Version "${VERSION}"'
  Pop $0
  SetOutPath "$TEMP"
  RMDir /r "$PLUGINSDIR\app"
  ${If} $0 == 3
  ${OrIf} $0 == "error"
    MessageBox MB_ICONSTOP "Не вдалося відкрити вікно встановлення Nitor.$\r$\nПодробиці — у файлі %TEMP%\Nitor-install.log"
    Abort
  ${EndIf}
  ${If} $0 != 0
    Abort   ; встановлення скасовано або не вдалося — вікно вже про це сказало
  ${EndIf}

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${APP}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "${APP}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\dmxctl\static\icon.ico"
  WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegStr HKCU "${UNINST_KEY}" "URLInfoAbout" "https://github.com/Navascar/Nitor"
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
SectionEnd

; Вікно видалення. Uninstall.exe уже працює з копії в %TEMP%, тож тека програми не зайнята.
; Вікно саме видаляє ярлики й файли (дані — за вибором), тут лишається прибрати запис у
; «Програми та компоненти». Код вікна: 0 — видалено, 1 — скасовано, 3 — вікно не відкрилося.
Function un.onInit
  ${If} ${Silent}
    Return   ; /S — розділ Uninstall нижче: повне видалення без запитань
  ${EndIf}
  InitPluginsDir
  SetOutPath "$PLUGINSDIR\ui"
  File "${SRC}\installer\uninstall-gui.ps1"
  File "${SRC}\installer\ui-common.ps1"
  File "${SRC}\dmxctl\static\icon.ico"
  !insertmacro FindPowerShell
  nsExec::Exec '"$1" -NoProfile -STA -ExecutionPolicy Bypass -File "$PLUGINSDIR\ui\uninstall-gui.ps1" -AppDir "$INSTDIR" -Version "${VERSION}" -Icon "$PLUGINSDIR\ui\icon.ico"'
  Pop $0
  SetOutPath "$TEMP"
  ${If} $0 == 0
    DeleteRegKey HKCU "${UNINST_KEY}"
    SetErrorLevel 0
    Quit
  ${EndIf}
  ${If} $0 == 3
  ${OrIf} $0 == "error"
    ; вікно не відкрилося — запитуємо звичайним повідомленням і видаляємо все, як раніше
    MessageBox MB_YESNO|MB_ICONQUESTION "Видалити Nitor разом із налаштуваннями, приладами й сценами?$\r$\nЩоб зберегти сцени, спершу збережіть їх у файли (меню сцени → «Зберегти у файл…»)." IDYES +2
    Quit
    SetSilent silent   ; далі — розділ Uninstall без сторінок
    Return
  ${EndIf}
  SetErrorLevel 1   ; видалення скасовано
  Quit
FunctionEnd

Section "Uninstall"
  ; програма має бути закрита, інакше файли зайняті
  ; процеси Python з dmxctl / nitor.pyw (порт не годиться: Nitor може працювати на 8081+);
  ; сам PowerShell теж містить «dmxctl» у рядку команди, тому дивимося лише на python*.exe
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "try { if (Get-CimInstance Win32_Process | Where-Object { $$_.Name -like $\'python*$\' -and $$_.CommandLine -match $\'dmxctl|nitor\.pyw|sc-dmx\.pyw$\' }) { exit 1 } } catch { }; exit 0"'
  Pop $0
  Pop $1   ; вивід команди — не потрібен
  ${If} $0 == 1
    MessageBox MB_ICONEXCLAMATION "Nitor зараз відкрито. Закрийте вікно програми й запустіть видалення ще раз." /SD IDOK
    Abort
  ${EndIf}
  Delete "$DESKTOP\Nitor.lnk"
  Delete "$SMPROGRAMS\Nitor.lnk"
  SetOutPath "$TEMP"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${UNINST_KEY}"
SectionEnd
