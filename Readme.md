# 🔄 ROTUP - Rotation Backup Tool

![Version](https://img.shields.io/badge/version-v0.7.1-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

**ROTUP** is a lightweight, cross-platform backup utility designed specifically for **disk rotation strategies**. It automatically detects which backup drive is currently connected (based on Label/UUID) and performs a compressed backup of selected folders.

It features a modern GUI for configuration and a headless mode for automated scheduled backups.

---

## ✨ Key Features

* **💿 Smart Disk Detection**: Automatically identifies authorized backup drives (USB/HDD) regardless of their drive letter or mount point.
* **🐧 Cross-Platform**: Works seamlessly on **Windows** (via PowerShell/Task Scheduler) and **Linux** (via Bash/Cron).
* **🗜️ Efficient Compression**: Creates standard `.zip` archives containing your source data + execution logs.
* **⏰ Automated Scheduling**: Built-in scheduler configuration (Windows Task Scheduler & Linux Crontab).
* **🖥️ Modern GUI**: User-friendly interface (Tkinter) to manage source folders and trusted disks.
* **🧵 Thread-Safe**: Responsive interface with real-time logging during backup operations.

---

## 🚀 Installation

### 🪟 Windows

1. Download the repository or just the `install_rotup.ps1` file.
2. Right-click `install_rotup.ps1` and select **"Run with PowerShell"**.
   * *Note: You must run this as Administrator.*
3. The script will:
   * Install Python dependencies (`psutil`).
   * Create shortcuts on Desktop and Start Menu.
   * Set up the automatic daily task.

### 🐧 Linux

Use the automatic installer script. Run the following command in your terminal:

    curl -sSL https://raw.githubusercontent.com/bejusxd/Rotup/main/install_rotup.sh | sudo bash

Alternatively, clone the repo and run:

    sudo bash install_rotup.sh

---

## 📖 Usage

### GUI Mode (Configuration)
Launch **ROTUP** from your desktop shortcut or via terminal:

    rotup

1. Click **SETTINGS**.
2. **Tab 1 (Sources):** Add the folders you want to back up.
3. **Tab 2 (Disks):** Plug in your USB drive, click "Add Disk", and select it from the list. Repeat for all rotation drives.
4. **Tab 3 (Schedule):** Enable automatic daily backups (default is 02:00 AM).
5. Click **SAVE CONFIGURATION**.

You can also click **START BACKUP** to run an immediate manual backup.

### CLI / Headless Mode (Automation)
ROTUP can run without a window (perfect for cron jobs). The installer sets this up automatically, but you can run it manually:

    # Windows
    python rotup.py --cron

    # Linux
    python3 rotup.py --cron

---

## 🛠️ Building Executable (Windows)

If you want to create a standalone `.exe` file (portable version):

1. Ensure you have `pyinstaller` installed:

       pip install pyinstaller

2. Run the build script:

       python install_rotup.py

3. The executable will be available in the `dist/` folder.

---

## 📂 Project Structure

* `rotup.py` - Main application core (GUI + Logic).
* `config.json` - Stores user settings (paths, disk UUIDs, schedule).
* `install_rotup.ps1` - Windows installer & environment setup.
* `install_rotup.sh` - Linux installer & environment setup.
* `install_rotup.py` - Builder script for creating Windows .exe.

---

## 📝 License

This project is open-source. Feel free to modify and distribute.