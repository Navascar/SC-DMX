# Nitor — інсталятор для Windows.
#
# Найпростіше: Nitor-Setup.exe зі сторінки релізів (показує вікно встановлення й сам запускає цей скрипт).
# Запуск з розпакованого архіву:  install.bat
# Або одним рядком у PowerShell (завантажить останню версію з GitHub):
#   $s = irm https://raw.githubusercontent.com/Navascar/Nitor/main/install.ps1; iex $s.TrimStart([char]0xFEFF)
#
# Що робить: копіює програму в %LOCALAPPDATA%\Nitor, створює окреме середовище Python (.venv),
# встановлює залежності, створює ярлики «Nitor» на робочому столі та в меню «Пуск» і запускає програму.
# Повторний запуск безпечний: налаштування (config.json) зберігаються.
#
# -NoLaunch     — не запускати програму наприкінці.
# -NoDesktop    — без ярлика на робочому столі.
# -NoStartMenu  — без ярлика в меню «Пуск».
# -Progress     — режим для вікна встановлення (installer/setup-gui.ps1): без запитань і консолі,
#                 хід встановлення — рядками @@STEP|крок|текст, @@LOG|текст, @@ERROR|текст, @@DONE.

param([switch]$NoLaunch, [switch]$Progress, [switch]$NoDesktop, [switch]$NoStartMenu)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# Python пише в канал у системному кодуванні (cp1251), а ми читаємо UTF-8 — шлях до Python з кириличним
# іменем користувача (C:\Users\Дмитро\...) псувався, і Python «не знаходився». Просимо Python писати UTF-8.
$env:PYTHONIOENCODING = 'utf-8'
$Repo = 'Navascar/Nitor'
$AppDir = Join-Path $env:LOCALAPPDATA 'Nitor'

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
            # найновіший Python 3.10+: Python313 > Python39 — порівнюємо як числа, а не як текст
            $cand = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
                Where-Object { [int]($_.Directory.Name -replace '\D', '') -ge 310 } |
                Sort-Object { [int]($_.Directory.Name -replace '\D', '') } -Descending | Select-Object -First 1
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
    $rel = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ 'User-Agent' = 'Nitor-installer' }
    $asset = $rel.assets | Where-Object { $_.name -eq 'Nitor.zip' } | Select-Object -First 1
    $url = if ($asset) { $asset.browser_download_url } else { $rel.zipball_url }
    Log "Версія $($rel.tag_name)"
    $Tmp = Join-Path $env:TEMP ("nitor-" + [guid]::NewGuid())
    New-Item -ItemType Directory $Tmp | Out-Null
    $zip = Join-Path $Tmp 'Nitor.zip'
    Invoke-WebRequest $url -OutFile $zip -UseBasicParsing -Headers @{ 'User-Agent' = 'Nitor-installer' }
    Expand-Archive $zip -DestinationPath (Join-Path $Tmp 'x')
    $Src = (Get-ChildItem (Join-Path $Tmp 'x') -Recurse -Filter '__init__.py' |
            Where-Object { $_.Directory.Name -eq 'dmxctl' } | Select-Object -First 1).Directory.Parent.FullName
    if (-not $Src) { Fail 'В архіві немає програми.' }
}

# Якщо програма запущена — її треба закрити, щоб оновити файли
# Запущена Nitor — її процеси (python/pythonw з dmxctl, nitor.pyw або sc-dmx.pyw — версії до перейменування).
# Порт не годиться: якщо 8080 зайнятий іншим застосунком, Nitor працює на 8081…8099.
$running = $false
try {
    $running = [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction Stop |
        Where-Object { $_.CommandLine -match 'dmxctl|nitor\.pyw|sc-dmx\.pyw' })
} catch { }
if ($running) {
    if ($Progress) { Fail 'Nitor зараз відкрито. Закрийте вікно програми й спробуйте ще раз.' }
    Write-Host 'Nitor зараз відкрито. Закрийте вікно програми й натисніть Enter.' -ForegroundColor Yellow
    Read-Host | Out-Null
}

# ------------------------------------------------------- перейменування ---
# Раніше програма називалася SC DMX і жила в %LOCALAPPDATA%\SC-DMX. Налаштування (сцени, прилади)
# переносимо в нову теку, а стару копію з її ярликами й записом у «Програмах» прибираємо.
$OldDir = Join-Path $env:LOCALAPPDATA 'SC-DMX'
if (Test-Path -LiteralPath $OldDir) {
    New-Item -ItemType Directory -Force $AppDir | Out-Null
    $oldCfg = Join-Path $OldDir 'config.json'
    if ((Test-Path -LiteralPath $oldCfg) -and -not (Test-Path (Join-Path $AppDir 'config.json'))) {
        Copy-Item -LiteralPath $oldCfg $AppDir
        Log 'Налаштування перенесено з теки SC-DMX'
    }
    foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
        Remove-Item -LiteralPath (Join-Path $d 'SC DMX.lnk') -ErrorAction SilentlyContinue
    }
    Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\SC-DMX' -Recurse -ErrorAction SilentlyContinue
    # стару теку не видаляємо, якщо встановлення запущене саме з неї (install.bat у теці SC-DMX)
    $srcFull = (Resolve-Path $Src).Path.TrimEnd('\')
    if ($srcFull -ne $OldDir -and -not $srcFull.StartsWith($OldDir + '\', [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $OldDir -Recurse -Force -ErrorAction SilentlyContinue
        Log 'Стару теку SC-DMX видалено'
    }
}

# ------------------------------------------------------------- копіювання ---
Log "Тека програми: $AppDir"
New-Item -ItemType Directory -Force $AppDir | Out-Null
if ((Resolve-Path $Src).Path.TrimEnd('\') -ne (Resolve-Path $AppDir).Path.TrimEnd('\')) {
    $keep = @('config.json', '.venv', 'nitor.log', '.git', 'Uninstall.exe')
    Get-ChildItem $AppDir -Force | Where-Object { $keep -notcontains $_.Name } | Remove-Item -Recurse -Force
    Get-ChildItem $Src -Force | Where-Object { @('.venv', '.git', 'nitor.log', 'installer') -notcontains $_.Name } | ForEach-Object {
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
# Ярлики з ідентифікатором застосунку: на панелі задач — «Nitor» з іконкою програми, а не «Python»
$LinkDirs = @()
if (-not $NoDesktop) { $LinkDirs += [Environment]::GetFolderPath('Desktop') }
if (-not $NoStartMenu) { $LinkDirs += [Environment]::GetFolderPath('Programs') }
# ярлик, який цього разу не вибрали, прибираємо (лишився від попереднього встановлення)
if ($NoDesktop) { Remove-Item (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Nitor.lnk') -ErrorAction SilentlyContinue }
if ($NoStartMenu) { Remove-Item (Join-Path ([Environment]::GetFolderPath('Programs')) 'Nitor.lnk') -ErrorAction SilentlyContinue }
if ($LinkDirs.Count) {
    Step 'shortcuts' 'Створення ярликів'
    $linkArgs = @('-m', 'dmxctl.winshell', 'install')
    if ($NoDesktop) { $linkArgs += '--no-desktop' }
    if ($NoStartMenu) { $linkArgs += '--no-start-menu' }
    Push-Location $AppDir
    $code = Run $VenvPy $linkArgs
    Pop-Location
    if ($code -ne 0) {
        Log 'Ярлики — запасним способом'
        $shell = New-Object -ComObject WScript.Shell
        foreach ($dir in $LinkDirs) {
            $lnk = $shell.CreateShortcut((Join-Path $dir 'Nitor.lnk'))
            $lnk.TargetPath = $Pyw
            $lnk.Arguments = '"' + (Join-Path $AppDir 'nitor.pyw') + '"'
            $lnk.WorkingDirectory = $AppDir
            $lnk.IconLocation = Join-Path $AppDir 'dmxctl\static\icon.ico'
            $lnk.Description = 'Nitor — керування RGB-прожекторами'
            $lnk.Save()
        }
    }
}

if ($Progress) { Emit '@@DONE'; exit 0 }
if ($NoLaunch) {
    Step 'done' 'Готово!'
    exit 0
}
Step 'done' 'Готово! Запускаю Nitor'
Start-Process -FilePath $Pyw -ArgumentList ('"' + (Join-Path $AppDir 'nitor.pyw') + '"') -WorkingDirectory $AppDir
if ($Host.Name -eq 'ConsoleHost' -and $PSScriptRoot) { Start-Sleep -Seconds 4 }
