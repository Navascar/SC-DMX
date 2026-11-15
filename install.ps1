# SC DMX — інсталятор для Windows.
#
# Найпростіше: SC-DMX-Setup.exe зі сторінки релізів (він сам запускає цей скрипт).
# Запуск з розпакованого архіву:  install.bat
# Або одним рядком у PowerShell (завантажить останню версію з GitHub):
#   $s = irm https://raw.githubusercontent.com/Navascar/SC-DMX/main/install.ps1; iex $s.TrimStart([char]0xFEFF)
#
# Що робить: копіює програму в %LOCALAPPDATA%\SC-DMX, створює окреме середовище Python (.venv),
# встановлює залежності, створює ярлики «SC DMX» на робочому столі та в меню «Пуск» і запускає програму.
# Повторний запуск безпечний: налаштування (config.json) зберігаються.
#
# -NoLaunch — не запускати програму наприкінці (так робить SC-DMX-Setup.exe: запуск — з його останньої сторінки).

param([switch]$NoLaunch)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Repo = 'Navascar/SC-DMX'
$AppDir = Join-Path $env:LOCALAPPDATA 'SC-DMX'

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Fail($text) {
    Write-Host "`nПОМИЛКА: $text" -ForegroundColor Red
    if ($Host.Name -eq 'ConsoleHost') { Read-Host 'Натисніть Enter, щоб закрити' | Out-Null }
    exit 1
}

# ---------------------------------------------------------------- Python ---
function Find-Python {
    foreach ($cmd in @('py', 'python', 'python3')) {
        try {
            $exe = & $cmd -c "import sys; print(sys.executable if sys.version_info >= (3, 10) else '')" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path $exe)) { return $exe.Trim() }
        } catch { }
    }
    return $null
}

Step 'Пошук Python 3.10+'
$Python = Find-Python
if (-not $Python) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host 'Python не знайдено — встановлюю через winget...'
        winget install -e --id Python.Python.3.13 --scope user --accept-package-agreements --accept-source-agreements
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
        $Python = Find-Python
        if (-not $Python) {
            $cand = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue | Select-Object -Last 1
            if ($cand) { $Python = $cand.FullName }
        }
    }
    if (-not $Python) {
        Start-Process 'https://www.python.org/downloads/'
        Fail 'Python 3.10+ не знайдено. Встановіть його з python.org (позначте "Add python.exe to PATH") і запустіть інсталятор знову.'
    }
}
Write-Host "Python: $Python"

# ------------------------------------------------------------- джерело ----
$Src = $null
$Tmp = $null
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot 'dmxctl\__init__.py'))) {
    $Src = $PSScriptRoot
    Step "Встановлення з теки $Src"
} else {
    Step 'Завантаження останньої версії з GitHub'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $rel = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ 'User-Agent' = 'SC-DMX-installer' }
    $asset = $rel.assets | Where-Object { $_.name -eq 'SC-DMX.zip' } | Select-Object -First 1
    $url = if ($asset) { $asset.browser_download_url } else { $rel.zipball_url }
    Write-Host "Версія $($rel.tag_name)"
    $Tmp = Join-Path $env:TEMP ("sc-dmx-" + [guid]::NewGuid())
    New-Item -ItemType Directory $Tmp | Out-Null
    $zip = Join-Path $Tmp 'SC-DMX.zip'
    Invoke-WebRequest $url -OutFile $zip -UseBasicParsing -Headers @{ 'User-Agent' = 'SC-DMX-installer' }
    Expand-Archive $zip -DestinationPath (Join-Path $Tmp 'x')
    $Src = (Get-ChildItem (Join-Path $Tmp 'x') -Recurse -Filter '__init__.py' |
            Where-Object { $_.Directory.Name -eq 'dmxctl' } | Select-Object -First 1).Directory.Parent.FullName
    if (-not $Src) { Fail 'В архіві немає програми.' }
}

# Якщо програма запущена — просимо її вимкнутися, щоб оновити файли
try {
    $null = Invoke-WebRequest 'http://127.0.0.1:8080/' -UseBasicParsing -TimeoutSec 2
    Write-Host 'SC DMX зараз відкрито. Закрийте вікно програми й натисніть Enter.' -ForegroundColor Yellow
    Read-Host | Out-Null
} catch { }

# ------------------------------------------------------------- копіювання ---
Step "Копіювання в $AppDir"
New-Item -ItemType Directory -Force $AppDir | Out-Null
if ((Resolve-Path $Src).Path.TrimEnd('\') -ne (Resolve-Path $AppDir).Path.TrimEnd('\')) {
    $keep = @('config.json', '.venv', 'sc-dmx.log', '.git', 'Uninstall.exe')
    Get-ChildItem $AppDir -Force | Where-Object { $keep -notcontains $_.Name } | Remove-Item -Recurse -Force
    Get-ChildItem $Src -Force | Where-Object { @('.venv', '.git', 'sc-dmx.log') -notcontains $_.Name } | ForEach-Object {
        if ($_.Name -eq 'config.json') {
            # налаштування зі старої теки переносимо лише якщо нових ще немає
            if (-not (Test-Path (Join-Path $AppDir 'config.json'))) { Copy-Item $_.FullName $AppDir }
        } else {
            Copy-Item $_.FullName $AppDir -Recurse -Force
        }
    }
}
if ($Tmp) { Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue }

# ---------------------------------------------------------- середовище ----
$VenvPy = Join-Path $AppDir '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPy)) {
    Step 'Створення середовища Python'
    & $Python -m venv (Join-Path $AppDir '.venv')
    if ($LASTEXITCODE -ne 0) { Fail 'не вдалося створити віртуальне середовище' }
}
Step 'Встановлення залежностей (вперше — близько 250 МБ: вбудоване вікно програми)'
& $VenvPy -m pip install --disable-pip-version-check -q --upgrade pip
& $VenvPy -m pip install --disable-pip-version-check -r (Join-Path $AppDir 'requirements.txt')
if ($LASTEXITCODE -ne 0) { Fail 'не вдалося встановити залежності (див. текст вище)' }

# --------------------------------------------------------------- ярлики ---
Step 'Створення ярликів'
$Pyw = Join-Path $AppDir '.venv\Scripts\pythonw.exe'
$Icon = Join-Path $AppDir 'dmxctl\static\icon.ico'
$shell = New-Object -ComObject WScript.Shell
$places = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path ([Environment]::GetFolderPath('Programs')) '')
)
foreach ($dir in $places) {
    $lnk = $shell.CreateShortcut((Join-Path $dir 'SC DMX.lnk'))
    $lnk.TargetPath = $Pyw
    $lnk.Arguments = '-m dmxctl --open'
    $lnk.WorkingDirectory = $AppDir
    $lnk.IconLocation = $Icon
    $lnk.Description = 'SC DMX — керування RGB-прожекторами'
    $lnk.Save()
}

# ---------------------------------------------------------- перевірка uDMX ---
Step 'Перевірка uDMX'
Push-Location $AppDir
& $VenvPy -m dmxctl --check
$udmxOk = ($LASTEXITCODE -eq 0)
Pop-Location
if (-not $udmxOk) {
    Write-Host @'

uDMX поки не працює. Якщо адаптер підключено, встановіть драйвер WinUSB:
  1. Завантажте Zadig: https://zadig.akeo.ie
  2. Options -> List All Devices, виберіть "uDMX" (16C0 05DC)
  3. Драйвер WinUSB -> Install / Replace Driver
Програма сама підхопить адаптер, перезапускати не треба.
'@ -ForegroundColor Yellow
}

if ($NoLaunch) {
    Step 'Готово!'
    exit 0
}
Step 'Готово! Запускаю SC DMX'
Write-Host 'Надалі запускайте програму ярликом «SC DMX» на робочому столі. Оновлення програма пропонує сама.'
Start-Process -FilePath $Pyw -ArgumentList '-m dmxctl --open' -WorkingDirectory $AppDir
if ($Host.Name -eq 'ConsoleHost' -and $PSScriptRoot) { Start-Sleep -Seconds 4 }
