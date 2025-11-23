#!/bin/bash

# --- ROTUP Linux Installation Script (v2.0 English) ---

INSTALL_DIR="/opt/rotup"
PYTHON_BIN="/usr/bin/python3"

echo "--- Starting ROTUP v2.0 Installation ---"

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root: sudo ./install.sh"
  exit 1
fi

echo "Installing dependencies: python3, pip, ntfs-3g, zip, python3-tk, python3-psutil..."
apt update
apt install python3 python3-pip ntfs-3g zip python3-tk python3-psutil -y

echo "Creating installation directory: $INSTALL_DIR..."
mkdir -p $INSTALL_DIR

if [ ! -f "rotup.py" ]; then
    echo "ERROR: rotup.py must be in the same directory as install.sh!"
    exit 1
fi

echo "Copying files..."
cp rotup.py $INSTALL_DIR/
if [ -f "config.json" ]; then
    cp config.json $INSTALL_DIR/
fi

# Default directories
LOG_DIR="/var/log/rotup"
MOUNT_POINT="/mnt/rotup_usb"

echo "Creating system directories..."
mkdir -p $LOG_DIR
chmod 777 $LOG_DIR
mkdir -p $MOUNT_POINT
chmod 777 $MOUNT_POINT

chmod +x $INSTALL_DIR/rotup.py

# Cron configuration
CRON_JOB="0 1 * * * $PYTHON_BIN $INSTALL_DIR/rotup.py --cron"

echo "Setting up Cron job (1:00 AM daily)..."
(crontab -l 2>/dev/null | grep -v "$INSTALL_DIR/rotup.py") | crontab -
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo ""
echo "--- INSTALLATION COMPLETE! ---"
echo "NEXT STEP: Run the program manually to configure disks via GUI."
echo "Command: sudo python3 $INSTALL_DIR/rotup.py"