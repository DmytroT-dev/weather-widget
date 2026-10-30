# Starts the widget with Windows: puts a shortcut into the current user's Startup folder.
# No admin rights needed. Remove with: scripts\install-autostart.ps1 -Uninstall
param([switch]$Uninstall)

$project = Split-Path -Parent $PSScriptRoot
$shortcut = Join-Path ([Environment]::GetFolderPath('Startup')) 'Desk Widget.lnk'

if ($Uninstall) {
    Remove-Item $shortcut -ErrorAction SilentlyContinue
    Write-Host "Autostart removed."
    return
}

$pythonw = Join-Path $project '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $pythonw)) {
    Write-Error "Virtual environment not found. Run the setup steps from README.md first."
    exit 1
}

$link = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcut)
$link.TargetPath = $pythonw
$link.Arguments = '"' + (Join-Path $project 'main.pyw') + '"'
$link.WorkingDirectory = $project
$link.Description = 'Weather, pomodoro and Hacker News desktop widget'
$link.Save()
Write-Host "Autostart installed: $shortcut"
