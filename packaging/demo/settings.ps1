# Museum Wallpapers: settings for recording the demo, and back again.
#
#   powershell -ExecutionPolicy Bypass -File packaging\demo\settings.ps1 en       landscapes only, English
#   powershell -ExecutionPolicy Bypass -File packaging\demo\settings.ps1 ru       landscapes only, Russian
#   powershell -ExecutionPolicy Bypass -File packaging\demo\settings.ps1 restore  your own settings back
#
# The first run copies settings.json to settings.json.before-demo; restore puts it back.
# Each run restarts the tray app so it reads the change.

param([Parameter(Mandatory = $true)][ValidateSet('en', 'ru', 'restore')][string]$Mode)
$ErrorActionPreference = 'Stop'

$family = 'dpsk.MuseumWallpapers_9n62pad56wkq8'
$package = Join-Path $env:LOCALAPPDATA "Packages\$family"
$storeCopy = Test-Path $package
# The Store app keeps its settings in its package folder; the GitHub installer's copy in %APPDATA%.
$dir = if ($storeCopy) { Join-Path $package 'LocalCache\MuseumWallpapers\config' } else { Join-Path $env:APPDATA 'MuseumWallpapers' }
$file = Join-Path $dir 'settings.json'
$backup = "$file.before-demo"
$noFile = "$backup.none"            # there was no settings.json before the demo
$utf8 = New-Object System.Text.UTF8Encoding $false   # no BOM: the app's JSON reader rejects one

Get-Process MuseumWallpapers -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

if ($Mode -eq 'restore') {
    if (Test-Path $backup) { Move-Item -Force $backup $file }
    elseif (Test-Path $noFile) { Remove-Item -Force $file -ErrorAction SilentlyContinue; Remove-Item -Force $noFile }
    else { Write-Warning "No backup next to $file; nothing restored." }
} else {
    New-Item -ItemType Directory -Force $dir | Out-Null
    if (-not (Test-Path $backup) -and -not (Test-Path $noFile)) {
        if (Test-Path $file) { Copy-Item $file $backup } else { New-Item -ItemType File $noFile | Out-Null }
    }
    $s = if (Test-Path $file) { [IO.File]::ReadAllText($file, $utf8) | ConvertFrom-Json } else { New-Object psobject }
    if ($null -eq $s) { $s = New-Object psobject }
    $s | Add-Member -Force NoteProperty language $Mode
    $filters = if ($s.filters) { $s.filters } else { New-Object psobject }
    $filters | Add-Member -Force NoteProperty genres @('landscape')
    $s | Add-Member -Force NoteProperty filters $filters
    [IO.File]::WriteAllText($file, ($s | ConvertTo-Json -Depth 10), $utf8)
}

if ($storeCopy) { Start-Process explorer.exe "shell:AppsFolder\$family!App" }
else { Start-Process (Join-Path $env:LOCALAPPDATA 'Programs\Museum Wallpapers\MuseumWallpapers.exe') }

Write-Host "settings: $file"
if (Test-Path $file) { Get-Content -Raw -Encoding UTF8 $file | Write-Host }
if ($Mode -ne 'restore') {
    Write-Host "Wait about a minute (the app downloads 6 landscapes ahead), then press Next once so the old painting is gone."
}
