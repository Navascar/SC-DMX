# SC DMX — спільне для вікон встановлення (setup-gui.ps1) і видалення (uninstall-gui.ps1).
#
# Підключається через dot-source: . (Join-Path $PSScriptRoot 'ui-common.ps1')
# Очікує в області видимості скрипта: $LogPath (журнал), $Shots (тека знімків для CI або порожньо).
# Після New-ScDmxWindow доступні $win і $ui (елементи вікна за іменами).
#
# Кольори — з дизайн-системи програми (dmxctl/static/style.css):
#   --surface #171A21, --raised #1F232C, --line #2B303B, --line-strong #3D4452, --text #E6E8EE,
#   --muted #9AA1AE, --accent #4F8CFF, --danger #EF5B60, --warn #F5A524.

function Write-Log($text) {
    try { Add-Content -LiteralPath $LogPath -Value ("{0:HH:mm:ss}  {1}" -f (Get-Date), $text) -Encoding UTF8 } catch { }
}

# WPF і функції Windows для вікна; $AppId — своя кнопка на панелі задач, а не «Windows PowerShell»
function Initialize-ScDmxUi($AppId) {
    Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
    if (-not ('ScDmx.Native' -as [type])) {
        Add-Type -Namespace ScDmx -Name Native -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(System.IntPtr hWnd);
[DllImport("shell32.dll", CharSet = CharSet.Unicode)] public static extern int SetCurrentProcessExplicitAppUserModelID(string id);
'@
    }
    [void][ScDmx.Native]::SetCurrentProcessExplicitAppUserModelID($AppId)
}

# ------------------------------------------------------------------- вигляд ---
$ScDmxResources = @'
  <Window.Resources>
    <SolidColorBrush x:Key="Surface" Color="#171A21"/>
    <SolidColorBrush x:Key="Raised" Color="#1F232C"/>
    <SolidColorBrush x:Key="Line" Color="#2B303B"/>
    <SolidColorBrush x:Key="LineStrong" Color="#3D4452"/>
    <SolidColorBrush x:Key="Muted" Color="#9AA1AE"/>
    <SolidColorBrush x:Key="Accent" Color="#4F8CFF"/>
    <SolidColorBrush x:Key="Danger" Color="#EF5B60"/>
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
    <!-- небезпечна дія — як .btn.danger в інтерфейсі: червона рамка й текст -->
    <Style x:Key="DangerBtn" TargetType="Button" BasedOn="{StaticResource Btn}">
      <Setter Property="Background" Value="Transparent"/>
      <Setter Property="BorderBrush" Value="{StaticResource Danger}"/>
      <Setter Property="Foreground" Value="{StaticResource Danger}"/>
      <Style.Triggers>
        <Trigger Property="IsMouseOver" Value="True">
          <Setter Property="Background" Value="#2A1A1C"/>
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
    <Style x:Key="Min" TargetType="Button" BasedOn="{StaticResource Close}">
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="b" Background="Transparent" CornerRadius="8">
              <Path Data="M0,0 L10,0" Stroke="#9AA1AE" StrokeThickness="1.6"
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
    <!-- прапорець: квадрат 18×18, увімкнено — синій із галочкою -->
    <Style x:Key="Check" TargetType="CheckBox">
      <Setter Property="Foreground" Value="#E6E8EE"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="FocusVisualStyle" Value="{x:Null}"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="CheckBox">
            <Grid Background="Transparent">
              <Grid.ColumnDefinitions>
                <ColumnDefinition Width="Auto"/>
                <ColumnDefinition Width="*"/>
              </Grid.ColumnDefinitions>
              <Border x:Name="box" Width="18" Height="18" CornerRadius="5" BorderThickness="1.5" VerticalAlignment="Top"
                      Margin="0,1,0,0" Background="{StaticResource Raised}" BorderBrush="{StaticResource LineStrong}">
                <Path x:Name="tick" Data="M0,3.5 L2.8,6.2 L8,0.6" Stroke="White" StrokeThickness="1.8"
                      StrokeStartLineCap="Round" StrokeEndLineCap="Round" StrokeLineJoin="Round"
                      HorizontalAlignment="Center" VerticalAlignment="Center" Visibility="Collapsed"/>
              </Border>
              <ContentPresenter Grid.Column="1" Margin="10,0,0,0" VerticalAlignment="Center"/>
            </Grid>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="box" Property="BorderBrush" Value="#9AA1AE"/>
              </Trigger>
              <Trigger Property="IsChecked" Value="True">
                <Setter TargetName="box" Property="Background" Value="{StaticResource Accent}"/>
                <Setter TargetName="box" Property="BorderBrush" Value="{StaticResource Accent}"/>
                <Setter TargetName="tick" Property="Visibility" Value="Visible"/>
              </Trigger>
              <Trigger Property="IsKeyboardFocused" Value="True">
                <Setter TargetName="box" Property="BorderBrush" Value="White"/>
              </Trigger>
              <Trigger Property="IsEnabled" Value="False">
                <Setter Property="Opacity" Value="0.5"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <!-- перемикач варіанта: коло 18×18, вибрано — синя точка -->
    <Style x:Key="Radio" TargetType="RadioButton">
      <Setter Property="Foreground" Value="#E6E8EE"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="FocusVisualStyle" Value="{x:Null}"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="RadioButton">
            <Grid Background="Transparent">
              <Grid.ColumnDefinitions>
                <ColumnDefinition Width="Auto"/>
                <ColumnDefinition Width="*"/>
              </Grid.ColumnDefinitions>
              <Grid Width="18" Height="18" VerticalAlignment="Top" Margin="0,1,0,0">
                <Ellipse x:Name="ring" StrokeThickness="1.5" Stroke="{StaticResource LineStrong}" Fill="{StaticResource Raised}"/>
                <Ellipse x:Name="dot" Width="8" Height="8" Fill="White" Visibility="Collapsed"/>
              </Grid>
              <ContentPresenter Grid.Column="1" Margin="12,0,0,0"/>
            </Grid>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="ring" Property="Stroke" Value="#9AA1AE"/>
              </Trigger>
              <Trigger Property="IsChecked" Value="True">
                <Setter TargetName="ring" Property="Stroke" Value="{StaticResource Accent}"/>
                <Setter TargetName="ring" Property="Fill" Value="{StaticResource Accent}"/>
                <Setter TargetName="dot" Property="Visibility" Value="Visible"/>
              </Trigger>
              <Trigger Property="IsKeyboardFocused" Value="True">
                <Setter TargetName="ring" Property="Stroke" Value="White"/>
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
'@

# Вікно SC DMX: заголовок із логотипом, $Body (вміст, Grid.Row="1") і нижня панель з кнопками
# LogBtn (зліва), SecondBtn і MainBtn (справа). $MainStyle — стиль основної кнопки.
function New-ScDmxWindow($Title, $Body, $MainText, $MainStyle = 'Primary') {
    $text = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="$Title" Width="600" SizeToContent="Height"
        WindowStyle="None" AllowsTransparency="True" Background="Transparent"
        ResizeMode="NoResize" WindowStartupLocation="CenterScreen" ShowInTaskbar="True"
        FontFamily="Segoe UI Variable Text, Segoe UI" FontSize="14" Foreground="#E6E8EE"
        TextOptions.TextFormattingMode="Display" UseLayoutRounding="True">
$ScDmxResources
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
        <StackPanel Orientation="Horizontal" HorizontalAlignment="Right">
          <Button x:Name="MinBtn" Style="{StaticResource Min}" ToolTip="Згорнути" Margin="0,0,4,0"/>
          <Button x:Name="CloseX" Style="{StaticResource Close}" ToolTip="Закрити"/>
        </StackPanel>
      </Grid>

$Body

      <Border Grid.Row="2" Margin="0,22,0,0" Padding="24,14" BorderBrush="{StaticResource Line}" BorderThickness="0,1,0,0">
        <DockPanel LastChildFill="False">
          <Button x:Name="LogBtn" DockPanel.Dock="Left" Style="{StaticResource Btn}" Margin="0" Content="Журнал" Visibility="Collapsed"/>
          <Button x:Name="MainBtn" DockPanel.Dock="Right" Style="{StaticResource $MainStyle}" Content="$MainText" IsDefault="True"/>
          <Button x:Name="SecondBtn" DockPanel.Dock="Right" Style="{StaticResource Btn}" Content="Скасувати"/>
        </DockPanel>
      </Border>
    </Grid>
  </Border>
</Window>
"@
    [xml]$xaml = $text
    $script:win = [Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader $xaml))
    $script:ui = @{}
    # усі елементи з x:Name — за іменами
    $names = $xaml.SelectNodes('//*[@*[local-name()="Name"]]') | ForEach-Object { $_.GetAttribute('Name', 'http://schemas.microsoft.com/winfx/2006/xaml') }
    foreach ($n in $names) { if ($n) { $o = $script:win.FindName($n); if ($o) { $script:ui[$n] = $o } } }
    return $script:win
}

function Brush($hex) { New-Object Windows.Media.SolidColorBrush ([Windows.Media.ColorConverter]::ConvertFromString($hex)) }

# Іконка вікна без блокування файлу (файл може бути видалено, поки вікно відкрите)
function Set-WindowIcon($path) {
    if (-not $path -or -not (Test-Path -LiteralPath $path)) { return }
    try {
        $bytes = [IO.File]::ReadAllBytes($path)
        $dec = [Windows.Media.Imaging.IconBitmapDecoder]::new([IO.MemoryStream]::new($bytes),
            [Windows.Media.Imaging.BitmapCreateOptions]::None, [Windows.Media.Imaging.BitmapCacheOption]::OnLoad)
        $win.Icon = $dec.Frames[0]
    } catch { Write-Log "Іконка: $_" }
}

# ------------------------------------------------------------------- кроки ---
# $Defs: масив @(id, назва, частка смуги прогресу на початку кроку). Рядки — у панель $Panel.
$script:StepUi = @{}
$script:Order = @()
function New-Steps($Panel, $Defs) {
    foreach ($d in $Defs) {
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
        $Panel.Children.Add($row) | Out-Null
        $script:StepUi[$d[0]] = @{ Ring = $ring; Glyph = $glyph; Label = $label; Start = $d[2]; Mark = $mark; Row = $row; State = 'wait' }
    }
    $script:Order = @($Defs | ForEach-Object { $_[0] })
}

function Set-StepState($id, $state) {
    $s = $script:StepUi[$id]
    if (-not $s) { return }
    $s.State = $state
    $s.Mark.RenderTransform = $null
    switch ($state) {
        'active' {
            $s.Ring.Stroke = Brush '#4F8CFF'; $s.Ring.Fill = $null
            $s.Ring.StrokeDashArray = New-Object Windows.Media.DoubleCollection (,[double[]](6, 3))
            $rt = New-Object Windows.Media.RotateTransform; $s.Mark.RenderTransformOrigin = '0.5,0.5'
            $s.Mark.RenderTransform = $rt
            if (-not $script:Spin) {
                $script:Spin = [Windows.Media.Animation.DoubleAnimation]::new(0, 360, [TimeSpan]::FromSeconds(0.9))
                $script:Spin.RepeatBehavior = [Windows.Media.Animation.RepeatBehavior]::Forever
            }
            $rt.BeginAnimation([Windows.Media.RotateTransform]::AngleProperty, $script:Spin)
            $s.Glyph.Data = $null; $s.Label.Foreground = Brush '#E6E8EE'
        }
        'done' {
            $s.Ring.StrokeDashArray = $null; $s.Ring.Stroke = Brush '#4F8CFF'; $s.Ring.Fill = Brush '#4F8CFF'
            $s.Glyph.Data = [Windows.Media.Geometry]::Parse('M0,3.5 L2.8,6.2 L8,0.6'); $s.Glyph.Stroke = Brush '#FFFFFF'
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

# Перехід до кроку: попередні позначаються виконаними, смуга — не менше початку кроку
function Enter-Step($id) {
    $i = [array]::IndexOf($script:Order, $id)
    if ($i -lt 0) { return }
    for ($k = 0; $k -lt $i; $k++) {
        if ($script:StepUi[$script:Order[$k]].State -in 'wait', 'active') { Set-StepState $script:Order[$k] 'done' }
    }
    if ($script:StepUi[$id].State -ne 'active') { Set-StepState $id 'active' }
    $script:CurStep = $id
    $ui.Bar.Value = [Math]::Max($ui.Bar.Value, $script:StepUi[$id].Start)
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

# Дає вікну перемалюватися під час довгої роботи в цьому ж потоці
function Pump { $win.Dispatcher.Invoke([Action]{ }, [Windows.Threading.DispatcherPriority]::Background) }

# ------------------------------------------------------- запущена SC DMX ---
# Запущена SC DMX: її процеси (python/pythonw з dmxctl або sc-dmx.pyw) або сама програма на порту 8080.
# Інший застосунок на порту 8080 — це не SC DMX, він не заважає; тоді SC DMX працює
# на одному з наступних портів (8081…8099).
function Get-AppProcs {
    try {
        @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction Stop |
            Where-Object { $_.CommandLine -match 'dmxctl|sc-dmx\.pyw' })
    } catch { @() }
}
function Test-ScDmxServer($port) {
    try {
        $r = [Net.WebRequest]::Create("http://127.0.0.1:$port/")
        $r.Timeout = 1500
        $r.Proxy = $null
        $resp = $r.GetResponse()
        $text = (New-Object IO.StreamReader ($resp.GetResponseStream())).ReadToEnd()
        $resp.Close()
        return $text -match '<title>SC DMX</title>'
    } catch { return $false }
}
function Find-AppPort {
    try {
        $listening = [Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() |
            ForEach-Object { $_.Port } | Where-Object { $_ -ge 8080 -and $_ -le 8099 } | Sort-Object -Unique
    } catch { $listening = 8080 }
    foreach ($p in $listening) { if (Test-ScDmxServer $p) { return $p } }
    return $null
}
function App-Running { return ((Get-AppProcs).Count -gt 0) -or ($null -ne (Find-AppPort)) }

# Закриває SC DMX так само, як кнопка закриття у вікні програми (світло гасне), а що лишилося — зупиняє
function Close-App {
    Show-Note 'Закриваю SC DMX…' 'info'
    $ui.MainBtn.IsEnabled = $false
    Pump
    try {
        $ws = New-Object Net.WebSockets.ClientWebSocket
        $port = Find-AppPort
        if ($port -and $ws.ConnectAsync([Uri]"ws://127.0.0.1:$port/ws", [Threading.CancellationToken]::None).Wait(2000)) {
            $bytes = [Text.Encoding]::UTF8.GetBytes('{"cmd":"quit"}')
            $seg = New-Object 'ArraySegment[byte]' -ArgumentList (, $bytes)
            [void]$ws.SendAsync($seg, [Net.WebSockets.WebSocketMessageType]::Text, $true,
                                [Threading.CancellationToken]::None).Wait(2000)
            Write-Log 'Програмі надіслано команду закриття'
        }
        $ws.Dispose()
    } catch { Write-Log "Команда закриття не дійшла: $_" }
    $end = (Get-Date).AddSeconds(12)
    while ((Get-Date) -lt $end -and (App-Running)) { Start-Sleep -Milliseconds 300; Pump }
    foreach ($p in Get-AppProcs) {
        Write-Log "Зупиняю процес $($p.ProcessId): $($p.CommandLine)"
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch { }
    }
    Start-Sleep -Milliseconds 600
    $ui.MainBtn.IsEnabled = $true
    $ok = -not (App-Running)
    Write-Log ("SC DMX закрито: " + $ok)
    return $ok
}

# ------------------------------------------------------------- показ вікна ---
# Перетягування, згортання, закриття. $OnShown викликається один раз, коли вікно вже видно.
function Register-WindowChrome($OnShown) {
    $script:OnShown = $OnShown
    $ui.TitleBar.Add_MouseLeftButtonDown({ try { $win.DragMove() } catch { } })
    $ui.MinBtn.Add_Click({ $win.WindowState = 'Minimized' })
    $ui.CloseX.Add_Click({ $win.Close() })
    $ui.LogBtn.Add_Click({ try { Start-Process -FilePath 'notepad.exe' -ArgumentList "`"$LogPath`"" } catch { } })
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
        if (-not $script:Shown) {
            $script:Shown = $true
            Write-Log ("Вікно видиме: " + [ScDmx.Native]::IsWindowVisible($h))
            if ($script:OnShown) { & $script:OnShown }
        }
    })
}
