# Starts the widget with Windows via a Task Scheduler task for the current user.
# Triggers: logon, session unlock and wake from sleep. A Startup-folder shortcut only runs at logon,
# so after sleep a closed widget never came back. Duplicates are impossible: the widget holds a
# named mutex and a second copy exits at once (see ui/single_instance.py).
# No admin rights needed. Remove with: scripts\install-autostart.ps1 -Uninstall
param([switch]$Uninstall)

$taskName = 'Desk Widget'
$project = Split-Path -Parent $PSScriptRoot
# The old autostart method; removed on install and uninstall so the widget is not set up twice.
$legacyShortcut = Join-Path ([Environment]::GetFolderPath('Startup')) 'Desk Widget.lnk'

Remove-Item $legacyShortcut -ErrorAction SilentlyContinue

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Autostart removed."
    return
}

$pythonw = Join-Path $project '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $pythonw)) {
    Write-Error "Virtual environment not found. Run the setup steps from README.md first."
    exit 1
}

$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$esc = [System.Security.SecurityElement]   # XML-escapes paths, e.g. a user name with '&'
$mainPyw = Join-Path $project 'main.pyw'

# XML because the wake-from-sleep trigger is an event trigger, which the ScheduledTasks cmdlets
# cannot build. Power-Troubleshooter event 1 = "the system has returned from a low power state".
$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Weather, pomodoro and Hacker News desktop widget</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>$($esc::Escape($user))</UserId>
    </LogonTrigger>
    <SessionStateChangeTrigger>
      <Enabled>true</Enabled>
      <StateChange>SessionUnlock</StateChange>
      <UserId>$($esc::Escape($user))</UserId>
    </SessionStateChangeTrigger>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Delay>PT10S</Delay>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;Select Path="System"&gt;*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
    </EventTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$($esc::Escape($user))</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <StartWhenAvailable>false</StartWhenAvailable>
    <AllowHardTerminate>true</AllowHardTerminate>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$($esc::Escape($pythonw))</Command>
      <Arguments>"$($esc::Escape($mainPyw))"</Arguments>
      <WorkingDirectory>$($esc::Escape($project))</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

Register-ScheduledTask -TaskName $taskName -Xml $xml -Force | Out-Null
Write-Host "Autostart installed: Task Scheduler task '$taskName' (logon, unlock, wake from sleep)."
