# --- ROTUP Windows Installation Script (v2.0 English) ---

$installDir = "C:\ProgramData\ROTUP"
$logDir = "C:\ProgramData\ROTUP\Logs"
$scriptName = "rotup.py"
$configName = "config.json"

# Check for Administrator privileges
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "--- Running with elevated privileges (Admin required) ---" -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -File `"$($MyInvocation.MyCommand.Path)`""
    exit
}

Write-Host "--- Starting ROTUP v2.0 Installation on Windows ---" -ForegroundColor Green

# 1. Check Python
$pythonPath = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonPath) {
    Write-Host "ERROR: Python not found. Please install Python 3 and add to PATH." -ForegroundColor Red
    Read-Host "Press Enter to exit..."
    exit 1
}
Write-Host "Python found at: $($pythonPath.Source)"

# 2. Install Dependencies
Write-Host "Installing Python dependencies (psutil)..."
& $pythonPath.Source -m pip install psutil
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install psutil." -ForegroundColor Red
    Read-Host "Press Enter to exit..."
    exit 1
}

# 3. Create Directories
Write-Host "Creating directories in $installDir..."
New-Item -Path $installDir -ItemType Directory -Force | Out-Null
New-Item -Path $logDir -ItemType Directory -Force | Out-Null

# 4. Copy Files
$sourceDir = $PSScriptRoot
Write-Host "Copying files from $sourceDir..."
Copy-Item -Path (Join-Path $sourceDir $scriptName) -Destination $installDir -Force
if (Test-Path (Join-Path $sourceDir $configName)) {
    Copy-Item -Path (Join-Path $sourceDir $configName) -Destination $installDir -Force
}

# 5. Task Scheduler
$scriptPath = Join-Path $installDir $scriptName
$taskName = "ROTUP_Daily_Backup"

Write-Host "Configuring Task Scheduler (Daily at 01:00 AM)..."

$action = New-ScheduledTaskAction -Execute $pythonPath.Source -Argument "`"$scriptPath`" --cron"
$trigger = New-ScheduledTaskTrigger -Daily -At "01:00 AM"
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -TaskName $taskName -Description "Daily cross-platform rotation backup script (rotup)." -Force

Write-Host ""
Write-Host "--- ROTUP INSTALLATION COMPLETED SUCCESSFULLY! ---" -ForegroundColor Green
Write-Host "NEXT STEP: Go to $installDir and run rotup.py to configure disks." -ForegroundColor Yellow
Read-Host "Press Enter to exit..."