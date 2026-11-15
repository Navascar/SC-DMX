# SC DMX — вікно встановлення (запускає SC-DMX-Setup.exe, без консолі).
#
# Вікно в стилі програми (темне, кольори й шрифт — як в інтерфейсі). Саме встановлення робить
# install.ps1 -Progress у фоновому процесі без вікна, а сюди передає хід рядками @@STEP/@@LOG/...
#
# Код виходу: 0 — програму встановлено, 1 — ні (скасовано або помилка встановлення),
# 3 — саме вікно не вдалося відкрити (тоді SC-DMX-Setup.exe показує повідомлення з журналом).
# Для перевірки в CI: SCDMX_SETUP_AUTOTEST=1 — встановлення починається само, вікно закривається саме,
# а знімки вікна зберігаються в теку SCDMX_SETUP_SHOTS.

param([string]$Source = $PSScriptRoot, [string]$Version = '')

$ErrorActionPreference = 'Stop'
$LogPath = Join-Path $env:TEMP 'SC-DMX-install.log'
$AutoTest = $env:SCDMX_SETUP_AUTOTEST -eq '1'
$Shots = $env:SCDMX_SETUP_SHOTS
$script:Installed = $false

function Write-Log($text) {
    try { Add-Content -LiteralPath $LogPath -Value ("{0:HH:mm:ss}  {1}" -f (Get-Date), $text) -Encoding UTF8 } catch { }
}

try {
    Set-Content -LiteralPath $LogPath -Value "SC DMX $Version — встановлення" -Encoding UTF8
    Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
    Add-Type -Namespace ScDmx -Name Native -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(System.IntPtr hWnd);
[DllImport("shell32.dll", CharSet = CharSet.Unicode)] public static extern int SetCurrentProcessExplicitAppUserModelID(string id);
'@
    # своя кнопка на панелі задач, а не «Windows PowerShell»
    [void][ScDmx.Native]::SetCurrentProcessExplicitAppUserModelID('SCDMX.Setup')
} catch {
    Write-Log "Не вдалося підготувати вікно: $_"
    exit 3
}

# ------------------------------------------------------------------- вигляд ---
[xml]$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Встановлення SC DMX" Width="600" SizeToContent="Height"
        WindowStyle="None" AllowsTransparency="True" Background="Transparent"
        ResizeMode="NoResize" WindowStartupLocation="CenterScreen" ShowInTaskbar="True"
        FontFamily="Segoe UI Variable Text, Segoe UI" FontSize="14" Foreground="#E6E8EE"
        TextOptions.TextFormattingMode="Display" UseLayoutRounding="True">
  <Window.Resources>
    <SolidColorBrush x:Key="Surface" Color="#171A21"/>
    <SolidColorBrush x:Key="Raised" Color="#1F232C"/>
    <SolidColorBrush x:Key="Line" Color="#2B303B"/>
    <SolidColorBrush x:Key="LineStrong" Color="#3D4452"/>
    <SolidColorBrush x:Key="Muted" Color="#9AA1AE"/>
    <SolidColorBrush x:Key="Accent" Color="#4F8CFF"/>
    <Style x:Key="Btn" TargetType="Button">
      <Setter Property="Foreground" Value="#E6E8EE"/>
      <Setter Property="Background" Value="{StaticResource Raised}"/>
      <Setter Property="BorderBrush" Value="{StaticResource Line}"/>
      <Setter Property="FontWeight" Value="Medium"/>
      <Setter Property="Height" Value="34"/>
      <Setter Property="Padding" Value="14,0"/>
      <Setter Property="Margin" Value="8,0,0,0"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="FocusVisualStyle" Value="{x:Null}"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="b" Background="{TemplateBinding Background}" BorderBrush="{TemplateBinding BorderBrush}"
                    BorderThickness="1" CornerRadius="10" Padding="{TemplateBinding Padding}">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="b" Property="BorderBrush" Value="{StaticResource LineStrong}"/>
              </Trigger>
              <Trigger Property="IsKeyboardFocused" Value="True">
                <Setter TargetName="b" Property="BorderBrush" Value="{StaticResource Accent}"/>
              </Trigger>
              <Trigger Property="IsEnabled" Value="False">
                <Setter TargetName="b" Property="Opacity" Value="0.5"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style x:Key="Primary" TargetType="Button" BasedOn="{StaticResource Btn}">
      <Setter Property="Background" Value="{StaticResource Accent}"/>
      <Setter Property="BorderBrush" Value="{StaticResource Accent}"/>
      <Setter Property="Foreground" Value="White"/>
      <Style.Triggers>
        <Trigger Property="IsMouseOver" Value="True">
          <Setter Property="Background" Value="#3F7CF0"/>
        </Trigger>
      </Style.Triggers>
    </Style>
    <Style x:Key="Close" TargetType="Button">
      <Setter Property="Width" Value="32"/>
      <Setter Property="Height" Value="32"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="FocusVisualStyle" Value="{x:Null}"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="b" Background="Transparent" CornerRadius="8">
              <Path Data="M0,0 L10,10 M10,0 L0,10" Stroke="#9AA1AE" StrokeThickness="1.6"
                    StrokeStartLineCap="Round" StrokeEndLineCap="Round"
                    HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="b" Property="Background" Value="#1F232C"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style TargetType="ProgressBar">
      <Setter Property="Height" Value="6"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="ProgressBar">
            <Grid>
              <Border Background="#2B303B" CornerRadius="3"/>
              <Border x:Name="PART_Track"/>
              <Border x:Name="PART_Indicator" HorizontalAlignment="Left" Background="{StaticResource Accent}" CornerRadius="3"/>
            </Grid>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
  </Window.Resources>

  <Border Margin="16" Background="{StaticResource Surface}" BorderBrush="{StaticResource Line}" BorderThickness="1" CornerRadius="14">
    <Border.Effect>
      <DropShadowEffect BlurRadius="24" ShadowDepth="4" Opacity="0.45" Color="Black"/>
    </Border.Effect>
    <Grid>
      <Grid.RowDefinitions>
        <RowDefinition Height="Auto"/>
        <RowDefinition Height="Auto"/>
        <RowDefinition Height="Auto"/>
      </Grid.RowDefinitions>

      <!-- верхня панель: перетягування вікна -->
      <Grid x:Name="TitleBar" Grid.Row="0" Background="Transparent" Margin="20,14,12,0">
        <StackPanel Orientation="Horizontal" VerticalAlignment="Center">
          <Grid Width="28" Height="28">
            <Border Background="#0F1115" CornerRadius="7"/>
            <Ellipse Width="13" Height="13" Fill="#FF3B3B" Opacity="0.9" Margin="-6,-6,0,0"/>
            <Ellipse Width="13" Height="13" Fill="#3BFF6A" Opacity="0.75" Margin="6,-6,0,0"/>
            <Ellipse Width="13" Height="13" Fill="#3B7BFF" Opacity="0.8" Margin="0,6,0,0"/>
          </Grid>
          <TextBlock Text="SC DMX" FontWeight="SemiBold" FontSize="16" Margin="10,0,0,0" VerticalAlignment="Center"/>
          <TextBlock x:Name="VersionText" Foreground="{StaticResource Muted}" FontSize="12" Margin="8,2,0,0" VerticalAlignment="Center"/>
        </StackPanel>
        <Button x:Name="CloseX" Style="{StaticResource Close}" HorizontalAlignment="Right" ToolTip="Закрити"/>
      </Grid>

      <StackPanel Grid.Row="1" Margin="24,18,24,0">
        <TextBlock x:Name="Heading" FontSize="20" FontWeight="SemiBold" Text="Встановлення SC DMX"/>
        <TextBlock x:Name="Sub" Foreground="{StaticResource Muted}" FontSize="12" Margin="0,6,0,0" TextWrapping="Wrap"
                   Text="Програма встановиться для поточного користувача, права адміністратора не потрібні. Під час першого встановлення завантажується близько 250 МБ, тому потрібен інтернет. Налаштування й сцени зберігаються."/>
        <StackPanel x:Name="Steps" Margin="0,18,0,0"/>
        <ProgressBar x:Name="Bar" Minimum="0" Maximum="100" Value="0" Margin="0,14,0,0"/>
        <TextBlock x:Name="Status" Foreground="{StaticResource Muted}" FontSize="11" Margin="0,8,0,0"
                   FontFamily="Cascadia Mono, Consolas" TextTrimming="CharacterEllipsis" Text=" "/>
        <Border x:Name="Note" Visibility="Collapsed" Margin="0,14,0,0" Padding="12,10" CornerRadius="10" BorderThickness="1">
          <TextBlock x:Name="NoteText" TextWrapping="Wrap" FontSize="12"/>
        </Border>
      </StackPanel>

      <Border Grid.Row="2" Margin="0,22,0,0" Padding="24,14" BorderBrush="{StaticResource Line}" BorderThickness="0,1,0,0">
        <DockPanel LastChildFill="False">
          <Button x:Name="LogBtn" DockPanel.Dock="Left" Style="{StaticResource Btn}" Margin="0" Content="Журнал" Visibility="Collapsed"/>
          <Button x:Name="MainBtn" DockPanel.Dock="Right" Style="{StaticResource Primary}" Content="Встановити" IsDefault="True"/>
          <Button x:Name="SecondBtn" DockPanel.Dock="Right" Style="{StaticResource Btn}" Content="Скасувати"/>
        </DockPanel>
      </Border>
    </Grid>
  </Border>
</Window>
'@

try {
    $win = [Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader $xaml))
} catch {
    Write-Log "Не вдалося створити вікно: $_"
    exit 3
}
$ui = @{}
foreach ($n in 'TitleBar', 'CloseX', 'VersionText', 'Heading', 'Sub', 'Steps', 'Bar', 'Status', 'Note', 'NoteText',
               'LogBtn', 'MainBtn', 'SecondBtn') { $ui[$n] = $win.FindName($n) }
$icon = Join-Path $Source 'dmxctl\static\icon.ico'
if (Test-Path $icon) { try { $win.Icon = [Windows.Media.Imaging.BitmapFrame]::Create([Uri]$icon) } catch { } }
if ($Version) { $ui.VersionText.Text = $Version }

function Brush($hex) { New-Object Windows.Media.SolidColorBrush ([Windows.Media.ColorConverter]::ConvertFromString($hex)) }

# ------------------------------------------------------------------- кроки ---
# id, назва, частка смуги прогресу на початку кроку
$StepDefs = @(
    @('python', 'Python', 2),
    @('files', 'Файли програми', 10),
    @('venv', 'Середовище Python', 18),
    @('deps', 'Залежності (вперше близько 250 МБ)', 26),
    @('shortcuts', 'Ярлики на робочому столі й у меню «Пуск»', 90),
    @('udmx', 'Перевірка uDMX', 95)
)
$StepUi = @{}
foreach ($d in $StepDefs) {
    $row = New-Object Windows.Controls.Grid
    $row.Margin = '0,0,0,10'
    $c0 = New-Object Windows.Controls.ColumnDefinition; $c0.Width = '26'
    $c1 = New-Object Windows.Controls.ColumnDefinition
    $row.ColumnDefinitions.Add($c0); $row.ColumnDefinitions.Add($c1)
    $mark = New-Object Windows.Controls.Grid
    $mark.Width = 16; $mark.Height = 16; $mark.HorizontalAlignment = 'Left'
    $ring = New-Object Windows.Shapes.Ellipse
    $ring.StrokeThickness = 1.5; $ring.Stroke = Brush '#3D4452'
    $glyph = New-Object Windows.Shapes.Path
    $glyph.StrokeThickness = 1.8; $glyph.Stroke = Brush '#FFFFFF'
    $glyph.StrokeStartLineCap = 'Round'; $glyph.StrokeEndLineCap = 'Round'; $glyph.StrokeLineJoin = 'Round'
    $glyph.HorizontalAlignment = 'Center'; $glyph.VerticalAlignment = 'Center'
    $mark.Children.Add($ring) | Out-Null; $mark.Children.Add($glyph) | Out-Null
    $label = New-Object Windows.Controls.TextBlock
    $label.Text = $d[1]; $label.Foreground = Brush '#9AA1AE'
    [Windows.Controls.Grid]::SetColumn($label, 1)
    $row.Children.Add($mark) | Out-Null; $row.Children.Add($label) | Out-Null
    $ui.Steps.Children.Add($row) | Out-Null
    $StepUi[$d[0]] = @{ Ring = $ring; Glyph = $glyph; Label = $label; Start = $d[2]; Mark = $mark; State = 'wait' }
}
$Order = $StepDefs | ForEach-Object { $_[0] }

$Spin = New-Object Windows.Media.Animation.DoubleAnimation(0, 360, [TimeSpan]::FromSeconds(0.9))
$Spin.RepeatBehavior = [Windows.Media.Animation.RepeatBehavior]::Forever

function Set-StepState($id, $state) {
    $s = $StepUi[$id]
    if (-not $s) { return }
    $s.State = $state
    $s.Mark.RenderTransform = $null
    switch ($state) {
        'active' {
            $s.Ring.Stroke = Brush '#4F8CFF'; $s.Ring.Fill = $null
            $s.Ring.StrokeDashArray = New-Object Windows.Media.DoubleCollection (,[double[]](6, 3))
            $rt = New-Object Windows.Media.RotateTransform; $s.Mark.RenderTransformOrigin = '0.5,0.5'
            $s.Mark.RenderTransform = $rt
            $rt.BeginAnimation([Windows.Media.RotateTransform]::AngleProperty, $Spin)
            $s.Glyph.Data = $null; $s.Label.Foreground = Brush '#E6E8EE'
        }
        'done' {
            $s.Ring.StrokeDashArray = $null; $s.Ring.Stroke = Brush '#4F8CFF'; $s.Ring.Fill = Brush '#4F8CFF'
            $s.Glyph.Data = [Windows.Media.Geometry]::Parse('M0,3.5 L2.8,6.2 L8,0.6'); $s.Glyph.Stroke = Brush '#FFFFFF'
            $s.Label.Foreground = Brush '#E6E8EE'
        }
        'warn' {
            $s.Ring.StrokeDashArray = $null; $s.Ring.Stroke = Brush '#F5A524'; $s.Ring.Fill = Brush '#F5A524'
            $s.Glyph.Data = [Windows.Media.Geometry]::Parse('M0,0 L0,4.5 M0,7.2 L0,7.4'); $s.Glyph.Stroke = Brush '#0F1115'
            $s.Label.Foreground = Brush '#E6E8EE'
        }
        'error' {
            $s.Ring.StrokeDashArray = $null; $s.Ring.Stroke = Brush '#EF5B60'; $s.Ring.Fill = Brush '#EF5B60'
            $s.Glyph.Data = [Windows.Media.Geometry]::Parse('M0,0 L6,6 M6,0 L0,6'); $s.Glyph.Stroke = Brush '#FFFFFF'
            $s.Label.Foreground = Brush '#E6E8EE'
        }
        default {
            $s.Ring.StrokeDashArray = $null; $s.Ring.Stroke = Brush '#3D4452'; $s.Ring.Fill = $null
            $s.Glyph.Data = $null; $s.Label.Foreground = Brush '#9AA1AE'
        }
    }
}

function Show-Note($text, $kind) {
    $colors = @{ warn = @('#F5A524', '#2A2416'); error = @('#EF5B60', '#2A1A1C'); info = @('#4F8CFF', '#17223A') }
    $c = $colors[$kind]
    $ui.Note.BorderBrush = Brush $c[0]; $ui.Note.Background = Brush $c[1]
    $ui.NoteText.Text = $text; $ui.NoteText.Foreground = Brush '#E6E8EE'
    $ui.Note.Visibility = 'Visible'
}

function Save-Shot($name) {
    if (-not $Shots) { return }
    try {
        New-Item -ItemType Directory -Force $Shots | Out-Null
        $win.UpdateLayout()
        $w = [int]($win.ActualWidth * 2); $h = [int]($win.ActualHeight * 2)
        $bmp = [Windows.Media.Imaging.RenderTargetBitmap]::new($w, $h, 192, 192, [Windows.Media.PixelFormats]::Pbgra32)
        $bmp.Render($win)
        $enc = New-Object Windows.Media.Imaging.PngBitmapEncoder
        $enc.Frames.Add([Windows.Media.Imaging.BitmapFrame]::Create($bmp))
        $fs = [IO.File]::Create((Join-Path $Shots "$name.png")); $enc.Save($fs); $fs.Close()
    } catch { Write-Log "Знімок $name не вдався: $_" }
}

# --------------------------------------------------------------- встановлення ---
$script:Proc = $null
$script:OutTask = $null
$script:ErrTask = $null
$script:CurStep = $null
$script:DepLines = 0
$script:Failed = $false
$script:Warned = $false
$script:Done = $false

function App-Running {
    $c = New-Object Net.Sockets.TcpClient
    try { return $c.ConnectAsync('127.0.0.1', 8080).Wait(400) -and $c.Connected } catch { return $false } finally { $c.Close() }
}

function Enter-Step($id) {
    $i = [array]::IndexOf($Order, $id)
    if ($i -lt 0) { return }
    for ($k = 0; $k -lt $i; $k++) { if ($StepUi[$Order[$k]].State -in 'wait', 'active') { Set-StepState $Order[$k] 'done' } }
    if ($StepUi[$id].State -ne 'active') { Set-StepState $id 'active' }
    $script:CurStep = $id
    $ui.Bar.Value = [Math]::Max($ui.Bar.Value, $StepUi[$id].Start)
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
        'WARN' { $script:Warned = $true; Set-StepState $parts[1] 'warn'; Show-Note $parts[2] 'warn' }
        'ERROR' {
            $script:Failed = $true
            if ($script:CurStep) { Set-StepState $script:CurStep 'error' }
            Show-Note $parts[1] 'error'
        }
        'DONE' { $script:Done = $true }
    }
}

function Start-Install {
    $ui.Note.Visibility = 'Collapsed'
    if (App-Running) { Show-Note 'SC DMX зараз відкрито. Закрийте вікно програми й натисніть «Встановити» ще раз.' 'warn'; return }
    foreach ($id in $Order) { Set-StepState $id 'wait' }
    $script:Failed = $false; $script:Warned = $false; $script:Done = $false; $script:DepLines = 0; $script:CurStep = $null
    $ui.Bar.Value = 0
    $ui.Heading.Text = 'Встановлення…'
    $ui.Sub.Text = 'Це може тривати кілька хвилин. Вікно можна згорнути.'
    $ui.MainBtn.Visibility = 'Collapsed'
    $ui.SecondBtn.Content = 'Скасувати'
    $ui.LogBtn.Visibility = 'Visible'

    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = (Get-Process -Id $PID).Path
    $psi.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $Source 'install.ps1') + '" -Progress -NoLaunch'
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
        foreach ($id in $Order) { if ($StepUi[$id].State -in 'wait', 'active') { Set-StepState $id 'done' } }
        $ui.Bar.Value = 100
        $script:Installed = $true
        $ui.Heading.Text = 'SC DMX встановлено'
        $ui.Sub.Text = 'Надалі запускайте програму ярликом «SC DMX» на робочому столі або в меню «Пуск». Оновлення програма пропонує сама.'
        $ui.Status.Text = ' '
        $ui.MainBtn.Content = 'Запустити SC DMX'
        $ui.MainBtn.Visibility = 'Visible'
        $ui.SecondBtn.Content = 'Закрити'
        Save-Shot '3-done'
    } else {
        if (-not $script:Failed) {
            if ($script:CurStep) { Set-StepState $script:CurStep 'error' }
            Show-Note "Встановлення перервано (код $code). Подробиці — у журналі." 'error'
        }
        $ui.Heading.Text = 'Не вдалося встановити'
        $ui.Sub.Text = 'Перевірте інтернет і спробуйте ще раз. Уже встановлені налаштування й сцени не постраждали.'
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
    $lnk = Join-Path ([Environment]::GetFolderPath('Programs')) 'SC DMX.lnk'
    $app = Join-Path $env:LOCALAPPDATA 'SC-DMX'
    try {
        if (Test-Path $lnk) { Start-Process -FilePath $lnk }
        else { Start-Process -FilePath (Join-Path $app '.venv\Scripts\pythonw.exe') -ArgumentList ('"' + (Join-Path $app 'sc-dmx.pyw') + '"') -WorkingDirectory $app }
    } catch { Write-Log "Не вдалося запустити: $_" }
}

# ------------------------------------------------------------------- події ---
$ui.TitleBar.Add_MouseLeftButtonDown({ try { $win.DragMove() } catch { } })
$ui.CloseX.Add_Click({ $win.Close() })
$ui.SecondBtn.Add_Click({ $win.Close() })
$ui.LogBtn.Add_Click({ try { Start-Process -FilePath 'notepad.exe' -ArgumentList "`"$LogPath`"" } catch { } })
$ui.MainBtn.Add_Click({
    if ($script:Installed) { Launch-App; $win.Close() } else { Start-Install }
})
$win.Add_Closing({
    param($s, $e)
    if ($script:Proc -and -not $script:Proc.HasExited) {
        if ($AutoTest) { Stop-Install; return }
        $r = [Windows.MessageBox]::Show($win, 'Зупинити встановлення SC DMX?', 'SC DMX', 'YesNo', 'Question')
        if ($r -ne 'Yes') { $e.Cancel = $true; return }
        Stop-Install
    }
})
# SC-DMX-Setup.exe запускає цей процес прихованим (без консолі). Windows застосовує «приховано»
# до першого показу вікна, тож перший виклик ShowWindow «витрачаємо» до показу, а потім показуємо явно.
$win.Add_SourceInitialized({
    $h = (New-Object Windows.Interop.WindowInteropHelper $win).Handle
    [void][ScDmx.Native]::ShowWindow($h, 0)
})
$win.Add_ContentRendered({
    $h = (New-Object Windows.Interop.WindowInteropHelper $win).Handle
    [void][ScDmx.Native]::ShowWindow($h, 5)
    [void][ScDmx.Native]::SetForegroundWindow($h)
    $win.Activate() | Out-Null
    Write-Log ("Вікно видиме: " + [ScDmx.Native]::IsWindowVisible($h))
    if ($AutoTest -and -not $script:Started) {
        $script:Started = $true
        Save-Shot '1-welcome'
        Start-Install
    }
})

try {
    [void]$win.ShowDialog()
} catch {
    Write-Log "Помилка вікна: $_"
    exit 3
}
if ($script:Installed) { exit 0 } else { exit 1 }
