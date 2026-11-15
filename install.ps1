# SC DMX — інсталятор для Windows.
#
# Найпростіше: SC-DMX-Setup.exe зі сторінки релізів (показує вікно встановлення й сам запускає цей скрипт).
# Запуск з розпакованого архіву:  install.bat
# Або одним рядком у PowerShell (завантажить останню версію з GitHub):
#   $s = irm https://raw.githubusercontent.com/Navascar/SC-DMX/main/install.ps1; iex $s.TrimStart([char]0xFEFF)
#
# Що робить: копіює програму в %LOCALAPPDATA%\SC-DMX, створює окреме середовище Python (.venv),
# встановлює залежності, створює ярлики «SC DMX» на робочому столі та в меню «Пуск» і запускає програму.
# Повторний запуск безпечний: налаштування (config.json) зберігаються.
#
# -NoLaunch  — не запускати програму наприкінці.
# -Progress  — режим для вікна встановлення (installer/setup-gui.ps1): без запитань і консолі,
#              хід встановлення — рядками @@STEP|крок|текст, @@LOG|текст, @@ERROR|текст, @@DONE.

param([switch]$NoLaunch, [switch]$Progress)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Repo = 'Navascar/SC-DMX'
$AppDir = Join-Path $env:LOCALAPPDATA 'SC-DMX'

function Emit($line) { [Console]::Out.WriteLine($line); [Console]::Out.Flush() }
function Step($id, $text) {
    if ($Progress) { Emit "@@STEP|$id|$text" } else { Write-Host "`n==> $text" -ForegroundColor Cyan }
}
function Log($text) {
    $text = "$text".TrimEnd()
    if (-not $text) { return }
    if ($Progress) { Emit ("@@LOG|" + ($text -replace '[\r\n]+', ' ')) } else { Write-Host "  $text" }
}
function Fail($text) {
    if ($Progress) { Emit "@@ERROR|$text"; exit 1 }
    Write-Host "`nПОМИЛКА: $text" -ForegroundColor Red
    if ($Host.Name -eq 'ConsoleHost') { Read-Host 'Натисніть Enter, щоб закрити' | Out-Null }
    exit 1
}
# Зовнішня програма (pip, winget…): її вивід — у журнал, повідомлення в stderr не зупиняють скрипт
function Run($exe, [string[]]$arguments) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $exe @arguments 2>&1 | ForEach-Object { Log ([string]$_) } } finally { $ErrorActionPreference = $old }
    return $LASTEXITCODE
}
trap { Fail "$($_.Exception.Message)" }

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

Step 'python' 'Пошук Python 3.10+'
$Python = Find-Python
if (-not $Python) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Step 'python' 'Встановлення Python'
        $null = Run 'winget' @('install', '-e', '--id', 'Python.Python.3.13', '--scope', 'user', '--silent',
                               '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity')
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
        $Python = Find-Python
        if (-not $Python) {
            $cand = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue | Select-Object -Last 1
            if ($cand) { $Python = $cand.FullName }
        }
    }
    if (-not $Python) {
        if (-not $Progress) { Start-Process 'https://www.python.org/downloads/' }
        Fail 'Python 3.10+ не знайдено. Встановіть його з python.org і запустіть встановлення знову.'
    }
}
Log "Python: $Python"

# ------------------------------------------------------------- джерело ----
$Src = $null
$Tmp = $null
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot 'dmxctl\__init__.py'))) {
    $Src = $PSScriptRoot
    Step 'files' 'Копіювання програми'
} else {
    Step 'files' 'Завантаження останньої версії з GitHub'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $rel = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ 'User-Agent' = 'SC-DMX-installer' }
    $asset = $rel.assets | Where-Object { $_.name -eq 'SC-DMX.zip' } | Select-Object -First 1
    $url = if ($asset) { $asset.browser_download_url } else { $rel.zipball_url }
    Log "Версія $($rel.tag_name)"
    $Tmp = Join-Path $env:TEMP ("sc-dmx-" + [guid]::NewGuid())
    New-Item -ItemType Directory $Tmp | Out-Null
    $zip = Join-Path $Tmp 'SC-DMX.zip'
    Invoke-WebRequest $url -OutFile $zip -UseBasicParsing -Headers @{ 'User-Agent' = 'SC-DMX-installer' }
    Expand-Archive $zip -DestinationPath (Join-Path $Tmp 'x')
    $Src = (Get-ChildItem (Join-Path $Tmp 'x') -Recurse -Filter '__init__.py' |
            Where-Object { $_.Directory.Name -eq 'dmxctl' } | Select-Object -First 1).Directory.Parent.FullName
    if (-not $Src) { Fail 'В архіві немає програми.' }
}

# Якщо програма запущена — її треба закрити, щоб оновити файли
$running = $false
# інший застосунок на порту 8080 — не SC DMX: він встановленню не заважає
try { $running = (Invoke-WebRequest 'http://127.0.0.1:8080/' -UseBasicParsing -TimeoutSec 2).Content -match '<title>SC DMX</title>' } catch { }
if ($running) {
    if ($Progress) { Fail 'SC DMX зараз відкрито. Закрийте вікно програми й спробуйте ще раз.' }
    Write-Host 'SC DMX зараз відкрито. Закрийте вікно програми й натисніть Enter.' -ForegroundColor Yellow
    Read-Host | Out-Null
}

# ------------------------------------------------------------- копіювання ---
Log "Тека програми: $AppDir"
New-Item -ItemType Directory -Force $AppDir | Out-Null
if ((Resolve-Path $Src).Path.TrimEnd('\') -ne (Resolve-Path $AppDir).Path.TrimEnd('\')) {
    $keep = @('config.json', '.venv', 'sc-dmx.log', '.git', 'Uninstall.exe')
    Get-ChildItem $AppDir -Force | Where-Object { $keep -notcontains $_.Name } | Remove-Item -Recurse -Force
    Get-ChildItem $Src -Force | Where-Object { @('.venv', '.git', 'sc-dmx.log', 'installer') -notcontains $_.Name } | ForEach-Object {
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
$Pyw = Join-Path $AppDir '.venv\Scripts\pythonw.exe'
Step 'venv' 'Середовище Python'
if (-not (Test-Path $VenvPy)) {
    if ((Run $Python @('-m', 'venv', (Join-Path $AppDir '.venv'))) -ne 0) { Fail 'Не вдалося створити середовище Python.' }
}
Step 'deps' 'Встановлення компонентів'
$null = Run $VenvPy @('-m', 'pip', 'install', '--disable-pip-version-check', '--progress-bar', 'off', '-q', '--upgrade', 'pip')
$code = Run $VenvPy @('-m', 'pip', 'install', '--disable-pip-version-check', '--progress-bar', 'off',
                      '-r', (Join-Path $AppDir 'requirements.txt'))
if ($code -ne 0) { Fail 'Не вдалося встановити компоненти. Перевірте інтернет і спробуйте ще раз.' }

# --------------------------------------------------------------- ярлики ---
# Ярлики з ідентифікатором застосунку: на панелі задач — «SC DMX» з іконкою програми, а не «Python»
Step 'shortcuts' 'Створення ярликів'
Push-Location $AppDir
$code = Run $VenvPy @('-m', 'dmxctl.winshell', 'install')
Pop-Location
if ($code -ne 0) {
    Log 'Ярлики — запасним способом'
    $shell = New-Object -ComObject WScript.Shell
    foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
        $lnk = $shell.CreateShortcut((Join-Path $dir 'SC DMX.lnk'))
        $lnk.TargetPath = $Pyw
        $lnk.Arguments = '"' + (Join-Path $AppDir 'sc-dmx.pyw') + '"'
        $lnk.WorkingDirectory = $AppDir
        $lnk.IconLocation = Join-Path $AppDir 'dmxctl\static\icon.ico'
        $lnk.Description = 'SC DMX — керування RGB-прожекторами'
        $lnk.Save()
    }
}

if ($Progress) { Emit '@@DONE'; exit 0 }
if ($NoLaunch) {
    Step 'done' 'Готово!'
    exit 0
}
Step 'done' 'Готово! Запускаю SC DMX'
Start-Process -FilePath $Pyw -ArgumentList ('"' + (Join-Path $AppDir 'sc-dmx.pyw') + '"') -WorkingDirectory $AppDir
if ($Host.Name -eq 'ConsoleHost' -and $PSScriptRoot) { Start-Sleep -Seconds 4 }
