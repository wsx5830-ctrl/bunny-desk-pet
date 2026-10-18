<#
  桌面桌宠 · 宿主程序（PowerShell + WPF，无需安装任何运行时）

  能力：
  - 透明无边框窗口，置顶、不占任务栏，透明区域可穿透点击
  - 11 套皮肤，右键 / 托盘菜单切换，自动记忆上次用的皮肤
  - idle 呼吸+摆发+眨眼；戳一戳 Q 弹点头+台词；拖拽跟随并倾斜；
    松手真实重力落地回弹；20 秒无操作入睡 Zzz；点击唤醒
  - 托盘常驻，可设开机自启

  用法：双击"启动桌宠.vbs"，或
        powershell -ExecutionPolicy Bypass -File DeskPet.ps1
  自检：powershell -ExecutionPolicy Bypass -File DeskPet.ps1 -Diagnostics
#>
param(
    [switch]$Diagnostics,
    [string]$StartSkin = ""
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# ---------------- 路径与常量 ----------------
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
$skinsDir = Join-Path $rootDir "skins"
$csvPath = Join-Path $rootDir "台词表.csv"
$statePath = Join-Path $scriptDir "pet-state.json"
Remove-Item (Join-Path $scriptDir "_says.log") -ErrorAction SilentlyContinue

$PET_PX = 160          # 角色显示高度（像素，DIP）
$WIN_W = 220
$BUBBLE_H = 100
$WIN_H = $PET_PX + $BUBBLE_H
$CANVAS = 640          # 素材画布边长
$BASE_Y = 616          # 素材里脚底基线
$GRAVITY = 2200
$SLEEP_AFTER = 90.0        # 秒：多久没互动就睡着
$CHAT_MIN = 4.5            # 秒：自言自语最短间隔
$CHAT_SPAN = 450           # 毫秒级别随机抖动（4.5 + 0~4.5 秒）
$CHAT_HOLD = 2600          # 一句台词在气泡上停留多少毫秒

$SKIN_ORDER = @("default", "yigong", "casual1", "ergong", "casual2", "nanbao2",
                "casual3", "hanlin", "casual4", "sitting", "casual6")

# ---------------- 皮肤清单 ----------------
function Get-SkinList {
    $list = @()
    foreach ($d in Get-ChildItem -LiteralPath $skinsDir -Directory) {
        $j = Join-Path $d.FullName "skin.json"
        if (Test-Path -LiteralPath $j) {
            $list += (Get-Content -LiteralPath $j -Raw -Encoding UTF8 | ConvertFrom-Json)
        }
    }
    $ordered = @()
    foreach ($id in $SKIN_ORDER) {
        foreach ($m in $list) { if ($m.id -eq $id) { $ordered += $m } }
    }
    foreach ($m in $list) {
        $seen = $false
        foreach ($o in $ordered) { if ($o.id -eq $m.id) { $seen = $true } }
        if (-not $seen) { $ordered += $m }
    }
    return $ordered
}

# ---------------- 台词 ----------------
function Get-QuoteTable {
    $map = @{}
    if (Test-Path -LiteralPath $csvPath) {
        foreach ($r in (Import-Csv -LiteralPath $csvPath -Encoding UTF8)) {
            if (-not $r.text) { continue }
            $key = "$($r.skin)|$($r.state)"
            if (-not $map.ContainsKey($key)) { $map[$key] = New-Object System.Collections.ArrayList }
            [void]$map[$key].Add($r.text)
        }
    }
    return $map
}

function Pick-Quote([string]$state) {
    $pool = New-Object System.Collections.ArrayList
    $g = "|" + $state
    if ($script:quotes.ContainsKey($g)) {
        foreach ($q in $script:quotes[$g]) { [void]$pool.Add($q) }
    }
    $s = "$($script:skin.id)|$state"
    if ($script:quotes.ContainsKey($s)) {
        foreach ($q in $script:quotes[$s]) { [void]$pool.Add($q); [void]$pool.Add($q) }
    }
    if ($pool.Count -eq 0) { return "" }
    # 话痨模式下同一状态会连着抽很多次，避免“刚说完又重复同一句”
    $last = $script:lastQuote[$state]
    $pick = $pool[(Get-Random -Minimum 0 -Maximum $pool.Count)]
    $tries = 0
    while ($pick -eq $last -and $pool.Count -gt 2 -and $tries -lt 6) {
        $pick = $pool[(Get-Random -Minimum 0 -Maximum $pool.Count)]
        $tries++
    }
    $script:lastQuote[$state] = $pick
    return $pick
}

# ---------------- 素材加载 ----------------
function Load-Bitmap([string]$path) {
    $bi = New-Object System.Windows.Media.Imaging.BitmapImage
    $bi.BeginInit()
    $bi.CacheOption = [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad
    $bi.UriSource = New-Object System.Uri($path)
    $bi.EndInit()
    $bi.Freeze()
    return $bi
}

# ---------------- 界面 ----------------
$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        WindowStyle="None" AllowsTransparency="True" Background="Transparent"
        Topmost="True" ShowInTaskbar="False" ResizeMode="NoResize"
        Width="220" Height="260" Left="1200" Top="600">
  <Grid x:Name="Root" Background="{x:Null}">
    <Grid.RowDefinitions>
      <RowDefinition Height="100"/>
      <RowDefinition Height="160"/>
    </Grid.RowDefinitions>

    <Border x:Name="Bubble" Grid.Row="0" Visibility="Collapsed"
            VerticalAlignment="Bottom" HorizontalAlignment="Center"
            Background="#FFFDFBF7" BorderBrush="#33000000" BorderThickness="1"
            CornerRadius="10" Padding="8,5" MaxWidth="210" Margin="0,0,0,6">
      <Border.Effect>
        <DropShadowEffect Color="#000000" Opacity="0.18" BlurRadius="8" ShadowDepth="1"/>
      </Border.Effect>
      <TextBlock x:Name="BubbleText" Text="" TextWrapping="Wrap" MaxWidth="190"
                 FontSize="11.5" Foreground="#FF2B2B2B" FontFamily="Microsoft YaHei"/>
    </Border>

    <Canvas x:Name="Stage" Grid.Row="1" Width="160" Height="160"
            HorizontalAlignment="Center" VerticalAlignment="Bottom"
            RenderTransformOrigin="0.5,1">
      <Canvas.RenderTransform>
        <RotateTransform x:Name="TiltT" Angle="0"/>
      </Canvas.RenderTransform>
      <Canvas x:Name="Squash" Width="640" Height="640" RenderTransformOrigin="0.5,0.9625">
        <Canvas.RenderTransform>
          <ScaleTransform x:Name="SquashT" ScaleX="1" ScaleY="1"/>
        </Canvas.RenderTransform>
        <Canvas x:Name="Pet" Width="640" Height="640">
          <Canvas.RenderTransform>
            <ScaleTransform x:Name="PetScale" ScaleX="0.25" ScaleY="0.25"/>
          </Canvas.RenderTransform>
        </Canvas>
      </Canvas>
      <TextBlock x:Name="Zzz" Text="Z z z" FontSize="12" FontStyle="Italic"
                 Foreground="#FF8A8A8A" Canvas.Left="120" Canvas.Top="2"
                 Opacity="0" FontFamily="Segoe UI"/>
    </Canvas>
  </Grid>
</Window>
'@

$window = [Windows.Markup.XamlReader]::Parse($xaml)
$rootGrid = $window.FindName("Root")
$bubble = $window.FindName("Bubble")
$bubbleText = $window.FindName("BubbleText")
$stage = $window.FindName("Stage")
$petCanvas = $window.FindName("Pet")
$tiltT = $window.FindName("TiltT")
$zzz = $window.FindName("Zzz")
$squashT = $window.FindName("SquashT")
$petScale = $window.FindName("PetScale")

$window.Width = $WIN_W
$window.Height = $WIN_H

# ---------------- 状态 ----------------
$script:skins = Get-SkinList
$script:quotes = Get-QuoteTable
$script:skin = $script:skins[0]
$script:layers = @()          # @{ role, img, scale, rotate, group }
$script:state = "idle"
$script:dragging = $false
$script:moved = $false
$script:clock = [System.Diagnostics.Stopwatch]::StartNew()
$script:last = 0.0
$script:vy = 0.0
$script:vyDrag = 0.0
$script:vx = 0.0
$script:tilt = 0.0
$script:pokeAt = -99.0
$script:blinkAt = -99.0
$script:nextBlink = 0.0
$script:sayUntil = -1.0
$script:idleSince = 0.0
$script:lastQuote = @{}
$script:landedAt = -99.0
$script:nextChat = 4.0
$script:earFlap = $false
$script:scaleX = 1.0
$script:scaleY = 1.0

# 记忆上次皮肤
if (-not $StartSkin -and (Test-Path -LiteralPath $statePath)) {
    try {
        $saved = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($saved.skin) { $StartSkin = $saved.skin }
    } catch { }
}
if ($StartSkin) {
    foreach ($m in $script:skins) { if ($m.id -eq $StartSkin) { $script:skin = $m } }
}

# ---------------- 构建皮肤图层 ----------------
$BODY_ROLES = @("tail", "shorts", "body", "hand_L", "hand_R")

function New-LayerImage([string]$src, [double]$px, [double]$py) {
    $img = New-Object System.Windows.Controls.Image
    $img.Source = Load-Bitmap $src
    $img.Width = $CANVAS
    $img.Height = $CANVAS
    $img.Stretch = [System.Windows.Media.Stretch]::Fill
    $img.RenderTransformOrigin = New-Object System.Windows.Point(($px / $CANVAS), ($py / $CANVAS))
    $tr = New-Object System.Windows.Media.TransformGroup
    $sc = New-Object System.Windows.Media.ScaleTransform(1.0, 1.0)
    $ro = New-Object System.Windows.Media.RotateTransform(0.0)
    [void]$tr.Children.Add($sc)
    [void]$tr.Children.Add($ro)
    $img.RenderTransform = $tr
    return @{ img = $img; scale = $sc; rotate = $ro }
}

function Build-Skin([object]$meta) {
    $petCanvas.Children.Clear()
    $script:layers = @()

    $neck = @(320, 460)
    if ($meta.pivots.face) { $neck = $meta.pivots.face }

    # 头部组容器：整组绕脖子点转，保证点头时五官不散开
    $head = New-Object System.Windows.Controls.Canvas
    $head.Width = $CANVAS
    $head.Height = $CANVAS
    $head.RenderTransformOrigin = New-Object System.Windows.Point(($neck[0] / $CANVAS), ($neck[1] / $CANVAS))
    $headRot = New-Object System.Windows.Media.RotateTransform(0.0)
    $head.RenderTransform = $headRot

    $bodyItems = @()
    $headItems = @()

    foreach ($l in $meta.layers) {
        $src = Join-Path (Join-Path $skinsDir $meta.id) ($l.src -replace "/", [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $src)) { continue }
        $pv = @(320, 460)
        $prop = $meta.pivots.PSObject.Properties[$l.role]
        if ($prop -and $prop.Value) { $pv = $prop.Value }
        $entry = New-LayerImage $src ([double]$pv[0]) ([double]$pv[1])
        $entry.role = $l.role
        if ($BODY_ROLES -contains $l.role) {
            $bodyItems += $entry
        } else {
            $headItems += $entry
        }
        $script:layers += $entry
    }

    foreach ($e in $bodyItems) { [void]$petCanvas.Children.Add($e.img) }
    foreach ($e in $headItems) { [void]$head.Children.Add($e.img) }
    [void]$petCanvas.Children.Add($head)

    $script:headRot = $headRot
    $script:bodyItems = $bodyItems
    $script:headItems = $headItems

    $anim = $meta.anim
    $script:earSway = $false
    if ($anim -and $anim.earSway -ne $null) { $script:earSway = [bool]$anim.earSway }
    $script:canBlink = $false
    if ($anim -and $anim.blink -ne $null) { $script:canBlink = [bool]$anim.blink }
    $script:canBreathe = $true
    if ($anim -and $anim.breathe -ne $null) { $script:canBreathe = [bool]$anim.breathe }
    $script:hairSwayOn = $true
    if ($anim -and $anim.hairSway -ne $null) { $script:hairSwayOn = [bool]$anim.hairSway }
}

function Find-Layer([string]$role) {
    foreach ($e in $script:layers) { if ($e.role -eq $role) { return $e } }
    return $null
}

# ---------------- 台词气泡 ----------------
function Say([string]$text, [double]$ms = 2200) {
    if (-not $text) { return }
    try {
        ("{0:HH:mm:ss} {1}" -f (Get-Date), $text) | Add-Content -LiteralPath (Join-Path $scriptDir "_says.log") -Encoding UTF8
    } catch { }
    $bubbleText.Text = $text
    $bubble.Visibility = [System.Windows.Visibility]::Visible
    $script:sayUntil = $script:clock.Elapsed.TotalSeconds + ($ms / 1000.0)
}

# ---------------- 交互 ----------------
$script:pressScreen = $null
$script:winStart = $null
$script:pressTime = 0.0
$script:lastMove = @(0, 0)

function On-Down([object]$sender, [object]$e) {
    if ($e.ChangedButton -ne [System.Windows.Input.MouseButton]::Left) { return }
    try { $stage.CaptureMouse() | Out-Null } catch { }
    $p = [System.Windows.Forms.Cursor]::Position
    $script:pressScreen = @($p.X, $p.Y)
    $script:lastMove = @($p.X, $p.Y)
    $script:winStart = @($window.Left, $window.Top)
    $script:pressTime = $script:clock.Elapsed.TotalSeconds
    $script:moved = $false
    $script:dragging = $true
    $script:idleSince = $script:clock.Elapsed.TotalSeconds
    if ($script:state -eq "sleep") {
        $script:state = "idle"
        Say (Pick-Quote "wake") 1800
    }
}

function On-Move([object]$sender, [object]$e) {
    if (-not $script:dragging) { return }
    $p = [System.Windows.Forms.Cursor]::Position
    $dxRaw = $p.X - $script:pressScreen[0]
    $dyRaw = $p.Y - $script:pressScreen[1]
    $dx = $dxRaw / $script:scaleX
    $dy = $dyRaw / $script:scaleY

    if (-not $script:moved -and ([Math]::Sqrt($dxRaw * $dxRaw + $dyRaw * $dyRaw) -gt 6)) {
        $script:moved = $true
        $script:state = "drag"
        $script:earFlap = $true
        if ((Get-Random -Maximum 10) -lt 5) { Say (Pick-Quote "drag") 1500 }
    }
    if ($script:moved) {
        $now = $script:clock.Elapsed.TotalSeconds
        $dt = [Math]::Max($now - $script:lastT, 0.008)
        $mvx = ($p.X - $script:lastMove[0]) / $script:scaleX
        $mvy = ($p.Y - $script:lastMove[1]) / $script:scaleY
        $script:vx = $mvx / $dt
        $script:vyDrag = $mvy / $dt
        $script:lastMove = @($p.X, $p.Y)
        $script:lastT = $now
        $window.Left = $script:winStart[0] + $dx
        $window.Top = $script:winStart[1] + $dy
    }
}

function On-Up([object]$sender, [object]$e) {
    if (-not $script:dragging) { return }
    $script:dragging = $false
    try { $stage.ReleaseMouseCapture() } catch { }

    if ($script:moved) {
        $script:state = "fall"
        $script:vy = [Math]::Min([Math]::Max($script:vyDrag * 0.55, -900), 2600)
    } else {
        $script:state = "idle"
        $script:pokeAt = $script:clock.Elapsed.TotalSeconds
        $script:idleSince = $script:clock.Elapsed.TotalSeconds
        Say (Pick-Quote "poke") 1600
    }
}

$stage.Add_MouseLeftButtonDown({ param($s, $e) On-Down $s $e })
$stage.Add_MouseMove({ param($s, $e) On-Move $s $e })
$stage.Add_MouseLeftButtonUp({ param($s, $e) On-Up $s $e })

# ---------------- 每帧渲染 ----------------
function Update-Frame {
    $now = $script:clock.Elapsed.TotalSeconds
    $dt = $now - $script:last
    if ($dt -lt 0) { $dt = 0 }
    if ($dt -gt 0.06) { $dt = 0.06 }
    $script:last = $now

    # 气泡超时
    if ($script:sayUntil -gt 0 -and $now -gt $script:sayUntil) {
        $bubble.Visibility = [System.Windows.Visibility]::Collapsed
        $script:sayUntil = -1
    }

    # 入睡判定
    if ($script:state -eq "idle" -and -not $script:dragging -and ($now - $script:idleSince) -gt $SLEEP_AFTER) {
        $script:state = "sleep"
        Say (Pick-Quote "sleep") 2000
    }

    # 自言自语：闲着就时不时冒一句（约 4.5~9 秒一句，偶尔紧接着再补一句）
    if ($script:state -eq "idle" -and -not $script:dragging) {
        if ($now -gt $script:nextChat) {
            $q = Pick-Quote "idle"
            if ($q) { Say $q $CHAT_HOLD }
            if ((Get-Random -Maximum 100) -lt 28) {
                # 28% 概率：1.6 秒后马上补一句，像在自言自语地续上一句
                $script:nextChat = $now + 1.6
            } else {
                $script:nextChat = $now + $CHAT_MIN + (Get-Random -Minimum 0 -Maximum $CHAT_SPAN) / 100.0
            }
        }
    } else {
        if ($script:nextChat -lt $now + 4) { $script:nextChat = $now + 4 }
    }

    # 物理：下落
    if ($script:state -eq "fall") {
        $workBottom = [System.Windows.SystemParameters]::WorkArea.Bottom
        $script:vy += $GRAVITY * $dt
        $window.Top = $window.Top + $script:vy * $dt
        $feet = $window.Top + $WIN_H
        if ($feet -ge $workBottom) {
            $window.Top = $workBottom - $WIN_H
            if ($script:vy -gt 420) {
                $script:vy = -$script:vy * 0.34
            } else {
                $script:vy = 0
                $script:state = "idle"
                $script:landedAt = $now
                $script:idleSince = $now
                Say (Pick-Quote "fall") 1500
            }
        }
        if ($window.Top -lt 0) {
            $window.Top = 0
            $script:vy = [Math]::Abs($script:vy) * 0.3
        }
    }

    # 横向跑出屏幕则拉回
    $wa = [System.Windows.SystemParameters]::WorkArea
    $leftDip = $wa.Left
    $rightDip = $wa.Right
    if ($window.Left -lt $leftDip - 40) { $window.Left = $leftDip - 40 }
    if ($window.Left -gt $rightDip - 60) { $window.Left = $rightDip - 60 }

    # 倾斜（拖拽时按横向速度）
    $targetTilt = 0.0
    if ($script:state -eq "drag") {
        $targetTilt = [Math]::Max(-13.0, [Math]::Min(13.0, $script:vx * 0.03))
    }
    $script:tilt = $script:tilt + ($targetTilt - $script:tilt) * [Math]::Min(1.0, $dt * 10)
    $tiltT.Angle = $script:tilt

    # 呼吸
    $breathe = 1.0
    if ($script:canBreathe -and $script:state -ne "sleep") {
        $breathe = 1.0 + 0.013 * [Math]::Sin($now * 2.0 * [Math]::PI / 2.6)
    }
    foreach ($e in $script:bodyItems) {
        if ($e.role -eq "body" -or $e.role -eq "shorts") {
            $e.scale.ScaleY = $breathe
            $e.scale.ScaleX = 1.0 + (1.0 - $breathe) * 0.35
        }
    }

    # 眨眼
    $eyeScaleY = 1.0
    if ($script:canBlink) {
        if ($script:nextBlink -eq 0) { $script:nextBlink = $now + 2.5 }
        if ($now -gt $script:nextBlink) {
            $script:blinkAt = $now
            $script:nextBlink = $now + 2.6 + (Get-Random -Minimum 0 -Maximum 260) / 100.0
        }
        $bd = $now - $script:blinkAt
        if ($bd -ge 0 -and $bd -lt 0.15) {
            $k = $bd / 0.15
            $eyeScaleY = 1.0 - 0.92 * [Math]::Sin($k * [Math]::PI)
        }
    }

    # 点头 / 戳一戳
    $nod = 0.0
    $squashY = 1.0
    $squashX = 1.0
    $pd = $now - $script:pokeAt
    if ($pd -ge 0 -and $pd -lt 0.5) {
        $k = $pd / 0.5
        $nod = -7.0 * [Math]::Sin($k * [Math]::PI) + 4.0 * [Math]::Sin($k * 2.0 * [Math]::PI)
        $squashY = 1.0 - 0.10 * [Math]::Sin($k * [Math]::PI)
        $squashX = 1.0 + 0.07 * [Math]::Sin($k * [Math]::PI)
    }
    # 落地回弹
    $ld = $now - $script:landedAt
    if ($ld -ge 0 -and $ld -lt 0.45) {
        $k = $ld / 0.45
        $squashY = $squashY * (1.0 - 0.12 * [Math]::Sin($k * [Math]::PI))
        $squashX = $squashX * (1.0 + 0.09 * [Math]::Sin($k * [Math]::PI))
    }

    $headAngle = $nod

    # 头发轻晃
    $hair = Find-Layer "hair"
    if ($hair) {
        $a = 0.0
        if ($script:hairSwayOn -and $script:state -ne "sleep") {
            $a = 0.7 * [Math]::Sin($now * 2.0 * [Math]::PI / 3.2)
        }
        $hair.rotate.Angle = $a
    }

    # 耳朵：独立摆动 / 固定跟随头部 / 拖拽扇动
    foreach ($e in $script:layers) {
        if ($e.role -ne "ear_L" -and $e.role -ne "ear_R") { continue }
        $dir = 1.0
        if ($e.role -eq "ear_R") { $dir = -1.0 }
        $a = 0.0
        if ($script:earSway -and $script:state -eq "idle") {
            $a = $dir * 2.3 * [Math]::Sin($now * 2.0 * [Math]::PI / 3.2)
        }
        if ($script:earSway -and $script:state -eq "drag") {
            $a = $dir * 13.0 * [Math]::Sin($now * 2.0 * [Math]::PI * 2.4)
        }
        $e.rotate.Angle = $a
    }

    # 眼睛眨眼
    foreach ($e in $script:layers) {
        if ($e.role -eq "eye_L" -or $e.role -eq "eye_R") {
            $e.scale.ScaleY = $eyeScaleY
        }
    }

    # 戳一戳压扁：整体（含头）绕脚底缩放；基础缩放 PetScale 保持不变
    $squashT.ScaleX = $squashX
    $squashT.ScaleY = $squashY

    # 头部整组转
    $script:headRot.Angle = $headAngle

    # 睡眠：变暗 + Zzz 呼吸
    if ($script:state -eq "sleep") {
        $stage.Opacity = 0.86
        $zzz.Opacity = 0.35 + 0.35 * [Math]::Abs([Math]::Sin($now * 1.4))
    } else {
        $stage.Opacity = 1.0
        $zzz.Opacity = 0.0
    }
}

# ---------------- 皮肤切换 ----------------
function Switch-Skin([string]$id) {
    $found = $null
    foreach ($m in $script:skins) { if ($m.id -eq $id) { $found = $m } }
    if (-not $found) { return }
    $script:skin = $found
    Build-Skin $found
    $script:state = "idle"
    $script:idleSince = $script:clock.Elapsed.TotalSeconds
    Say "换好啦！" 1400
    if (-not $Diagnostics) {
        try {
            @{ skin = $found.id } | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
        } catch { }
    }
}

# ---------------- 右键菜单 / 托盘 ----------------
$menu = New-Object System.Windows.Forms.ContextMenuStrip
$skinMenu = New-Object System.Windows.Forms.ToolStripMenuItem("换皮肤")
[void]$menu.Items.Add($skinMenu)
foreach ($m in $script:skins) {
    $it = New-Object System.Windows.Forms.ToolStripMenuItem($m.name)
    $it.Tag = $m.id
    $it.add_Click({ param($s, $e) Switch-Skin ([string]$s.Tag) })
    [void]$skinMenu.DropDownItems.Add($it)
}
[void]$menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
$itemToggle = New-Object System.Windows.Forms.ToolStripMenuItem("隐藏桌宠")
[void]$menu.Items.Add($itemToggle)

$startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$lnkPath = Join-Path $startupDir "桌宠.lnk"
$itemAuto = New-Object System.Windows.Forms.ToolStripMenuItem("开机自启")
$itemAuto.Checked = Test-Path -LiteralPath $lnkPath
[void]$menu.Items.Add($itemAuto)

[void]$menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
$itemExit = New-Object System.Windows.Forms.ToolStripMenuItem("退出")
[void]$menu.Items.Add($itemExit)

$itemToggle.add_Click({
    if ($window.Visibility -eq [System.Windows.Visibility]::Visible) {
        $window.Visibility = [System.Windows.Visibility]::Hidden
        $itemToggle.Text = "显示桌宠"
    } else {
        $window.Visibility = [System.Windows.Visibility]::Visible
        $itemToggle.Text = "隐藏桌宠"
    }
})
$itemAuto.add_Click({
    if (Test-Path -LiteralPath $lnkPath) {
        Remove-Item -LiteralPath $lnkPath -Force
        $itemAuto.Checked = $false
    } else {
        $sh = New-Object -ComObject WScript.Shell
        $sc = $sh.CreateShortcut($lnkPath)
        $vbs = Join-Path $scriptDir "启动桌宠.vbs"
        $sc.TargetPath = "wscript.exe"
        $sc.Arguments = '"' + $vbs + '"'
        $sc.WorkingDirectory = $scriptDir
        $sc.Description = "桌面桌宠"
        $sc.Save()
        $itemAuto.Checked = $true
    }
})
$itemExit.add_Click({
    $script:alive = $false
    if ($script:tray) { $script:tray.Visible = $false; $script:tray.Dispose() }
    $window.Close()
})

$stage.Add_MouseRightButtonUp({
    $menu.Show([System.Windows.Forms.Cursor]::Position)
})

# 托盘
$tray = New-Object System.Windows.Forms.NotifyIcon
try {
    $thumbPath = Join-Path (Join-Path $skinsDir $script:skin.id) "thumb.png"
    $bmp = [System.Drawing.Bitmap]::FromFile($thumbPath)
    $tray.Icon = [System.Drawing.Icon]::FromHandle($bmp.GetHicon())
} catch {
    $tray.Icon = [System.Drawing.SystemIcons]::Application
}
$tray.Text = "桌宠"
$tray.Visible = $true
$tray.ContextMenuStrip = $menu
$tray.add_DoubleClick({
    $window.Visibility = [System.Windows.Visibility]::Visible
    $itemToggle.Text = "隐藏桌宠"
})
$script:tray = $tray

# ---------------- 启动 ----------------
Build-Skin $script:skin

# 桌面图标：不存在则自建（换目录后仍有效）
function Ensure-DesktopShortcut {
    try {
        $desk = [Environment]::GetFolderPath("Desktop")
        $lnk = Join-Path $desk "桌宠.lnk"
        if (-not (Test-Path -LiteralPath $lnk)) {
            $sh = New-Object -ComObject WScript.Shell
            $sc = $sh.CreateShortcut($lnk)
            $sc.TargetPath = "wscript.exe"
            $sc.Arguments = '"' + (Join-Path $scriptDir "启动桌宠.vbs") + '"'
            $sc.WorkingDirectory = $scriptDir
            $ico = Join-Path $scriptDir "pet.ico"
            if (Test-Path -LiteralPath $ico) { $sc.IconLocation = "$ico,0" }
            $sc.Description = "启动桌面桌宠"
            $sc.Save()
        }
    } catch { }
}
Ensure-DesktopShortcut

# DPI 换算：窗口坐标是 DIP，鼠标/屏幕是像素
$window.Show()
$src = [System.Windows.PresentationSource]::FromVisual($window)
$m = $src.CompositionTarget.TransformToDevice
$script:scaleX = $m.M11
$script:scaleY = $m.M22

# 初始位置：右下角偏上（WorkArea 与窗口坐标同为 DIP，无需换算）
$wa = [System.Windows.SystemParameters]::WorkArea
$window.Left = $wa.Right - $WIN_W - 40
$window.Top = $wa.Bottom - $WIN_H - 40
$script:idleSince = $script:clock.Elapsed.TotalSeconds
$script:lastT = $script:clock.Elapsed.TotalSeconds
Say "我在这儿陪你啦" 1800

$timer = New-Object System.Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromMilliseconds(33)
$timer.Add_Tick({ Update-Frame })
$timer.Start()

if ($Diagnostics) {
    $log = Join-Path $scriptDir "_diag.txt"
    $lines = @()
    $lines += "skins: $($script:skins.Count)"
    $lines += "active: $($script:skin.id) / layers: $($script:layers.Count) / body: $($script:bodyItems.Count) / head: $($script:headItems.Count)"
    $lines += "earSway: $script:earSway / blink: $script:canBlink / scale: $($script:scaleX)x$($script:scaleY)"
    $lines += "pool |idle: $(@($script:quotes['|idle']).Count) / pool $($script:skin.id)|idle: $(@($script:quotes[($script:skin.id + '|idle')]).Count)"
    Start-Sleep -Milliseconds 150
    Update-Frame
    $lines += "frame1 ok"
    $script:pokeAt = $script:clock.Elapsed.TotalSeconds
    Update-Frame
    $lines += "poke ok, head angle: $($script:headRot.Angle)"
    $script:state = "sleep"
    Update-Frame
    $lines += "sleep ok, opacity: $($stage.Opacity)"
    Switch-Skin "casual1"
    Update-Frame
    $lines += "diag ok, layers after switch: $($script:layers.Count), skin: $($script:skin.id)"
    $lines | Set-Content -LiteralPath $log -Encoding UTF8
    $timer.Stop()
    $tray.Visible = $false
    $window.Close()
    return
}

$app = New-Object System.Windows.Application
[void]$app.Run($window)
$tray.Visible = $false
$tray.Dispose()
