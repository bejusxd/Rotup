#!/bin/bash

# --- ROTUP Linux Installation Script ---

INSTALL_DIR="/opt/rotup"
PYTHON_BIN="/usr/bin/python3" # Upewnij się, że to poprawna ścieżka

echo "--- Rozpoczęcie instalacji programu ROTUP ---"

# 1. Sprawdzenie, czy skrypt jest uruchomiony jako root
if [ "$EUID" -ne 0 ]; then
  echo "Proszę uruchomić instalator z sudo: sudo ./install.sh"
  exit 1
fi

# 2. Instalacja wymaganych pakietów
echo "Instaluję wymagane pakiety: python3, pip, ntfs-3g, zip, python3-tk, python3-psutil..."
apt update
apt install python3 python3-pip ntfs-3g zip python3-tk python3-psutil -y

# 3. Tworzenie katalogu instalacyjnego
echo "Tworzę katalog instalacyjny w $INSTALL_DIR..."
mkdir -p $INSTALL_DIR

# 4. Kopiowanie plików (Zakładamy, że config.json i rotup.py są w bieżącym katalogu)
if [ ! -f "rotup.py" ] || [ ! -f "config.json" ]; then
    echo "BŁĄD: Pliki rotup.py i config.json muszą znajdować się w tym samym katalogu co install.sh!"
    exit 1
fi
cp rotup.py $INSTALL_DIR/
cp config.json $INSTALL_DIR/

# 5. Odczytanie ścieżek z config.json
# Używamy prostego grep/awk/tr do parsowania JSON
LOG_DIR=$(grep "logging_directory" $INSTALL_DIR/config.json | awk -F': ' '{print $2}' | tr -d ',"')
MOUNT_POINT=$(grep "target_mount_point_linux" $INSTALL_DIR/config.json | awk -F': ' '{print $2}' | tr -d ',"')

# 6. Tworzenie katalogu logów i punktu montowania
echo "Tworzę katalog logów: $LOG_DIR"
mkdir -p $LOG_DIR
chmod 777 $LOG_DIR

echo "Tworzę punkt montowania: $MOUNT_POINT"
mkdir -p $MOUNT_POINT
chmod 777 $MOUNT_POINT

# 7. Ustawienie uprawnień wykonawczych
chmod +x $INSTALL_DIR/rotup.py

# 8. Konfiguracja Crona
# Używamy --cron, aby uruchomić skrypt bez UI
CRON_JOB="0 1 * * * $PYTHON_BIN $INSTALL_DIR/rotup.py --cron"

echo "Ustawiam harmonogram Cron (codziennie o 1:00 w nocy)..."
(crontab -l 2>/dev/null | grep -v "$INSTALL_DIR/rotup.py") | crontab -
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo ""
echo "--- INSTALACJA ROTUP ZAKOŃCZONA POMYŚLNIE! ---"
echo "PROSZĘ ZAPAMIĘTAĆ:"
echo "1. Pliki zostały zainstalowane w: $INSTALL_DIR"
echo "2. Upewnij się, że edytowałeś $INSTALL_DIR/config.json (UUID, Ścieżki)."
echo "3. Logi znajdziesz w: $LOG_DIR"