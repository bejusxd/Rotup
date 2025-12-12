#!/bin/bash
# ROTUP - Linux Installer
# Usage: curl -sSL https://raw.githubusercontent.com/bejusxd/Rotup/main/install_rotup.sh | sudo bash
# Or: sudo bash install_rotup.sh

set -e

echo "========================================"
echo "ROTUP v0.7 alpha - Rotation Backup Tool"
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
    ubuntu|debian|linuxmint|pop)
        apt-get update
        apt-get install -y python3 python3-pip python3-tk zip ntfs-3g curl wget
        ;;
    fedora|rhel|centos)
        dnf install -y python3 python3-pip python3-tkinter zip ntfs-3g curl wget
        ;;
    arch|manjaro)
        pacman -Sy --noconfirm python python-pip tk zip ntfs-3g curl wget
        ;;
    *)
        echo "⚠️  Unknown distribution, attempting universal install..."
        apt-get install -y python3 python3-pip python3-tk zip ntfs-3g curl wget || \
        dnf install -y python3 python3-pip python3-tkinter zip ntfs-3g curl wget || \
        pacman -Sy --noconfirm python python-pip tk zip ntfs-3g curl wget
        ;;
esac

# Install Python psutil library
echo "🐍 Installing psutil library..."
pip3 install --break-system-packages psutil 2>/dev/null || pip3 install psutil

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

# Create wrapper script that runs WITHOUT terminal
echo "🔧 Creating launcher script..."
cat > "$INSTALL_DIR/rotup-gui.sh" << 'EOFSCRIPT'
#!/bin/bash
# ROTUP GUI Launcher (no terminal)
cd /opt/rotup
nohup python3 /opt/rotup/rotup.py > /dev/null 2>&1 &
EOFSCRIPT

chmod +x "$INSTALL_DIR/rotup-gui.sh"

# Create symbolic link for command line
echo "🔗 Creating symbolic links..."
ln -sf "$INSTALL_DIR/rotup.py" /usr/local/bin/rotup-cli
ln -sf "$INSTALL_DIR/rotup-gui.sh" /usr/local/bin/rotup

# Create .desktop file for application menu (FIXED - no terminal!)
DESKTOP_FILE="/usr/share/applications/rotup.desktop"
echo "🖥️  Creating application menu shortcut..."
cat > "$DESKTOP_FILE" << 'EOFDESKTOP'
[Desktop Entry]
Version=1.0
Type=Application
Name=ROTUP Backup
Comment=Rotation Backup Tool
Exec=/opt/rotup/rotup-gui.sh
Icon=drive-harddisk
Terminal=false
Categories=Utility;System;Archiving;
StartupNotify=false
EOFDESKTOP

chmod 644 "$DESKTOP_FILE"

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database /usr/share/applications
fi

# Create autostart entry (optional, disabled by default)
AUTOSTART_DIR="/etc/xdg/autostart"
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/rotup-autostart.desktop.disabled" << 'EOFAUTOSTART'
[Desktop Entry]
Type=Application
Name=ROTUP Backup (Autostart)
Comment=Start ROTUP backup tool on login
Exec=/opt/rotup/rotup-gui.sh
Icon=drive-harddisk
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
EOFAUTOSTART

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
echo "   - GUI (no terminal): rotup"
echo "   - From application menu: Search 'ROTUP'"
echo "   - CLI with terminal: rotup-cli"
echo "   - Cron mode: python3 $INSTALL_DIR/rotup.py --cron"
echo ""
echo "⏰ To enable automatic backup (daily at 2:00 AM):"
echo "   1. Run: rotup"
echo "   2. Click SETTINGS"
echo "   3. Enable 'Automatic Backup' checkbox"
echo "   4. Click SAVE"
echo ""
echo "🎯 To enable autostart on login (optional):"
echo "   sudo mv $AUTOSTART_DIR/rotup-autostart.desktop.disabled \\"
echo "        $AUTOSTART_DIR/rotup-autostart.desktop"
echo ""
echo "🎉 Done! Find ROTUP in your application menu or run 'rotup'"
echo ""