# Tao tac vu Task Scheduler "DangKyPhatSong": chay run.bat khi bat may (khong can ai dang nhap), tai khoan SYSTEM.
# Dung boi setup.bat (can quyen Administrator).
param(
    [int]$Port = 8004,
    [Parameter(Mandatory = $true)][string]$Dir
)
$ErrorActionPreference = 'Stop'
try {
    $Dir = $Dir.TrimEnd('\')
    $action = New-ScheduledTaskAction -Execute (Join-Path $Dir 'run.bat') -Argument "$Port auto" -WorkingDirectory $Dir
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $trigger.Delay = 'PT30S'          # doi 30 giay sau khi bat may cho mang san sang
    # Mac dinh cua Task Scheduler la tu dung tac vu sau 72 gio -> phai tat gioi han nay
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    Register-ScheduledTask -TaskName 'DangKyPhatSong' -Action $action -Trigger $trigger -Settings $settings `
        -Principal $principal -Description 'Web Dang ky phat song (run.bat auto)' -Force | Out-Null
} catch {
    Write-Host "      [loi] $($_.Exception.Message)"
    exit 1
}
