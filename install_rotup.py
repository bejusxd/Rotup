"""
ROTUP - EXE Builder Script
This script uses PyInstaller to create a standalone Windows executable

Prerequisites:
    pip install pyinstaller

Usage:
    python build_exe.py

Output:
    dist/ROTUP.exe - Standalone executable
"""

import os
import sys
import subprocess
import shutil


def build_exe():
    """Builds Windows executable using PyInstaller"""

    print("=" * 60)
    print("ROTUP v0.6 alpha - Building Windows Executable")
    print("=" * 60)

    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print(f"✅ PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("❌ PyInstaller not found!")
        print("📦 Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller installed successfully")

    # Check if rotup.py exists
    if not os.path.exists("rotup.py"):
        print("❌ Error: rotup.py not found in current directory!")
        return False

    print("\n🔨 Building executable...")

    # PyInstaller command
    # PyInstaller command
    cmd = [
        sys.executable,  # Ścieżka do aktywnego Pythona (C:\Users\Bejoz\...)
        "-m",  # Argument do uruchomienia modułu
        "PyInstaller",
        "--name=ROTUP",  # Output name
        "--name=ROTUP",  # Output name
        "--onefile",  # Single executable file
        "--windowed",  # No console window (GUI only)
        "--icon=NONE",  # No icon (can be added later)
        "--add-data=config.json;." if os.path.exists("config.json") else "",
        "--hidden-import=tkinter",
        "--hidden-import=psutil",
        "--clean",  # Clean cache
        "rotup.py"
    ]

    # Remove empty strings
    cmd = [arg for arg in cmd if arg]

    try:
        subprocess.check_call(cmd)
        print("\n✅ Build completed successfully!")
        print(f"\n📦 Executable location: {os.path.abspath('dist/ROTUP.exe')}")
        print(f"📦 File size: {os.path.getsize('dist/ROTUP.exe') / (1024 * 1024):.2f} MB")

        # Create portable package
        print("\n📦 Creating portable package...")
        package_dir = "dist/ROTUP_Portable"
        os.makedirs(package_dir, exist_ok=True)

        # Copy executable
        shutil.copy2("dist/ROTUP.exe", f"{package_dir}/ROTUP.exe")

        # Create README
        readme_content = """ROTUP v0.6 - Rotation Backup Tool
=====================================

Portable Windows Version

How to Use:
1. Double-click ROTUP.exe to launch
2. Click SETTINGS to configure:
   - Add source folders to backup
   - Select rotation disks
3. Click START BACKUP to run backup

Configuration:
- Settings are saved in config.json (created automatically)
- Logs are saved in ./logs/ directory

Automatic Backup (Optional):
- Use Windows Task Scheduler to run ROTUP.exe with --cron argument
- Example: ROTUP.exe --cron

For more information, visit:
https://github.com/YOUR_REPO/rotup
"""

        with open(f"{package_dir}/README.txt", "w", encoding="utf-8") as f:
            f.write(readme_content)

        # Create sample config
        sample_config = {
            "source_directories": [],
            "disk_rotation": {
                "windows": []
            },
            "logging_directory": "./logs",
            "backup_filename_prefix": "backup"
        }

        import json
        with open(f"{package_dir}/config.json.sample", "w", encoding="utf-8") as f:
            json.dump(sample_config, f, indent=4)

        # Create ZIP archive
        print("📦 Creating ZIP archive...")
        shutil.make_archive("dist/ROTUP_v0.6_Windows_Portable", "zip", "dist", "ROTUP_Portable")

        print("\n✅ ============================================")
        print("✅ Build process completed!")
        print("✅ ============================================")
        print(f"\n📦 Standalone EXE: dist/ROTUP.exe")
        print(f"📦 Portable package: dist/ROTUP_v0.6_Windows_Portable.zip")
        print("\nDistribute the ZIP file for easy deployment!")

        return True

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = build_exe()
    sys.exit(0 if success else 1)