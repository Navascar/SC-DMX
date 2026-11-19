# Nitor — вікно встановлення (запускає Nitor-Setup.exe, без консолі).
#
# Вікно в стилі програми (темне, кольори й шрифт — як в інтерфейсі; спільне з вікном видалення —
# у ui-common.ps1). Перед встановленням можна вибрати ярлики: на робочому столі й у меню «Пуск».
# Саме встановлення робить install.ps1 -Progress у фоновому процесі без вікна, а сюди передає хід
# рядками @@STEP/@@LOG/...
#
# Код виходу: 0 — програму встановлено, 1 — ні (скасовано або помилка встановлення),
# 3 — саме вікно не вдалося відкрити (тоді Nitor-Setup.exe показує повідомлення з журналом).
# Для перевірки в CI: NITOR_SETUP_AUTOTEST=1 — встановлення починається само, вікно закривається саме,
# а знімки вікна зберігаються в теку NITOR_SETUP_SHOTS. NITOR_SETUP_LINKS — які ярлики створити
# в автоперевірці: «desktop,start» (типово), «start», «none»…

param([string]$Source = (Split-Path $PSScriptRoot), [string]$Version = '')

$ErrorActionPreference = 'Stop'
$LogPath = Join-Path $env:TEMP 'Nitor-install.log'
$AutoTest = $env:NITOR_SETUP_AUTOTEST -eq '1'
$Shots = $env:NITOR_SETUP_SHOTS
$script:Installed = $false

try {
    . (Join-Path $PSScriptRoot 'ui-common.ps1')
    Set-Content -LiteralPath $LogPath -Value "Nitor $Version — встановлення" -Encoding UTF8
    Initialize-NitorUi 'Nitor.Setup'
} catch {
    try { Add-Content -LiteralPath $LogPath -Value "Не вдалося підготувати вікно: $_" -Encoding UTF8 } catch { }
    exit 3
}

# ------------------------------------------------------------------- вигляд ---
$Body = @'
      <StackPanel Grid.Row="1" Margin="24,18,24,0">
        <TextBlock x:Name="Heading" FontSize="20" FontWeight="SemiBold" Text="Встановлення Nitor"/>
        <TextBlock x:Name="Sub" Foreground="{StaticResource Muted}" FontSize="12" Margin="0,6,0,0" TextWrapping="Wrap"
                   Text="Потрібне підключення до інтернету."/>
        <StackPanel x:Name="Options" Margin="0,20,0,0">
          <CheckBox x:Name="DesktopBox" Style="{StaticResource Check}" IsChecked="True" Content="Створити ярлик на робочому столі"/>
          <CheckBox x:Name="StartBox" Style="{StaticResource Check}" IsChecked="True" Margin="0,12,0,0" Content="Додати ярлик у меню «Пуск»"/>
        </StackPanel>
        <StackPanel x:Name="Progress" Visibility="Collapsed">
          <StackPanel x:Name="Steps" Margin="0,18,0,0"/>
          <ProgressBar x:Name="Bar" Minimum="0" Maximum="100" Value="0" Margin="0,14,0,0"/>
          <TextBlock x:Name="Status" Foreground="{StaticResource Muted}" FontSize="11" Margin="0,8,0,0"
                     FontFamily="Cascadia Mono, Consolas" TextTrimming="CharacterEllipsis" Text=" "/>
        </StackPanel>
        <Border x:Name="Note" Visibility="Collapsed" Margin="0,14,0,0" Padding="12,10" CornerRadius="10" BorderThickness="1">
          <TextBlock x:Name="NoteText" TextWrapping="Wrap" FontSize="12"/>
        </Border>
      </StackPanel>
'@

try {
    $win = New-NitorWindow 'Встановлення Nitor' $Body 'Встановити'
} catch {
    Write-Log "Не вдалося створити вікно: $_"
    exit 3
}
Set-WindowIcon (Join-Path $Source 'dmxctl\static\icon.ico')
if ($Version) { $ui.VersionText.Text = $Version }

if ($AutoTest -and $env:NITOR_SETUP_LINKS) {
    $ui.DesktopBox.IsChecked = $env:NITOR_SETUP_LINKS -match 'desktop'
    $ui.StartBox.IsChecked = $env:NITOR_SETUP_LINKS -match 'start'
}

# ------------------------------------------------------------------- кроки ---
# id, назва, частка смуги прогресу на початку кроку
New-Steps $ui.Steps @(
    @('python', 'Python', 2),
    @('files', 'Файли програми', 10),
    @('venv', 'Середовище Python', 18),
    @('deps', 'Компоненти', 26),
    @('shortcuts', 'Ярлики', 92)
)

# --------------------------------------------------------------- встановлення ---
$script:Proc = $null
$script:OutTask = $null
$script:ErrTask = $null
$script:CurStep = $null
$script:DepLines = 0
$script:Failed = $false
$script:Done = $false

function Show-RunningNote {
    Show-Note 'Nitor відкрито. Її буде закрито, прожектори згаснуть.' 'warn'
    $ui.MainBtn.Content = 'Закрити Nitor і встановити'
    $script:CloseMode = $true
}

function Handle-Line($line) {
    $line = "$line".TrimStart([char]0xFEFF)
    Write-Log $line
    if (-not $line.StartsWith('@@')) { if ($line.Trim()) { $ui.Status.Text = $line.Trim() }; return }
    $parts = $line.Substring(2).Split('|', 3)
    switch ($parts[0]) {
        'STEP' { Enter-Step $parts[1]; $ui.Status.Text = $parts[2] }
        'LOG' {
            $ui.Status.Text = $parts[1]
            if ($script:CurStep -eq 'deps') {
                # pip не повідомляє загальний відсоток: смуга повільно наближається до кінця кроку
                if ($parts[1] -match '^(Collecting|Downloading|Using cached|Installing collected)') { $script:DepLines++ }
                $ui.Bar.Value = [Math]::Max($ui.Bar.Value, 26 + 60 * (1 - [Math]::Exp(-$script:DepLines / 14)))
            }
        }
        'ERROR' {
            $script:Failed = $true
            if ($script:CurStep) { Set-StepState $script:CurStep 'error' }
            Show-Note $parts[1] 'error'
        }
        'DONE' { $script:Done = $true }
    }
}

function Start-Install {
    if (App-Running) {
        if (-not $script:CloseMode -and -not $AutoTest) { Show-RunningNote; return }
        Save-Shot '0-running'
        if (-not (Close-App)) {
            Show-Note 'Не вдалося закрити Nitor. Закрийте її вручну.' 'error'
            $ui.MainBtn.Content = 'Встановити'
            $script:CloseMode = $false
            return
        }
    }
    $script:CloseMode = $false
    $ui.Note.Visibility = 'Collapsed'
    # вибір ярликів — лише до першої спроби; повторна спроба бере той самий вибір
    $ui.Options.Visibility = 'Collapsed'
    $ui.Progress.Visibility = 'Visible'
    $desktop = [bool]$ui.DesktopBox.IsChecked
    $start = [bool]$ui.StartBox.IsChecked
    if (-not $desktop -and -not $start) { $StepUi['shortcuts'].Row.Visibility = 'Collapsed' }
    foreach ($id in $Order) { Set-StepState $id 'wait' }
    $script:Failed = $false; $script:Done = $false; $script:DepLines = 0; $script:CurStep = $null
    $ui.Bar.Value = 0
    $ui.Heading.Text = 'Встановлення…'
    $ui.Sub.Text = 'Це може тривати кілька хвилин.'
    $ui.MainBtn.Visibility = 'Collapsed'
    $ui.SecondBtn.Content = 'Скасувати'
    $ui.LogBtn.Visibility = 'Visible'

    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = (Get-Process -Id $PID).Path
    $psi.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $Source 'install.ps1') + '" -Progress -NoLaunch'
    if (-not $desktop) { $psi.Arguments += ' -NoDesktop' }
    if (-not $start) { $psi.Arguments += ' -NoStartMenu' }
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [Text.Encoding]::UTF8
    $psi.WorkingDirectory = $Source
    Write-Log "Запуск: $($psi.FileName) $($psi.Arguments)"
    $script:Proc = [Diagnostics.Process]::Start($psi)
    $script:OutTask = $script:Proc.StandardOutput.ReadLineAsync()
    $script:ErrTask = $script:Proc.StandardError.ReadLineAsync()
    $timer.Start()
}

function Finish-Install {
    $timer.Stop()
    $code = $script:Proc.ExitCode
    Write-Log "Завершено з кодом $code"
    $ui.SecondBtn.Visibility = 'Visible'
    if ($code -eq 0 -and $script:Done -and -not $script:Failed) {
        foreach ($id in $Order) {
            if (($StepUi[$id].State -in 'wait', 'active') -and $StepUi[$id].Row.Visibility -eq 'Visible') { Set-StepState $id 'done' }
        }
        $ui.Bar.Value = 100
        $script:Installed = $true
        $ui.Heading.Text = 'Nitor встановлено'
        $ui.Sub.Visibility = 'Collapsed'
        $ui.Status.Text = ' '
        $ui.MainBtn.Content = 'Запустити Nitor'
        $ui.MainBtn.Visibility = 'Visible'
        $ui.SecondBtn.Content = 'Закрити'
        Save-Shot '3-done'
    } else {
        if (-not $script:Failed) {
            if ($script:CurStep) { Set-StepState $script:CurStep 'error' }
            Show-Note 'Встановлення перервано.' 'error'
        }
        $ui.Heading.Text = 'Не вдалося встановити'
        $ui.Sub.Text = 'Перевірте інтернет і спробуйте ще раз.'
        $ui.MainBtn.Content = 'Спробувати ще раз'
        $ui.MainBtn.Visibility = 'Visible'
        $ui.SecondBtn.Content = 'Закрити'
        Save-Shot '3-error'
    }
    if ($AutoTest) { $win.Close() }
}

function Stop-Install {
    if ($script:Proc -and -not $script:Proc.HasExited) {
        Write-Log 'Скасовано користувачем'
        try { Start-Process -FilePath 'taskkill.exe' -ArgumentList "/PID $($script:Proc.Id) /T /F" -WindowStyle Hidden -Wait } catch { }
    }
}

$timer = New-Object Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromMilliseconds(80)
$timer.Add_Tick({
    try {
        while ($script:ErrTask -and $script:ErrTask.IsCompleted) {
            $l = $script:ErrTask.Result
            if ($null -eq $l) { $script:ErrTask = $null; break }
            Write-Log "stderr: $l"
            $script:ErrTask = $script:Proc.StandardError.ReadLineAsync()
        }
        while ($script:OutTask -and $script:OutTask.IsCompleted) {
            $l = $script:OutTask.Result
            if ($null -eq $l) { $script:OutTask = $null; break }
            Handle-Line $l
            $script:OutTask = $script:Proc.StandardOutput.ReadLineAsync()
        }
        if (-not $script:OutTask -and -not $script:ErrTask -and $script:Proc.HasExited) { Finish-Install }
        elseif ($AutoTest -and $script:CurStep -eq 'deps' -and -not $script:ShotDeps) { $script:ShotDeps = $true; Save-Shot '2-progress' }
    } catch {
        Write-Log "Помилка вікна: $_"
    }
})

function Launch-App {
    # через ярлик — тоді вікно одразу з ідентифікатором Nitor на панелі задач
    $lnk = @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop')) |
        ForEach-Object { Join-Path $_ 'Nitor.lnk' } | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    $app = Join-Path $env:LOCALAPPDATA 'Nitor'
    try {
        if ($lnk) { Start-Process -FilePath $lnk }
        else { Start-Process -FilePath (Join-Path $app '.venv\Scripts\pythonw.exe') -ArgumentList ('"' + (Join-Path $app 'nitor.pyw') + '"') -WorkingDirectory $app }
    } catch { Write-Log "Не вдалося запустити: $_" }
}

# ------------------------------------------------------------------- події ---
$ui.SecondBtn.Add_Click({ $win.Close() })
$ui.MainBtn.Add_Click({
    if ($script:Installed) { Launch-App; $win.Close() } else { Start-Install }
})
$win.Add_Closing({
    param($s, $e)
    if ($script:Proc -and -not $script:Proc.HasExited) {
        if ($AutoTest) { Stop-Install; return }
        $r = [Windows.MessageBox]::Show($win, 'Зупинити встановлення Nitor?', 'Nitor', 'YesNo', 'Question')
        if ($r -ne 'Yes') { $e.Cancel = $true; return }
        Stop-Install
    }
})
Register-WindowChrome {
    if ($AutoTest) {
        Save-Shot '1-welcome'
        Start-Install
    } elseif (App-Running) {
        Show-RunningNote
    }
}

try {
    [void]$win.ShowDialog()
} catch {
    Write-Log "Помилка вікна: $_"
    exit 3
}
if ($script:Installed) { exit 0 } else { exit 1 }
