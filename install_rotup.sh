#!/bin/bash
# ROTUP - Linux Installer
# Usage: curl -sSL https://raw.githubusercontent.com/bejusxd/Rotup/main/install_rotup.sh | bash

set -e

echo "========================================"
echo "ROTUP v2.0 - Rotation Backup Tool"
echo "Linux Installer"
echo "========================================"

# Check root privileges
if [ "$EUID" -ne 0 ]; then
    echo "❌ Error: This script requires root privileges (sudo)"
    echo "Run again: sudo bash install_rotup.sh"
    exit 1
fi

# Detect distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    echo "❌ Cannot detect Linux distribution"
    exit 1
fi

echo "📋 Detected distribution: $DISTRO"

# Install dependencies
echo "📦 Installing dependencies..."

case $DISTRO in
    ubuntu|debian|linuxmint)
        apt-get update
        apt-get install -y python3 python3-pip python3-tk zip ntfs-3g
        ;;
    fedora|rhel|centos)
        dnf install -y python3 python3-pip python3-tkinter zip ntfs-3g
        ;;
    arch|manjaro)
        pacman -Sy --noconfirm python python-pip tk zip ntfs-3g
        ;;
    *)
        echo "⚠️  Unknown distribution, attempting universal install..."
        apt-get install -y python3 python3-pip python3-tk zip ntfs-3g || \
        dnf install -y python3 python3-pip python3-tkinter zip ntfs-3g || \
        pacman -Sy --noconfirm python python-pip tk zip ntfs-3g
        ;;
esac

# Install Python psutil library
echo "🐍 Installing psutil library..."
pip3 install psutil

# Create installation directory
INSTALL_DIR="/opt/rotup"
echo "📁 Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Download rotup.py file
echo "⬇️  Downloading ROTUP..."
if command -v curl &> /dev/null; then
    curl -sSL https://raw.githubusercontent.com/bejusxd/Rotup/main/rotup.py -o "$INSTALL_DIR/rotup.py"
elif command -v wget &> /dev/null; then
    wget -q https://raw.githubusercontent.com/bejusxd/Rotup/main/rotup.py -O "$INSTALL_DIR/rotup.py"
else
    echo "❌ Error: Neither curl nor wget found. Install one of them."
    exit 1
fi

# Grant execution permissions
chmod +x "$INSTALL_DIR/rotup.py"

# Create mount point
MOUNT_POINT="/mnt/rotup_usb"
echo "📁 Creating mount point: $MOUNT_POINT"
mkdir -p "$MOUNT_POINT"

# Create log directory
LOG_DIR="/var/log/rotup"
echo "📁 Creating log directory: $LOG_DIR"
mkdir -p "$LOG_DIR"
chmod 755 "$LOG_DIR"

# Create symbolic link in /usr/local/bin
echo "🔗 Creating symbolic link..."
ln -sf "$INSTALL_DIR/rotup.py" /usr/local/bin/rotup

# Create .desktop file for application menu
DESKTOP_FILE="/usr/share/applications/rotup.desktop"
echo "🖥️  Creating application menu shortcut..."
cat > "$DESKTOP_FILE" << 'EOF'
[Desktop Entry]
Version=2.0
Type=Application
Name=ROTUP Backup
Comment=Rotation Backup Tool
Exec=python3 /opt/rotup/rotup.py
Icon=drive-harddisk
Terminal=false
Categories=Utility;System;
EOF

# Optionally: Add cron job (commented by default)
echo "⏰ Configuring cron (optional)..."
CRON_ENTRY="# 0 2 * * * /usr/bin/python3 $INSTALL_DIR/rotup.py --cron"
(crontab -l 2>/dev/null | grep -v "rotup.py --cron"; echo "$CRON_ENTRY") | crontab -

echo ""
echo "✅ ============================================"
echo "✅ ROTUP installed successfully!"
echo "✅ ============================================"
echo ""
echo "📍 Location: $INSTALL_DIR/rotup.py"
echo "📍 Mount point: $MOUNT_POINT"
echo "📍 Logs: $LOG_DIR"
echo ""
echo "🚀 Launch:"
echo "   - With GUI: rotup (or find in application menu)"
echo "   - From console: python3 $INSTALL_DIR/rotup.py"
echo "   - Cron mode: python3 $INSTALL_DIR/rotup.py --cron"
echo ""
echo "⏰ To enable automatic backup (daily at 2:00 AM):"
echo "   Run: crontab -e"
echo "   Uncomment the line with 'rotup.py --cron' (remove #)"
echo ""
echo "🎉 Done! Run 'rotup' to configure your backup."
echo ""