# ROTUP - Windows Installer (PowerShell)
# Usage: Run as Administrator
# Or: powershell -ExecutionPolicy Bypass -File install_rotup.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ROTUP v2.0 - Rotation Backup Tool" -ForegroundColor Cyan
Write-Host "Windows Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check if running as Administrator
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "❌ Error: This script requires Administrator privileges" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if Python is installed
Write-Host "🔍 Checking for Python installation..." -ForegroundColor Yellow
$pythonPath = $null

try {
    $pythonPath = (Get-Command python -ErrorAction Stop).Source
    $pythonVersion = python --version
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found!" -ForegroundColor Red
    Write-Host "📥 Please install Python 3 from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "    Make sure to check 'Add Python to PATH' during installation!" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Install pip if not present
Write-Host "📦 Checking pip..." -ForegroundColor Yellow
try {
    python -m pip --version | Out-Null
    Write-Host "✅ pip is available" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Installing pip..." -ForegroundColor Yellow
    python -m ensurepip --upgrade
}

# Install psutil library
Write-Host "🐍 Installing psutil library..." -ForegroundColor Yellow
python -m pip install --upgrade psutil

# Create installation directory
$INSTALL_DIR = "C:\Program Files\ROTUP"
Write-Host "📁 Creating installation directory: $INSTALL_DIR" -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null

# Download rotup.py
Write-Host "⬇️  Downloading ROTUP..." -ForegroundColor Yellow
$rotupUrl = "https://raw.githubusercontent.com/bejusxd/Rotup/main/rotup.py"
$rotupPath = Join-Path $INSTALL_DIR "rotup.py"

try {
    Invoke-WebRequest -Uri $rotupUrl -OutFile $rotupPath -UseBasicParsing
    Write-Host "✅ Downloaded rotup.py" -ForegroundColor Green
} catch {
    Write-Host "❌ Error downloading file: $_" -ForegroundColor Red
    Write-Host "Please check your internet connection or the repository URL" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Create log directory
$LOG_DIR = "C:\ProgramData\ROTUP\Logs"
Write-Host "📁 Creating log directory: $LOG_DIR" -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

# Create Start Menu shortcut
Write-Host "🔗 Creating Start Menu shortcut..." -ForegroundColor Yellow
$WshShell = New-Object -ComObject WScript.Shell
$ShortcutPath = "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\ROTUP Backup.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "pythonw.exe"
$Shortcut.Arguments = "`"$rotupPath`""
$Shortcut.WorkingDirectory = $INSTALL_DIR
$Shortcut.IconLocation = "shell32.dll,12"
$Shortcut.Description = "ROTUP - Rotation Backup Tool"
$Shortcut.Save()

# Create Desktop shortcut (optional)
Write-Host "🖥️  Creating Desktop shortcut..." -ForegroundColor Yellow
$DesktopShortcut = "$env:USERPROFILE\Desktop\ROTUP Backup.lnk"
$DesktopLink = $WshShell.CreateShortcut($DesktopShortcut)
$DesktopLink.TargetPath = "pythonw.exe"
$DesktopLink.Arguments = "`"$rotupPath`""
$DesktopLink.WorkingDirectory = $INSTALL_DIR
$DesktopLink.IconLocation = "shell32.dll,12"
$DesktopLink.Description = "ROTUP - Rotation Backup Tool"
$DesktopLink.Save()

# Automatic scheduled task creation (ENABLED by default)
Write-Host "⏰ Creating scheduled task for automatic backup..." -ForegroundColor Yellow
$TaskName = "ROTUP_AutoBackup"
$TaskDescription = "Automatic rotation backup at 2:00 AM daily"
$TaskAction = New-ScheduledTaskAction -Execute "python.exe" -Argument "`"$rotupPath`" --cron" -WorkingDirectory $INSTALL_DIR
$TaskTrigger = New-ScheduledTaskTrigger -Daily -At 2:00AM
$TaskSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 4)
$TaskPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

try {
    # Remove old task if exists
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    # Register new task (ENABLED by default)
    Register-ScheduledTask -TaskName $TaskName -Action $TaskAction -Trigger $TaskTrigger -Settings $TaskSettings -Principal $TaskPrincipal -Description $TaskDescription -Force | Out-Null

    Write-Host "✅ Scheduled task created and ENABLED (daily at 2:00 AM)" -ForegroundColor Green
    Write-Host "   Task runs as SYSTEM account for proper disk access" -ForegroundColor Cyan
} catch {
    Write-Host "⚠️  Could not create scheduled task: $_" -ForegroundColor Yellow
    Write-Host "   You can create it manually in Task Scheduler" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ ============================================" -ForegroundColor Green
Write-Host "✅ ROTUP installed successfully!" -ForegroundColor Green
Write-Host "✅ ============================================" -ForegroundColor Green
Write-Host ""
Write-Host "📍 Location: $INSTALL_DIR\rotup.py" -ForegroundColor Cyan
Write-Host "📍 Logs: $LOG_DIR" -ForegroundColor Cyan
Write-Host ""
Write-Host "🚀 Launch:" -ForegroundColor Yellow
Write-Host "   - From Start Menu: Search for 'ROTUP Backup'" -ForegroundColor White
Write-Host "   - From Desktop: Double-click 'ROTUP Backup' shortcut" -ForegroundColor White
Write-Host "   - From CMD: python `"$rotupPath`"" -ForegroundColor White
Write-Host ""
Write-Host "⏰ Automatic backup: ENABLED (daily at 2:00 AM)" -ForegroundColor Yellow
Write-Host "   To disable:" -ForegroundColor White
Write-Host "   1. Open Task Scheduler" -ForegroundColor White
Write-Host "   2. Find task: $TaskName" -ForegroundColor White
Write-Host "   3. Right-click → Disable" -ForegroundColor White
Write-Host "   To change schedule: Right-click → Properties → Triggers" -ForegroundColor White
Write-Host ""
Write-Host "🎉 Done! Use Start Menu or Desktop shortcut to launch." -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to exit"