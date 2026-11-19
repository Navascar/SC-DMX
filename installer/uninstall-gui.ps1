# Nitor — вікно видалення (запускає Uninstall.exe, без консолі).
#
# Вікно в стилі вікна встановлення (спільне — у ui-common.ps1). Два варіанти:
#   «Лише програму»          — файли програми й ярлики видаляються, config.json (сцени, прилади,
#                               налаштування) лишається в теці програми й підхоплюється повторним встановленням;
#   «Програму разом із даними» — розкривається список: сцени, прилади, власні профілі, статичні кольори,
#                               налаштування. Вибрані частини видаляються з config.json (dmxctl/userdata.py),
#                               усі разом — config.json видаляється повністю.
#
# Код виходу: 0 — програму видалено, 1 — ні (скасовано), 3 — вікно не вдалося відкрити
# (тоді Uninstall.exe питає звичайним повідомленням). Запис у «Програми та компоненти» прибирає Uninstall.exe.
# Для перевірки в CI: NITOR_SETUP_AUTOTEST=1 — видалення починається само, вікно закривається саме,
# знімки — в теку NITOR_SETUP_SHOTS. NITOR_UNINSTALL_PARTS — що видалити з даних: порожньо — нічого
# («Лише програму»), «all» — усе, або через кому: scenes,fixtures,profiles,colors,settings.

param([string]$AppDir = (Join-Path $env:LOCALAPPDATA 'Nitor'), [string]$Version = '', [string]$Icon = '')

$ErrorActionPreference = 'Stop'
$LogPath = Join-Path $env:TEMP 'Nitor-uninstall.log'
$AutoTest = $env:NITOR_SETUP_AUTOTEST -eq '1'
$Shots = $env:NITOR_SETUP_SHOTS
$script:Removed = $false
$script:Busy = $false
$AppDir = $AppDir.TrimEnd('\')
$Config = Join-Path $AppDir 'config.json'

try {
    . (Join-Path $PSScriptRoot 'ui-common.ps1')
    Set-Content -LiteralPath $LogPath -Value "Nitor $Version — видалення з $AppDir" -Encoding UTF8
    Initialize-NitorUi 'Nitor.Setup'
} catch {
    try { Add-Content -LiteralPath $LogPath -Value "Не вдалося підготувати вікно: $_" -Encoding UTF8 } catch { }
    exit 3
}

# ------------------------------------------------------------------- вигляд ---
$Body = @'
      <StackPanel Grid.Row="1" Margin="24,18,24,0">
        <TextBlock x:Name="Heading" FontSize="20" FontWeight="SemiBold" Text="Видалення Nitor"/>
        <TextBlock x:Name="Sub" Foreground="{StaticResource Muted}" FontSize="12" Margin="0,6,0,0" TextWrapping="Wrap"
                   Text="Оберіть, що видалити з комп'ютера."/>
        <StackPanel x:Name="Options" Margin="0,18,0,0">
          <Border x:Name="AppCard" CornerRadius="10" BorderThickness="1" Padding="14,12" Cursor="Hand">
            <RadioButton x:Name="AppOnly" GroupName="Mode" Style="{StaticResource Radio}" IsChecked="True">
              <StackPanel>
                <TextBlock Text="Лише програму" FontWeight="SemiBold"/>
                <TextBlock Foreground="{StaticResource Muted}" FontSize="12" Margin="0,4,0,0" TextWrapping="Wrap"
                           Text="Сцени, прилади й налаштування залишаться. Після повторного встановлення все буде на місці."/>
              </StackPanel>
            </RadioButton>
          </Border>
          <Border x:Name="FullCard" Margin="0,10,0,0" CornerRadius="10" BorderThickness="1" Padding="14,12" Cursor="Hand">
            <StackPanel>
              <RadioButton x:Name="Full" GroupName="Mode" Style="{StaticResource Radio}">
                <StackPanel>
                  <TextBlock Text="Програму разом із даними" FontWeight="SemiBold"/>
                  <TextBlock Foreground="{StaticResource Muted}" FontSize="12" Margin="0,4,0,0" TextWrapping="Wrap"
                             Text="Видалити також збережені дані. Можна вибрати, які саме."/>
                </StackPanel>
              </RadioButton>
              <StackPanel x:Name="Parts" Visibility="Collapsed" Margin="30,14,0,0" Cursor="Arrow">
                <CheckBox x:Name="PartScenes" Style="{StaticResource Check}" IsChecked="True" Content="Сцени"/>
                <CheckBox x:Name="PartFixtures" Style="{StaticResource Check}" IsChecked="True" Margin="0,10,0,0"
                          Content="Прилади та профілі їхніх моделей"/>
                <CheckBox x:Name="PartProfiles" Style="{StaticResource Check}" IsChecked="True" Margin="0,10,0,0"
                          Content="Власні профілі каналів"/>
                <CheckBox x:Name="PartColors" Style="{StaticResource Check}" IsChecked="True" Margin="0,10,0,0"
                          Content="Статичні кольори"/>
                <CheckBox x:Name="PartSettings" Style="{StaticResource Check}" IsChecked="True" Margin="0,10,0,0"
                          Content="Налаштування: DMX-інтерфейс, яскравість і гарячі клавіші"/>
                <TextBlock Foreground="{StaticResource Muted}" FontSize="12" Margin="0,12,0,0" TextWrapping="Wrap"
                           Text="Щоб зберегти окрему сцену, спершу збережіть її у файл: меню сцени → «Зберегти у файл…»."/>
              </StackPanel>
            </StackPanel>
          </Border>
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
    $win = New-NitorWindow 'Видалення Nitor' $Body 'Видалити' 'DangerBtn'
} catch {
    Write-Log "Не вдалося створити вікно: $_"
    exit 3
}
if (-not $Icon) { $Icon = Join-Path $AppDir 'dmxctl\static\icon.ico' }
Set-WindowIcon $Icon
if ($Version) { $ui.VersionText.Text = $Version }

# частина даних (аргумент dmxctl.userdata) — прапорець
$PartBoxes = [ordered]@{
    scenes = $ui.PartScenes; fixtures = $ui.PartFixtures; profiles = $ui.PartProfiles
    colors = $ui.PartColors; settings = $ui.PartSettings
}

# Даних ще немає (програму жодного разу не запускали) — вибирати нічого
$HasData = Test-Path -LiteralPath $Config
if (-not $HasData) {
    $ui.Options.Visibility = 'Collapsed'
    $ui.Sub.Text = 'Програму й ярлики буде видалено з комп''ютера.'
}

if ($AutoTest -and $env:NITOR_UNINSTALL_PARTS) {
    $want = if ($env:NITOR_UNINSTALL_PARTS -eq 'all') { @($PartBoxes.Keys) } else { $env:NITOR_UNINSTALL_PARTS -split ',' }
    $ui.Full.IsChecked = $true
    foreach ($k in @($PartBoxes.Keys)) { $PartBoxes[$k].IsChecked = $want -contains $k }
}

function Update-Mode {
    $full = [bool]$ui.Full.IsChecked
    $on = @{ Border = '#4F8CFF'; Back = '#1F2A40' }
    $off = @{ Border = '#2B303B'; Back = '#1F232C' }
    $a = if ($full) { $off } else { $on }
    $b = if ($full) { $on } else { $off }
    $ui.AppCard.BorderBrush = Brush $a.Border; $ui.AppCard.Background = Brush $a.Back
    $ui.FullCard.BorderBrush = Brush $b.Border; $ui.FullCard.Background = Brush $b.Back
    $ui.Parts.Visibility = if ($full) { 'Visible' } else { 'Collapsed' }
}
Update-Mode

# Вибрані частини даних; усі п'ять — це повне видалення config.json
function Get-Parts {
    if (-not $HasData -or -not $ui.Full.IsChecked) { return @() }
    return @($PartBoxes.Keys | Where-Object { $PartBoxes[$_].IsChecked })
}

# ------------------------------------------------------------------- кроки ---
New-Steps $ui.Steps @(
    @('links', 'Ярлики', 4),
    @('data', 'Дані', 14),
    @('files', 'Файли програми', 24)
)

function Show-RunningNote {
    Show-Note 'Nitor відкрито. Її буде закрито, прожектори згаснуть.' 'warn'
    $ui.MainBtn.Content = 'Закрити Nitor і видалити'
    $script:CloseMode = $true
}

# Зовнішня програма без вікна; поки вона працює, вікно перемальовується. Повертає код і вивід.
function Invoke-Hidden($exe, $arguments) {
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.Arguments = $arguments
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [Text.Encoding]::UTF8
    $psi.WorkingDirectory = $AppDir
    Write-Log "Запуск: $exe $arguments"
    $p = [Diagnostics.Process]::Start($psi)
    $out = $p.StandardOutput.ReadToEndAsync()
    $err = $p.StandardError.ReadToEndAsync()
    while (-not $p.HasExited) { Start-Sleep -Milliseconds 40; Pump }
    $p.WaitForExit()
    $text = ($out.Result + $err.Result).Trim()
    if ($text) { Write-Log $text }
    return @{ Code = $p.ExitCode; Out = $out.Result.Trim() }
}

function Remove-Shortcuts {
    $dirs = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))
    foreach ($d in $dirs) {
        $lnk = Join-Path $d 'Nitor.lnk'
        if (Test-Path -LiteralPath $lnk) {
            try { Remove-Item -LiteralPath $lnk -Force; Write-Log "Видалено $lnk" } catch { Write-Log "Не вдалося видалити $lnk`: $_" }
        }
    }
}

# Видаляє вибрані частини даних. Повертає $true, якщо config.json більше немає.
function Remove-Data($parts) {
    if (-not (Test-Path -LiteralPath $Config)) { return $true }
    if ($parts.Count -eq $PartBoxes.Count) {
        Remove-Item -LiteralPath $Config -Force
        Write-Log 'config.json видалено повністю'
        return $true
    }
    $py = Join-Path $AppDir '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $py)) { throw 'Не знайдено Python програми' }
    $r = Invoke-Hidden $py ('-m dmxctl.userdata --config "' + $Config + '" ' + ($parts -join ' '))
    if ($r.Code -ne 0) { throw "dmxctl.userdata: код $($r.Code)" }
    return $r.Out -match 'removed'
}

function Start-Uninstall {
    if (App-Running) {
        if (-not $script:CloseMode -and -not $AutoTest) { Show-RunningNote; return }
        if (-not (Close-App)) {
            Show-Note 'Не вдалося закрити Nitor. Закрийте її вручну.' 'error'
            $ui.MainBtn.Content = 'Видалити'
            $script:CloseMode = $false
            return
        }
    }
    # тека програми — лише та, де справді лежить Nitor
    $known = (Test-Path -LiteralPath (Join-Path $AppDir 'nitor.pyw')) -or ((Split-Path $AppDir -Leaf) -eq 'Nitor')
    if (-not $known) {
        Write-Log "Тека не схожа на теку Nitor: $AppDir"
        Show-Note "Тека $AppDir не схожа на теку Nitor — її не видалено." 'error'
        return
    }

    $parts = @(Get-Parts)
    Write-Log ("Видалити дані: " + $(if ($parts.Count) { $parts -join ', ' } else { 'ні' }))
    $script:Busy = $true
    $ui.Note.Visibility = 'Collapsed'
    $ui.Options.Visibility = 'Collapsed'
    $ui.Progress.Visibility = 'Visible'
    if (-not $parts.Count) { $StepUi['data'].Row.Visibility = 'Collapsed' }
    $ui.Heading.Text = 'Видалення…'
    $ui.Sub.Text = 'Це займе кілька секунд.'
    $ui.MainBtn.Visibility = 'Collapsed'
    $ui.SecondBtn.Visibility = 'Collapsed'
    $ui.LogBtn.Visibility = 'Visible'
    Pump

    $warn = @()
    Enter-Step 'links'
    $ui.Status.Text = 'Ярлики на робочому столі та в меню «Пуск»'
    Pump
    Remove-Shortcuts

    $keepConfig = $HasData
    if ($parts.Count) {
        Enter-Step 'data'
        $ui.Status.Text = 'config.json'
        Pump
        try {
            $keepConfig = -not (Remove-Data $parts)
        } catch {
            Write-Log "Дані не видалено: $_"
            Set-StepState 'data' 'error'
            $warn += 'Не вдалося видалити вибрані дані — вони залишилися в config.json.'
        }
    }

    Enter-Step 'files'
    $items = @(Get-ChildItem -LiteralPath $AppDir -Force -ErrorAction SilentlyContinue |
               Where-Object { -not ($keepConfig -and $_.Name -eq 'config.json') })
    $n = 0
    foreach ($it in $items) {
        $n++
        $ui.Status.Text = $it.Name
        Pump
        if ($it.PSIsContainer) {
            # rd — швидше за Remove-Item на тисячах файлів середовища Python, а вікно тим часом живе
            $null = Invoke-Hidden "$env:SystemRoot\System32\cmd.exe" ('/d /c rd /s /q "' + $it.FullName + '"')
        } else {
            try { Remove-Item -LiteralPath $it.FullName -Force } catch { Write-Log "Не вдалося видалити $($it.FullName): $_" }
        }
        $ui.Bar.Value = 24 + 74 * $n / [Math]::Max(1, $items.Count)
    }
    if (-not $keepConfig) {
        try { Remove-Item -LiteralPath $AppDir -Recurse -Force } catch { Write-Log "Тека: $_" }
    }
    $left = @(Get-ChildItem -LiteralPath $AppDir -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne 'config.json' })
    if ($left.Count) {
        Write-Log ("Залишилося: " + (($left | ForEach-Object { $_.Name }) -join ', '))
        $warn += "Деякі файли не вдалося видалити. Видаліть теку вручну: $AppDir"
    }

    foreach ($id in $Order) {
        if (($StepUi[$id].State -in 'wait', 'active') -and $StepUi[$id].Row.Visibility -eq 'Visible') { Set-StepState $id 'done' }
    }
    $ui.Bar.Value = 100
    $ui.Status.Text = ' '
    $script:Removed = $true
    $script:Busy = $false
    $ui.Heading.Text = 'Nitor видалено'
    $keptData = $keepConfig -and (Test-Path -LiteralPath $Config)
    Write-Log ("Готово. Дані залишено: " + $keptData)
    if ($keptData) {
        $ui.Sub.Text = "Збережені дані залишилися в теці $AppDir — після повторного встановлення вони з'являться знову."
    } else {
        $ui.Sub.Text = 'Програму видалено з комп''ютера.'
    }
    if ($warn.Count) { Show-Note ($warn -join "`n") 'warn' }
    $ui.MainBtn.Style = $win.FindResource('Primary')
    $ui.MainBtn.Content = 'Закрити'
    $ui.MainBtn.Visibility = 'Visible'
    Save-Shot 'u2-done'
    if ($AutoTest) { $win.Close() }
}

# ------------------------------------------------------------------- події ---
$ui.AppOnly.Add_Checked({ Update-Mode })
$ui.Full.Add_Checked({ Update-Mode })
$ui.AppCard.Add_MouseLeftButtonDown({ $ui.AppOnly.IsChecked = $true })
$ui.FullCard.Add_MouseLeftButtonDown({ if (-not $ui.Full.IsChecked) { $ui.Full.IsChecked = $true } })
$ui.SecondBtn.Add_Click({ $win.Close() })
function Invoke-Main {
    if ($script:Removed) { $win.Close(); return }
    try { Start-Uninstall } catch {
        Write-Log "Помилка видалення: $_"
        $script:Busy = $false
        Show-Note "Не вдалося видалити Nitor: $($_.Exception.Message)" 'error'
        $ui.SecondBtn.Visibility = 'Visible'
        $ui.SecondBtn.Content = 'Закрити'
        if ($AutoTest) { $win.Close() }
    }
}
$ui.MainBtn.Add_Click({ Invoke-Main })
$win.Add_Closing({
    param($s, $e)
    if ($script:Busy) { $e.Cancel = $true }   # файли вже видаляються — дочекаймося кінця
})
Register-WindowChrome {
    if ($AutoTest) {
        Save-Shot 'u1-options'
        Invoke-Main
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
if ($script:Removed) { exit 0 } else { exit 1 }
