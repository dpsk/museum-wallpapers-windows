# Museum Wallpapers demo, second method (media/demo/RECORDING-windows.md in dpsk/dpsk.github.io):
# Desktop Duplication (ffmpeg ddagrab) at 60 fps, the cursor gliding by script.
# The card opens by a second launch of the app while the cursor reaches the tray icon (no click on
# the taskbar); Next and the close button are clicked inside the card itself.
#   take.ps1 -Lang en|ru [-Tray X,Y]   (tray icon position in physical pixels)
param([ValidateSet('en', 'ru')][string]$Lang = 'en', [int[]]$Tray = @(3434, 2115), [double]$Seconds = 24)
$demo = Split-Path -Parent $MyInvocation.MyCommand.Path
$state = Join-Path $demo 'state.txt'
function Mark($text) { "$text $(Get-Date -Format o)" | Set-Content -Encoding ASCII $state }
Start-Transcript (Join-Path $demo "take2-$Lang.log") -Force | Out-Null
Add-Type @'
using System; using System.Runtime.InteropServices; using System.Text;
public static class W {
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, UIntPtr e);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    public struct POINT { public int X, Y; }
    public struct RECT { public int Left, Top, Right, Bottom; }
    // The largest visible Tk window of these processes: the card. Empty rect when closed.
    public static RECT Card(uint[] pids) {
        RECT best = new RECT(); int area = 0;
        EnumWindows((h, l) => {
            uint pid; GetWindowThreadProcessId(h, out pid);
            if (Array.IndexOf(pids, pid) >= 0 && IsWindowVisible(h)) {
                var c = new StringBuilder(64); GetClassName(h, c, 64);
                RECT r; GetWindowRect(h, out r);
                int a = (r.Right - r.Left) * (r.Bottom - r.Top);
                if (c.ToString().StartsWith("Tk") && a > area && r.Right - r.Left > 200) { area = a; best = r; }
            }
            return true;
        }, IntPtr.Zero);
        return best;
    }
    public static void Click() { mouse_event(0x0002, 0, 0, 0, UIntPtr.Zero); System.Threading.Thread.Sleep(70); mouse_event(0x0004, 0, 0, 0, UIntPtr.Zero); }
}
'@
[void][W]::SetProcessDPIAware()
$cli = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\museum-wallpapers.exe'
function Hold($s) { Start-Sleep -Milliseconds ([int]($s * 1000)) }
function Glide($x, $y, $s) {   # ease-in-out, 120 steps a second
    $p = New-Object W+POINT; [void][W]::GetCursorPos([ref]$p)
    $n = [math]::Max(1, [int]($s * 120))
    for ($i = 1; $i -le $n; $i++) {
        $t = $i / $n; $e = if ($t -lt 0.5) { 4 * $t * $t * $t } else { 1 - [math]::Pow(-2 * $t + 2, 3) / 2 }
        [void][W]::SetCursorPos([int]($p.X + ($x - $p.X) * $e), [int]($p.Y + ($y - $p.Y) * $e))
        Start-Sleep -Milliseconds 8
    }
}
function CardRect { [W]::Card([uint32[]]@(Get-Process MuseumWallpapers -ErrorAction SilentlyContinue | ForEach-Object Id)) }
function WaitCard($open, $max = 3) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $max) { $r = CardRect; if ((($r.Right - $r.Left) -gt 0) -eq $open) { return $r }; Start-Sleep -Milliseconds 30 }
    return (CardRect)
}
# Inside the card, in units of its width (measured on the 0.1.7 card): Next sits 16% in and
# 20% of the width above the bottom edge; the close button 6% from the right, 5% below the top.
function NextPoint($r) { $w = $r.Right - $r.Left; @([int]($r.Left + 0.16 * $w), [int]($r.Bottom - 0.20 * $w)) }
function ClosePoint($r) { $w = $r.Right - $r.Left; @([int]($r.Right - 0.058 * $w), [int]($r.Top + 0.05 * $w)) }
$rest = @(2300, 1150)
try {
    Hold 6                                                       # Claude lets go of the screen first
    $shell = New-Object -ComObject Shell.Application
    foreach ($i in 1..4) { $shell.MinimizeAll(); Hold 1.5 }
    [void][W]::SetCursorPos($rest[0], $rest[1]); Hold 0.5
    $out = Join-Path $demo "dda-$Lang-$(Get-Date -Format HHmmss).mkv"
    $rec = Start-Process -PassThru -WindowStyle Hidden -FilePath (Join-Path $demo 'ffmpeg.exe') -ArgumentList @(
        '-hide_banner', '-y', '-f', 'lavfi', '-i', 'ddagrab=output_idx=0:framerate=60:draw_mouse=1', '-t', "$Seconds",
        '-c:v', 'h264_nvenc', '-cq', '12', '-g', '60', "`"$out`"")
    Hold 1.2; Mark "recording-$Lang"
    $log = @()
    foreach ($round in 1..2) {
        Hold 1.5                                                 # the painting with its label
        Start-Process -FilePath $cli                             # the card opens as the cursor arrives
        Glide $Tray[0] $Tray[1] 0.6
        $r = WaitCard $true; $log += "card $round $($r.Left),$($r.Top),$($r.Right),$($r.Bottom)"
        Hold 1.0
        $n = NextPoint $r; Glide $n[0] $n[1] 0.5; Hold 0.35; [W]::Click()   # Next
        Hold 2.2                                                 # the new painting, its card follows
        $r = CardRect; $c = ClosePoint $r; Glide $c[0] $c[1] 0.45; Hold 0.2; [W]::Click()   # close
        Hold 0.15; Glide $rest[0] $rest[1] 0.6
        if ((CardRect).Right -gt 0) { $log += "card $round still open after close" }
    }
    Hold 1.8
    $rec.WaitForExit()
    $log | Set-Content (Join-Path $demo "take2-$Lang-points.log")
    Mark "recorded-$Lang $out"
} catch { Mark "error $($_.Exception.Message)" } finally { Stop-Transcript | Out-Null }
