# --- ROTUP Windows Installation Script (install.ps1) ---

$installDir = "C:\ProgramData\ROTUP"
$logDir = "C:\ProgramData\ROTUP\Logs" # Domyślny, jeśli config.json zawiedzie
$scriptName = "rotup.py"
$configName = "config.json"

# Uruchamianie tylko z uprawnieniami Administratora
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "--- Uruchamianie z podwyższonymi uprawnieniami (wymagane dla instalacji) ---" -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -File `"$($MyInvocation.MyCommand.Path)`""
    exit
}

Write-Host "--- Rozpoczęcie instalacji programu ROTUP na Windows ---" -ForegroundColor Green

# 1. Sprawdzenie instalacji Pythona
$pythonPath = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonPath) {
    Write-Host "BŁĄD: Python nie został znaleziony. Proszę zainstalować Python 3 i upewnić się, że jest w PATH." -ForegroundColor Red
    Read-Host "Naciśnij Enter, aby zakończyć..."
    exit 1
}
Write-Host "Znaleziono Pythona w: $($pythonPath.Source)"

# 2. Instalacja zależności Pythona
Write-Host "Instaluję zależności Pythona (psutil)..."
& $pythonPath.Source -m pip install psutil
if ($LASTEXITCODE -ne 0) {
    Write-Host "BŁĄD: Nie udało się zainstalować psutil." -ForegroundColor Red
    Read-Host "Naciśnij Enter, aby zakończyć..."
    exit 1
}

# 3. Tworzenie katalogów
Write-Host "Tworzę katalog instalacyjny w $installDir..."
New-Item -Path $installDir -ItemType Directory -Force | Out-Null
New-Item -Path $logDir -ItemType Directory -Force | Out-Null # Domyślny log, na wszelki wypadek

# 4. Kopiowanie plików
$sourceDir = $PSScriptRoot
Write-Host "Kopiowanie plików z $sourceDir..."
Copy-Item -Path (Join-Path $sourceDir $scriptName) -Destination $installDir -Force
Copy-Item -Path (Join-Path $sourceDir $configName) -Destination $installDir -Force

# 5. Konfiguracja harmonogramu (Task Scheduler)
$scriptPath = Join-Path $installDir $scriptName
$taskName = "ROTUP_Daily_Backup"

Write-Host "Ustawiam harmonogram Task Scheduler (codziennie o 1:00 w nocy)..."

# Definicja akcji (uruchomienie Pythona ze skryptem i flagą --cron)
# UWAGA: Upewnij się, że ścieżka $pythonPath.Source jest poprawna!
$action = New-ScheduledTaskAction -Execute $pythonPath.Source -Argument "`"$scriptPath`" --cron"

# Definicja wyzwalacza (codziennie o 1:00)
$trigger = New-ScheduledTaskTrigger -Daily -At "01:00 AM"

# Definicja ustawień (uruchamiaj jako SYSTEM, z najwyższymi uprawnieniami)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest

# Rejestracja zadania
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -TaskName $taskName -Description "Daily cross-platform rotation backup script (rotup)." -Force

Write-Host ""
Write-Host "--- INSTALACJA ROTUP ZAKOŃCZONA POMYŚLNIE! ---" -ForegroundColor Green
Write-Host "PROSZĘ ZAPAMIĘTAĆ:"
Write-Host "1. Pliki zostały zainstalowane w: $installDir" -ForegroundColor Yellow
Write-Host "2. Upewnij się, że edytowałeś $installDir\$configName (Etykiety dysków, Ścieżki Windows)." -ForegroundColor Yellow
Write-Host "3. Sprawdź Harmonogram Zadań (Task Scheduler), aby potwierdzić, że zadanie '$taskName' istnieje." -ForegroundColor Yellow
Read-Host "Naciśnij Enter, aby zakończyć..."