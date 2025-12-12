import platform
import json
import sys
import os
import subprocess
import datetime
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
import traceback

# --- GLOBALS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
CONFIG = {}
LOG_FILE = ""
BACKUP_FILENAME = ""
TEXT_WIDGET = None

# Check psutil availability with clear error message
try:
    import psutil

    # CRITICAL: Uruchomienie bez terminala na Windows
    if platform.system() == "Windows":
        import ctypes
        import sys

        # Ukryj okno konsoli jeśli uruchomiono z pythonw.exe
        if sys.executable.endswith("pythonw.exe"):
            kernel32 = ctypes.WinDLL('kernel32')
            user32 = ctypes.WinDLL('user32')
            SW_HIDE = 0
            hWnd = kernel32.GetConsoleWindow()
            if hWnd:
                user32.ShowWindow(hWnd, SW_HIDE)

    print(f"[DEBUG] psutil loaded successfully (version: {psutil.__version__})")
except ImportError as e:
    print(f"FATAL ERROR: Missing 'psutil' library. Install via: pip install psutil")
    print(f"[DEBUG] Import error details: {e}")
    input("Press Enter to exit...")
    sys.exit(1)


# === HIDE TERMINAL WINDOW (CROSS-PLATFORM) ===
def hide_terminal():
    """Hide console window on both Windows and Linux"""
    system = platform.system()

    if system == "Windows":
        # Windows: Hide console window
        try:
            import ctypes
            kernel32 = ctypes.WinDLL('kernel32')
            user32 = ctypes.WinDLL('user32')
            SW_HIDE = 0
            hWnd = kernel32.GetConsoleWindow()
            if hWnd:
                user32.ShowWindow(hWnd, SW_HIDE)
        except Exception as e:
            print(f"[DEBUG] Could not hide Windows terminal: {e}")

    elif system == "Linux":
        # Linux: Redirect stdout/stderr to /dev/null if not in cron mode
        if '--cron' not in sys.argv and '--debug' not in sys.argv:
            try:
                # Tylko jeśli nie jesteśmy w trybie cron lub debug
                sys.stdout = open(os.devnull, 'w')
                sys.stderr = open(os.devnull, 'w')
            except Exception as e:
                pass  # Ignoruj błędy


# Wywołaj ukrywanie terminala (NIE w trybie cron!)
if '--cron' not in sys.argv and '--debug' not in sys.argv:
    hide_terminal()

# --- CONFIGURATION HANDLING ---

def load_config():
    """Loads configuration from JSON file or returns empty dict"""
    global CONFIG
    print(f"[DEBUG] Attempting to load configuration from: {CONFIG_FILE}")
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                CONFIG = json.load(f)
            print(f"[DEBUG] Configuration loaded successfully: {len(CONFIG)} keys")
            return True
        except Exception as e:
            print(f"[DEBUG] Error loading config.json: {e}")
            traceback.print_exc()
            return False
    else:
        print(f"[DEBUG] Configuration file does not exist, will be created on save")
        CONFIG = {}
    return False


def save_config(new_config):
    """Saves configuration to JSON file"""
    global CONFIG
    try:
        print(f"[DEBUG] Saving configuration to: {CONFIG_FILE}")
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_config, f, indent=4, ensure_ascii=False)
        CONFIG = new_config
        print(f"[DEBUG] Configuration saved successfully")
        return True
    except Exception as e:
        error_msg = f"Failed to save config.json: {e}"
        print(f"[DEBUG] {error_msg}")
        traceback.print_exc()
        messagebox.showerror("Save Error", error_msg)
        return False


# --- DISK DETECTION ---

def get_available_disks_linux():
    """Detects available disks on Linux system"""
    disks = []
    try:
        print("[DEBUG] Linux: Detecting disks via lsblk...")
        cmd = ['lsblk', '-o', 'NAME,LABEL,UUID,FSTYPE,MOUNTPOINT', '-P']
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE)
        for line in output.splitlines():
            props = {}
            for part in line.split():
                if '=' in part:
                    key, value = part.split('=', 1)
                    props[key] = value.strip('"')
            if props.get('UUID'):
                name = f"{props.get('LABEL', 'NO_LABEL')} ({props.get('UUID')})"
                disks.append({
                    'display': name,
                    'value': f"{props.get('LABEL', 'DISK')}_{props.get('UUID')}",
                    'raw_uuid': props.get('UUID')
                })
        print(f"[DEBUG] Linux: Found {len(disks)} disks")
    except Exception as e:
        print(f"[DEBUG] Linux disk detection error: {e}")
        traceback.print_exc()
    return disks


def get_available_disks_windows():
    """Detects available disks on Windows system"""
    disks = []
    try:
        print("[DEBUG] Windows: Detecting disks via psutil...")
        partitions = psutil.disk_partitions()
        print(f"[DEBUG] psutil.disk_partitions() returned {len(partitions)} partitions")

        for part in partitions:
            print(f"[DEBUG] Checking partition: {part.device}, opts: {part.opts}")
            if 'removable' in part.opts or 'cdrom' not in part.opts:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    label = ""
                    try:
                        drive_letter = part.device.rstrip('\\').rstrip(':')
                        # FIX: Dodaj encoding='utf-8' i errors='ignore'
                        cmd = f"(Get-Volume -DriveLetter '{drive_letter}').FileSystemLabel"
                        print(f"[DEBUG] Executing PowerShell: {cmd}")
                        result = subprocess.check_output(
                            ['powershell', '-Command', cmd],
                            text=True,
                            encoding='utf-8',  # NOWE
                            errors='ignore',    # NOWE - ignoruj błędy dekodowania
                            stderr=subprocess.PIPE,
                            timeout=5
                        )
                        label = result.strip()
                        print(f"[DEBUG] Label for {drive_letter}: '{label}'")
                    except subprocess.TimeoutExpired:
                        print(f"[DEBUG] Timeout getting label for {part.device}")
                    except Exception as label_err:
                        print(f"[DEBUG] Cannot get label for {part.device}: {label_err}")

                    name = f"Drive {part.device} - {label if label else 'No Label'} [{part.fstype}]"
                    value = label if label else part.device
                    disks.append({'display': name, 'value': value})
                    print(f"[DEBUG] Added disk: {name}")
                except PermissionError:
                    print(f"[DEBUG] No access to {part.mountpoint}")
                except Exception as disk_err:
                    print(f"[DEBUG] Error with disk {part.device}: {disk_err}")
                    continue
        print(f"[DEBUG] Windows: Found {len(disks)} disks")
    except Exception as e:
        print(f"[DEBUG] Windows disk detection error: {e}")
        traceback.print_exc()
    return disks


# --- LOGGING AND COMMANDS ---

def initialize_logging():
    """Initializes logging system"""
    global LOG_FILE, BACKUP_FILENAME
    log_dir = CONFIG.get('logging_directory', './logs')
    prefix = CONFIG.get('backup_filename_prefix', 'backup')
    current_date = datetime.datetime.now().strftime("%Y_%m_%d")
    try:
        os.makedirs(log_dir, exist_ok=True)
        print(f"[DEBUG] Log directory: {log_dir}")
    except Exception as e:
        print(f"[DEBUG] Cannot create log directory: {e}")
    LOG_FILE = os.path.join(log_dir, f"{prefix}_{current_date}.log")
    BACKUP_FILENAME = f"{prefix}_{current_date}.zip"
    print(f"[DEBUG] Log file: {LOG_FILE}")
    print(f"[DEBUG] Backup filename: {BACKUP_FILENAME}")


def log_message(message, level="INFO"):
    """Logs message to file and displays in GUI"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {level}: {message}\n"
    print(log_entry.strip())
    if LOG_FILE:
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"[DEBUG] Cannot write to log: {e}")
    if TEXT_WIDGET:
        try:
            TEXT_WIDGET.insert(tk.END, log_entry)
            TEXT_WIDGET.see(tk.END)
        except Exception as e:
            print(f"[DEBUG] Cannot update GUI: {e}")


def run_command(command, error_message):
    """Executes system command"""
    try:
        log_message(f"CMD: {' '.join(command)}")
        subprocess.run(command, capture_output=True, text=True, check=True)
        return True
    except Exception as e:
        log_message(f"{error_message}: {e}", "ERROR")
        return False


def run_powershell_command(command, error_message):
    """Executes PowerShell command"""
    try:
        log_message(f"PS: {command}")
        subprocess.run(
            ['powershell', '-Command', command],
            capture_output=True,
            text=True,
            encoding='utf-8',    # NOWE
            errors='ignore',      # NOWE
            check=True
        )
        return True
    except Exception as e:
        log_message(f"{error_message}: {e}", "ERROR")
        return False

# --- LOGIC: LINUX ---

def find_and_mount_linux():
    """Finds and mounts rotation disk on Linux"""
    log_message("Linux: Searching for rotation disk...", "INFO")

    mount_point = CONFIG.get('target_mount_point_linux', '/mnt/rotup_usb')

    # Sprawdź czy punkt montowania już istnieje i jest zamontowany
    try:
        mount_output = subprocess.check_output(['mount'], text=True)
        if mount_point in mount_output:
            log_message(f"Mount point {mount_point} already in use, unmounting...", "WARN")
            subprocess.run(['umount', mount_point], stderr=subprocess.DEVNULL)
    except:
        pass

    try:
        blkid_output = subprocess.check_output(['blkid'], text=True).strip()
    except Exception as e:
        log_message(f"Missing permissions or 'blkid' tool: {e}", "FATAL")
        return None

    found_uuid = None
    linux_disks = CONFIG.get('disk_rotation', {}).get('linux', [])

    log_message(f"Checking for disks: {', '.join(linux_disks)}", "INFO")

    for full_uuid_entry in linux_disks:
        uuid = full_uuid_entry.split('_')[-1]
        if uuid in blkid_output:
            found_uuid = uuid
            log_message(f"Found disk from list: {full_uuid_entry}", "INFO")
            break

    if not found_uuid:
        log_message("No defined disk found.", "ERROR")
        return None

    # Ensure mount point exists
    try:
        os.makedirs(mount_point, exist_ok=True)
    except Exception as e:
        log_message(f"Cannot create mount point: {e}", "ERROR")
        return None

    mount_cmd = [
        'mount', '-t', 'ntfs-3g',
        '-o',
        f"defaults,uid={CONFIG.get('linux_user_uid', 1000)},gid={CONFIG.get('linux_user_gid', 1000)},remove_hiberfile,rw,exec",
        f'UUID={found_uuid}', mount_point
    ]

    log_message(f"Mounting disk to {mount_point}...", "INFO")
    if not run_command(mount_cmd, f"Mount error UUID={found_uuid}"):
        return None

    log_message("Disk mounted successfully", "INFO")
    return mount_point


def backup_logic_linux(mount_path):
    """Performs backup on Linux system"""
    log_message("Starting Linux backup process...", "INFO")
    source_dirs = CONFIG.get('source_directories', [])
    if not source_dirs:
        log_message("No source directories configured!", "ERROR")
        return False

    target = os.path.join(mount_path, BACKUP_FILENAME)
    log_message(f"Target file: {target}", "INFO")
    log_message(f"Source directories: {', '.join(source_dirs)}", "INFO")

    # Build zip command with multiple sources
    zip_cmd = ['zip', '-r', '-9', target] + source_dirs

    log_message("Creating ZIP archive...", "INFO")
    if not run_command(zip_cmd, "ZIP Error"):
        # Unmount nawet po błędzie
        subprocess.run(['umount', mount_path], stderr=subprocess.DEVNULL)
        return False

    log_message("Verifying ZIP archive...", "INFO")
    if not run_command(['zip', '-T', target], "ZIP Verification Error"):
        subprocess.run(['umount', mount_path], stderr=subprocess.DEVNULL)
        return False

    # Skopiuj log do archiwum ZIP
    if LOG_FILE and os.path.exists(LOG_FILE):
        log_message("Adding log file to archive...", "INFO")
        subprocess.run(['zip', '-u', target, LOG_FILE], stderr=subprocess.DEVNULL)

    log_message("Unmounting disk...", "INFO")
    unmount_result = subprocess.run(['umount', mount_path], capture_output=True, text=True)
    if unmount_result.returncode == 0:
        log_message("Disk unmounted successfully", "INFO")
    else:
        log_message(f"Unmount warning: {unmount_result.stderr}", "WARN")

    return True

# --- LOGIC: WINDOWS ---

def backup_logic_windows():
    """Performs backup on Windows system"""
    log_message("Starting Windows backup process...", "INFO")
    found_letter = None
    windows_labels = CONFIG.get('disk_rotation', {}).get('windows', [])

    if not windows_labels:
        log_message("No Windows disks configured in rotation list!", "ERROR")
        return False

    log_message(f"Looking for disks: {', '.join(windows_labels)}", "INFO")

    for part in psutil.disk_partitions():
        try:
            drive_letter = part.device.rstrip('\\').rstrip(':')
            cmd = f"(Get-Volume -DriveLetter '{drive_letter}').FileSystemLabel"
            label = subprocess.check_output(
                ['powershell', '-Command', cmd],
                text=True,
                encoding='utf-8',  # NOWE
                errors='ignore',  # NOWE
                stderr=subprocess.PIPE,
                timeout=5
            ).strip()
            print(f"[DEBUG] Checking disk {drive_letter}: label='{label}'")
            if label in windows_labels:
                found_letter = drive_letter
                log_message(f"Found backup disk: {label} ({found_letter}:)", "INFO")
                break
        except Exception as e:
            print(f"[DEBUG] Error checking {part.device}: {e}")
            continue

    if not found_letter:
        log_message("No disk from the rotation list found.", "ERROR")
        return False

    source_dirs = CONFIG.get('source_directories', [])
    if not source_dirs:
        log_message("No source directories configured!", "ERROR")
        return False

    target = os.path.join(f"{found_letter}:\\", BACKUP_FILENAME)
    log_message(f"Target file: {target}", "INFO")
    log_message(f"Source directories: {', '.join(source_dirs)}", "INFO")

    # Convert paths to Windows format
    sources_win = [s.replace('/', '\\') for s in source_dirs]
    sources_str = "', '".join(sources_win)

    log_message("Creating ZIP archive...", "INFO")
    cmd = f"Compress-Archive -Path '{sources_str}' -DestinationPath '{target}' -Force"

    if not run_powershell_command(cmd, "PowerShell Compression Error"):
        return False

    # Dodaj log do archiwum
    if LOG_FILE and os.path.exists(LOG_FILE):
        log_message("Adding log file to archive...", "INFO")
        log_win = LOG_FILE.replace('/', '\\')
        add_log_cmd = f"Compress-Archive -Path '{log_win}' -Update -DestinationPath '{target}'"
        subprocess.run(['powershell', '-Command', add_log_cmd],
                       capture_output=True, stderr=subprocess.DEVNULL)

    log_message("Backup file created successfully", "INFO")
    return True

# --- UI ---

def open_settings_window(root):
    """Opens settings window"""
    print("[DEBUG] Opening settings window...")
    settings_win = tk.Toplevel(root)
    settings_win.title("ROTUP Configuration")
    settings_win.geometry("750x750")  # Zwiększona wysokość
    settings_win.resizable(True, True)  # Pozwól na zmianę rozmiaru
    settings_win.configure(bg="#f5f5f5")

    # Colors
    COLOR_PRIMARY = "#2196F3"
    COLOR_BG = "#f5f5f5"
    COLOR_CARD = "#ffffff"

    # Header
    header = tk.Frame(settings_win, bg=COLOR_PRIMARY, height=60)
    header.pack(fill=tk.X)
    header.pack_propagate(False)

    tk.Label(
        header,
        text="⚙️ Configuration",
        font=("Arial", 16, "bold"),
        bg=COLOR_PRIMARY,
        fg="white"
    ).pack(side=tk.LEFT, padx=20, pady=15)

    # Main content area
    # Main content area with scrollbar
    content_outer = tk.Frame(settings_win, bg=COLOR_BG)
    content_outer.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # Canvas + Scrollbar
    canvas = tk.Canvas(content_outer, bg=COLOR_BG, highlightthickness=0)
    scrollbar = ttk.Scrollbar(content_outer, orient="vertical", command=canvas.yview)
    content = tk.Frame(canvas, bg=COLOR_BG)

    content.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=content, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Przewijanie myszką
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    # === SECTION: SOURCE FOLDERS ===
    folders_card = tk.Frame(content, bg=COLOR_CARD, relief=tk.FLAT, borderwidth=1)
    folders_card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

    tk.Label(
        folders_card,
        text="📁 Source Folders (to backup):",
        font=("Arial", 11, "bold"),
        bg=COLOR_CARD,
        fg="#333",
        anchor="w"
    ).pack(fill=tk.X, padx=15, pady=(15, 10))

    # Frame with folders list and scrollbar
    folders_frame = tk.Frame(folders_card, relief=tk.FLAT, bg="white", borderwidth=1)
    folders_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

    folders_listbox = tk.Listbox(folders_frame, height=6)
    folders_scrollbar = tk.Scrollbar(folders_frame, orient=tk.VERTICAL, command=folders_listbox.yview)
    folders_listbox.config(yscrollcommand=folders_scrollbar.set)
    folders_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    folders_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Load existing folders
    current_folders = CONFIG.get('source_directories', [])
    for folder in current_folders:
        folders_listbox.insert(tk.END, folder)

    # Buttons for folder management
    folder_buttons_frame = tk.Frame(folders_card, bg=COLOR_CARD)
    folder_buttons_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

    def add_folder():
        path = filedialog.askdirectory(title="Select folder to backup")
        if path:
            # Check if folder already exists
            if path not in folders_listbox.get(0, tk.END):
                folders_listbox.insert(tk.END, path)
            else:
                messagebox.showwarning("Duplicate", "This folder is already in the list!")

    def remove_folder():
        selection = folders_listbox.curselection()
        if selection:
            folders_listbox.delete(selection[0])
        else:
            messagebox.showwarning("No Selection", "Please select a folder to remove!")

    def clear_folders():
        if messagebox.askyesno("Confirm", "Remove all folders from the list?"):
            folders_listbox.delete(0, tk.END)

    tk.Button(folder_buttons_frame, text="➕ Add Folder", command=add_folder, bg="lightgreen").pack(side=tk.LEFT,
                                                                                                   fill=tk.X,
                                                                                                   expand=True, padx=2)
    tk.Button(folder_buttons_frame, text="➖ Remove Selected", command=remove_folder, bg="lightcoral").pack(side=tk.LEFT,
                                                                                                           fill=tk.X,
                                                                                                           expand=True,
                                                                                                           padx=2)
    tk.Button(folder_buttons_frame, text="🗑 Clear All", command=clear_folders, bg="lightgray").pack(side=tk.LEFT,
                                                                                                    fill=tk.X,
                                                                                                    expand=True, padx=2)

    # === SECTION: ROTATION DISKS ===
    disks_card = tk.Frame(content, bg=COLOR_CARD, relief=tk.FLAT, borderwidth=1)
    disks_card.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        disks_card,
        text="💾 Rotating Disks:",
        font=("Arial", 11, "bold"),
        bg=COLOR_CARD,
        fg="#333",
        anchor="w"
    ).pack(fill=tk.X, padx=15, pady=(15, 10))

    # Lista aktualnie dodanych dysków
    disks_list_frame = tk.Frame(disks_card, relief=tk.FLAT, bg="white", borderwidth=1)
    disks_list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

    disks_listbox = tk.Listbox(disks_list_frame, height=6)
    disks_scrollbar = tk.Scrollbar(disks_list_frame, orient=tk.VERTICAL, command=disks_listbox.yview)
    disks_listbox.config(yscrollcommand=disks_scrollbar.set)
    disks_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    disks_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Załaduj aktualnie zapisane dyski
    system_os = platform.system()
    if system_os == "Linux":
        current_disks = CONFIG.get('disk_rotation', {}).get('linux', [])
    else:
        current_disks = CONFIG.get('disk_rotation', {}).get('windows', [])

    for disk in current_disks:
        disks_listbox.insert(tk.END, disk)

    # Przyciski zarządzania dyskami
    disk_buttons_frame = tk.Frame(disks_card, bg=COLOR_CARD)
    disk_buttons_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

    # Wykryj dostępne dyski
    detected_disks = []
    if system_os == "Linux":
        detected_disks = get_available_disks_linux()
    else:
        detected_disks = get_available_disks_windows()

    def add_disk_from_detected():
        """Otwiera okno wyboru dysku"""
        if not detected_disks:
            messagebox.showwarning("No Disks", "No external disks detected!\nPlease connect a USB drive.")
            return

        # Okno wyboru dysku
        select_win = tk.Toplevel(settings_win)
        select_win.title("Select Disk")
        select_win.geometry("500x400")
        select_win.configure(bg="#f5f5f5")

        tk.Label(
            select_win,
            text="Select disk to add:",
            font=("Arial", 11, "bold"),
            bg="#f5f5f5"
        ).pack(padx=20, pady=(20, 10))

        # Lista dysków do wyboru
        select_frame = tk.Frame(select_win, bg="white", relief=tk.FLAT, borderwidth=1)
        select_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        select_listbox = tk.Listbox(select_frame, font=("Arial", 9))
        select_scroll = tk.Scrollbar(select_frame, orient=tk.VERTICAL, command=select_listbox.yview)
        select_listbox.config(yscrollcommand=select_scroll.set)
        select_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        select_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Dodaj dyski do listy (pomijając już dodane)
        disk_map = {}
        current_in_list = list(disks_listbox.get(0, tk.END))

        for disk in detected_disks:
            if disk['value'] not in current_in_list:
                select_listbox.insert(tk.END, disk['display'])
                disk_map[disk['display']] = disk['value']

        if select_listbox.size() == 0:
            select_listbox.insert(tk.END, "All detected disks are already added")
            select_listbox.config(state=tk.DISABLED)

        def confirm_add():
            selection = select_listbox.curselection()
            if selection:
                selected_display = select_listbox.get(selection[0])
                if selected_display in disk_map:
                    disk_value = disk_map[selected_display]
                    disks_listbox.insert(tk.END, disk_value)
                    select_win.destroy()
            else:
                messagebox.showwarning("No Selection", "Please select a disk!")

        btn_frame = tk.Frame(select_win, bg="#f5f5f5")
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        tk.Button(
            btn_frame,
            text="✓ Add Selected",
            command=confirm_add,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            padx=20,
            pady=10
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        tk.Button(
            btn_frame,
            text="✗ Cancel",
            command=select_win.destroy,
            bg="#757575",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            padx=20,
            pady=10
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

    def remove_disk():
        selection = disks_listbox.curselection()
        if selection:
            disks_listbox.delete(selection[0])
        else:
            messagebox.showwarning("No Selection", "Please select a disk to remove!")

    def clear_disks():
        if messagebox.askyesno("Confirm", "Remove all disks from the list?"):
            disks_listbox.delete(0, tk.END)

    tk.Button(
        disk_buttons_frame,
        text="➕ Add Disk",
        command=add_disk_from_detected,
        bg="lightgreen",
        font=("Arial", 9)
    ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

    tk.Button(
        disk_buttons_frame,
        text="➖ Remove Selected",
        command=remove_disk,
        bg="lightcoral",
        font=("Arial", 9)
    ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

    tk.Button(
        disk_buttons_frame,
        text="🗑 Clear All",
        command=clear_disks,
        bg="lightgray",
        font=("Arial", 9)
    ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

    tk.Button(
        disk_buttons_frame,
        text="🔄 Refresh",
        command=lambda: messagebox.showinfo("Refresh", "Please close and reopen Settings to refresh disk list"),
        bg="lightblue",
        font=("Arial", 9)
    ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

    # === SECTION: AUTOMATIC BACKUP ===
    auto_card = tk.Frame(content, bg=COLOR_CARD, relief=tk.FLAT, borderwidth=1)
    auto_card.pack(fill=tk.X, pady=(15, 0))

    tk.Label(
        auto_card,
        text="⏰ Automatic Backup Schedule:",
        font=("Arial", 11, "bold"),
        bg=COLOR_CARD,
        fg="#333",
        anchor="w"
    ).pack(fill=tk.X, padx=15, pady=(15, 10))

    auto_enabled_var = tk.BooleanVar(value=False)

    # Check if automatic backup is currently enabled
    system_os = platform.system()
    if system_os == "Linux":
        try:
            cron_output = subprocess.check_output(['crontab', '-l'], stderr=subprocess.DEVNULL, text=True)
            if 'rotup.py --cron' in cron_output and not cron_output.strip().startswith('#'):
                auto_enabled_var.set(True)
        except:
            pass
    else:  # Windows
        try:
            result = subprocess.run(['schtasks', '/Query', '/TN', 'ROTUP_AutoBackup', '/FO', 'LIST'],
                                    capture_output=True, text=True)
            if 'Ready' in result.stdout or 'Running' in result.stdout:
                auto_enabled_var.set(True)
        except:
            pass

    auto_frame = tk.Frame(auto_card, bg=COLOR_CARD)
    auto_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

    auto_check = tk.Checkbutton(
        auto_frame,
        text="Enable daily automatic backup at 2:00 AM",
        variable=auto_enabled_var,
        font=("Arial", 10),
        bg=COLOR_CARD,
        anchor="w"
    )
    auto_check.pack(fill=tk.X, pady=5)

    auto_info = tk.Label(
        auto_frame,
        text="ℹ️ Requires administrator/sudo privileges to enable/disable",
        font=("Arial", 8),
        bg=COLOR_CARD,
        fg="#666",
        anchor="w"
    )
    auto_info.pack(fill=tk.X, padx=20)
    # === SECTION: BACKUP TIME SELECTION ===
    time_card = tk.Frame(content, bg=COLOR_CARD, relief=tk.FLAT, borderwidth=1)
    time_card.pack(fill=tk.X, pady=(15, 0))

    tk.Label(
        time_card,
        text="🕐 Backup Time:",
        font=("Arial", 11, "bold"),
        bg=COLOR_CARD,
        fg="#333",
        anchor="w"
    ).pack(fill=tk.X, padx=15, pady=(15, 10))

    time_frame = tk.Frame(time_card, bg=COLOR_CARD)
    time_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

    tk.Label(time_frame, text="Hour:", bg=COLOR_CARD, font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 5))

    hour_var = tk.StringVar(value=CONFIG.get('backup_hour', '02'))
    hour_spinbox = tk.Spinbox(
        time_frame,
        from_=0,
        to=23,
        textvariable=hour_var,
        width=8,
        format="%02.0f",
        font=("Arial", 10)
    )
    hour_spinbox.pack(side=tk.LEFT, padx=5)

    tk.Label(time_frame, text="Minute:", bg=COLOR_CARD, font=("Arial", 10)).pack(side=tk.LEFT, padx=(15, 5))

    minute_var = tk.StringVar(value=CONFIG.get('backup_minute', '00'))
    minute_spinbox = tk.Spinbox(
        time_frame,
        from_=0,
        to=59,
        textvariable=minute_var,
        width=8,
        format="%02.0f",
        font=("Arial", 10)
    )
    minute_spinbox.pack(side=tk.LEFT, padx=5)

    tk.Label(
        time_frame,
        text="ℹ️ Default: 02:00 AM",
        font=("Arial", 8),
        bg=COLOR_CARD,
        fg="#666"
    ).pack(side=tk.LEFT, padx=15)
    # === SAVE BUTTON ===
    def save_settings():
        print("[DEBUG] Saving settings...")
        new_conf = CONFIG.copy()

        # Get folders from listbox
        folders_list = list(folders_listbox.get(0, tk.END))

        if not folders_list:
            messagebox.showwarning("No Folders", "Please add at least one source folder!")
            return

        new_conf['source_directories'] = folders_list

        # Get selected disks from listbox
        selected_disks = list(disks_listbox.get(0, tk.END))

        if not selected_disks:
            messagebox.showwarning("No Disks", "Please select at least one rotation disk!")
            return

        if 'disk_rotation' not in new_conf:
            new_conf['disk_rotation'] = {}

        if system_os == "Linux":
            new_conf['disk_rotation']['linux'] = selected_disks
            if 'target_mount_point_linux' not in new_conf:
                new_conf['target_mount_point_linux'] = "/mnt/rotup_usb"
            if 'logging_directory' not in new_conf:
                new_conf['logging_directory'] = "/var/log/rotup"
        else:
            new_conf['disk_rotation']['windows'] = selected_disks
            if 'logging_directory' not in new_conf:
                new_conf['logging_directory'] = "C:\\ProgramData\\ROTUP\\Logs"

        if 'backup_filename_prefix' not in new_conf:
            new_conf['backup_filename_prefix'] = 'backup'

        # Zapisz czas backupu
        try:
            new_conf['backup_hour'] = hour_spinbox.get().zfill(2)
            new_conf['backup_minute'] = minute_spinbox.get().zfill(2)
        except:
            new_conf['backup_hour'] = '02'
            new_conf['backup_minute'] = '00'

        # Save config first
        if not save_config(new_conf):
            messagebox.showerror("Error", "Failed to save configuration!")
            return

        # Handle automatic backup scheduling
        auto_enabled = auto_enabled_var.get()
        backup_hour = new_conf.get('backup_hour', '02')
        backup_minute = new_conf.get('backup_minute', '00')

        if system_os == "Linux":
            try:
                rotup_path = os.path.abspath(__file__)
                cron_line = f"{backup_minute} {backup_hour} * * * /usr/bin/python3 {rotup_path} --cron"

                # Get current crontab
                try:
                    current_cron = subprocess.check_output(['crontab', '-l'], stderr=subprocess.DEVNULL, text=True)
                except:
                    current_cron = ""

                # Remove old ROTUP entries
                lines = [l for l in current_cron.splitlines() if 'rotup.py --cron' not in l and 'rotup --cron' not in l]

                # Add new entry if enabled
                if auto_enabled:
                    lines.append(cron_line)

                # Write new crontab
                new_cron = '\n'.join(lines) + '\n'
                process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=new_cron)

                if process.returncode == 0:
                    status = "enabled" if auto_enabled else "disabled"
                    print(f"[DEBUG] Automatic backup {status} at {backup_hour}:{backup_minute}")
                    messagebox.showinfo("Success",
                                        f"Configuration saved!\nAutomatic backup {status} at {backup_hour}:{backup_minute}")
                else:
                    messagebox.showwarning("Cron Error", "Could not update crontab. You may need sudo privileges.")
            except Exception as e:
                messagebox.showwarning("Cron Error", f"Could not configure automatic backup: {e}")

        else:  # Windows
            try:
                task_name = "ROTUP_AutoBackup"

                if auto_enabled:
                    rotup_path = os.path.abspath(__file__)
                    python_exe = sys.executable

                    pythonw_exe = python_exe.replace('python.exe', 'pythonw.exe')
                    if os.path.exists(pythonw_exe):
                        python_exe = pythonw_exe

                    # Usuń stare zadanie
                    subprocess.run(['schtasks', '/Delete', '/TN', task_name, '/F'],
                                   capture_output=True, stderr=subprocess.DEVNULL)

                    # Utwórz nowe
                    cmd = [
                        'schtasks', '/Create', '/F',
                        '/TN', task_name,
                        '/TR', f'"{python_exe}" "{rotup_path}" --cron',
                        '/SC', 'DAILY',
                        '/ST', f'{backup_hour}:{backup_minute}',
                        '/RL', 'HIGHEST',
                        '/RU', 'SYSTEM'
                    ]

                    result = subprocess.run(cmd, capture_output=True, text=True)

                    if result.returncode != 0:
                        messagebox.showwarning("Task Scheduler Error",
                                               "Could not create scheduled task.\nRun as Administrator.")
                    else:
                        messagebox.showinfo("Success",
                                            f"Configuration saved!\nAutomatic backup enabled at {backup_hour}:{backup_minute}")
                else:
                    subprocess.run(['schtasks', '/Delete', '/TN', task_name, '/F'],
                                   capture_output=True)
                    messagebox.showinfo("Success", "Configuration saved!\nAutomatic backup disabled")

            except Exception as e:
                messagebox.showwarning("Task Scheduler Error", f"Error: {e}")

        settings_win.destroy()
# === SAVE BUTTON === (TO MUSI BYĆ NA KOŃCU, POZA save_settings!)
    save_btn = tk.Button(
        settings_win,
        text="💾 SAVE CONFIGURATION",
        command=save_settings,
        bg="#4CAF50",
        fg="white",
        font=("Arial", 11, "bold"),
        relief=tk.FLAT,
        cursor="hand2",
        pady=15
    )
    save_btn.pack(fill=tk.X, padx=20, pady=(0, 20))
def run_process():
    """Main backup process logic"""
    print("[DEBUG] Starting backup process...")
    if not CONFIG:
        if not load_config():
            log_message("No configuration found! Click SETTINGS.", "WARN")
            return

    initialize_logging()
    log_message("=== ROTUP BACKUP STARTED ===", "INFO")
    log_message(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO")
    log_message(f"System: {platform.system()} {platform.release()}", "INFO")

    sys_os = platform.system()
    ok = False

    try:
        if sys_os == "Linux":
            log_message("Platform: Linux detected", "INFO")
            mp = find_and_mount_linux()
            if mp:
                log_message(f"Disk mounted at: {mp}", "INFO")
                ok = backup_logic_linux(mp)
            else:
                log_message("Failed to mount disk", "ERROR")
        elif sys_os == "Windows":
            log_message("Platform: Windows detected", "INFO")
            ok = backup_logic_windows()
        else:
            log_message(f"Unsupported OS: {sys_os}", "ERROR")
    except Exception as e:
        log_message(f"Critical error during backup: {e}", "ERROR")
        traceback.print_exc()

    if ok:
        log_message("=== BACKUP COMPLETED SUCCESSFULLY ===", "INFO")
    else:
        log_message("=== BACKUP FAILED ===", "ERROR")

    if TEXT_WIDGET and ok:
        messagebox.showinfo("Info", "Backup Completed Successfully!")
    elif TEXT_WIDGET and not ok:
        messagebox.showerror("Error", "Backup failed! Check logs for details.")

    log_message("--- SUCCESS ---" if ok else "--- FAILED ---")
    if TEXT_WIDGET and ok:
        messagebox.showinfo("Info", "Backup Completed Successfully!")


def start_thread():
    """Starts backup process in separate thread"""
    print("[DEBUG] Starting backup thread...")
    if TEXT_WIDGET:
        TEXT_WIDGET.delete('1.0', tk.END)

    # Uruchom progress bar
    root = TEXT_WIDGET.master
    while root.master:
        root = root.master

    if hasattr(root, 'progress_bar'):
        root.progress_bar.start(10)
        root.progress_status.config(text="Backup in progress...", fg="#FF9800")

    def run_with_cleanup():
        try:
            run_process()
        finally:
            # Zatrzymaj progress bar
            if hasattr(root, 'progress_bar'):
                root.progress_bar.stop()
                root.progress_status.config(text="Completed", fg="#4CAF50")

    threading.Thread(target=run_with_cleanup, daemon=True).start()


def main_ui():
    """Creates and runs main GUI window"""
    global TEXT_WIDGET
    print("[DEBUG] Initializing GUI...")

    try:
        root = tk.Tk()
        root.title("ROTUP v0.7 - Rotation Backup Tool by Bejus")
        root.geometry("800x650")
        root.configure(bg="#f0f0f0")

        # Modern color scheme
        COLOR_PRIMARY = "#2196F3"
        COLOR_SUCCESS = "#4CAF50"
        COLOR_WARNING = "#FF9800"
        COLOR_BG = "#f0f0f0"
        COLOR_CARD = "#ffffff"

        # Header frame                                                                                
        header_frame = tk.Frame(root, bg=COLOR_PRIMARY, height=80)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)

        # Title                                                                                       
        title_label = tk.Label(
            header_frame,
            text="ROTUP",
            font=("Arial", 24, "bold"),
            bg=COLOR_PRIMARY,
            fg="white"
        )
        title_label.pack(side=tk.LEFT, padx=20, pady=20)

        subtitle_label = tk.Label(
            header_frame,
            text="Rotation Backup Tool v0.7 by Bejus",
            font=("Arial", 10),
            bg=COLOR_PRIMARY,
            fg="white"
        )
        subtitle_label.place(x=20, y=50)

        # Button container                                                                            
        button_container = tk.Frame(root, bg=COLOR_BG)
        button_container.pack(fill=tk.X, padx=20, pady=15)

        def create_modern_button(parent, text, command, bg_color, emoji=""):
            btn = tk.Button(
                parent,
                text=f"{emoji} {text}",
                command=command,
                bg=bg_color,
                fg="white",
                font=("Arial", 11, "bold"),
                relief=tk.FLAT,
                cursor="hand2",
                padx=20,
                pady=12,
                borderwidth=0
            )

            def on_enter(e):
                btn['bg'] = darken_color(bg_color)

            def on_leave(e):
                btn['bg'] = bg_color

            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)

            return btn

        def darken_color(hex_color):
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
            r, g, b = int(r * 0.8), int(g * 0.8), int(b * 0.8)
            return f'#{r:02x}{g:02x}{b:02x}'

        # Settings button
        settings_btn = create_modern_button(
            button_container,
            "SETTINGS",
            lambda: open_settings_window(root),
            COLOR_WARNING,
            "⚙️"
        )
        settings_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Start backup button
        start_btn = create_modern_button(
            button_container,
            "START BACKUP",
            start_thread,
            COLOR_SUCCESS,
            "▶️"
        )
        start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # NOWY: Progress bar container
        progress_container = tk.Frame(root, bg=COLOR_BG)
        progress_container.pack(fill=tk.X, padx=20, pady=(0, 10))

        progress_label = tk.Label(
            progress_container,
            text="⏳ Progress",
            font=("Arial", 10, "bold"),
            bg=COLOR_BG,
            fg="#333333",
            anchor="w"
        )
        progress_label.pack(fill=tk.X, pady=(0, 5))

        # Progress bar
        progress_bar = ttk.Progressbar(
            progress_container,
            mode='indeterminate',
            length=300
        )
        progress_bar.pack(fill=tk.X)

        # Progress status label
        progress_status = tk.Label(
            progress_container,
            text="Ready",
            font=("Arial", 9),
            bg=COLOR_BG,
            fg="#666666",
            anchor="w"
        )
        progress_status.pack(fill=tk.X, pady=(5, 0))

        # Przekaż widgety do globalnych
        root.progress_bar = progress_bar
        root.progress_status = progress_status

        # Log area container
        log_container = tk.Frame(root, bg=COLOR_BG)
        log_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        log_label = tk.Label(
            log_container,
            text="📋 Backup Log",
            font=("Arial", 10, "bold"),
            bg=COLOR_BG,
            fg="#333333",
            anchor="w"
        )
        log_label.pack(fill=tk.X, pady=(0, 5))

        log_frame = tk.Frame(log_container, bg=COLOR_CARD, relief=tk.FLAT, borderwidth=1)
        log_frame.pack(fill=tk.BOTH, expand=True)

        log_area = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            bg="#fafafa",
            fg="#333333",
            font=("Consolas", 9),
            relief=tk.FLAT,
            borderwidth=0,
            padx=10,
            pady=10
        )
        log_area.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        TEXT_WIDGET = log_area

        # Status bar
        status_bar = tk.Frame(root, bg="#263238", height=25)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)

        status_label = tk.Label(
            status_bar,
            text="Ready",
            font=("Arial", 8),
            bg="#263238",
            fg="white",
            anchor="w"
        )
        status_label.pack(side=tk.LEFT, padx=10)

        # Load config and display status
        load_config()
        if CONFIG:
            folders_count = len(CONFIG.get('source_directories', []))
            status_label.config(text=f"Ready • {folders_count} folder(s) configured")

        print("[DEBUG] GUI created, starting mainloop...")
        root.mainloop()
        print("[DEBUG] GUI closed")
    except Exception as e:
        print(f"[CRITICAL] Error creating GUI: {e}")
        traceback.print_exc()
        input("Press Enter to exit...")


if __name__ == "__main__":
    # Tryb debug - pokaż wszystkie logi
    if '--debug' in sys.argv:
        print("=" * 60)
        print("ROTUP v0.6 - DEBUG MODE")
        print("=" * 60)

    # Tryb normalny - ukryj terminal (już wykonane przez hide_terminal())
    if '--cron' not in sys.argv and '--debug' not in sys.argv:
        pass  # Terminal już ukryty przez hide_terminal()
    else:
        print("=" * 60)
        print("ROTUP v0.6 - Rotation Backup Tool")
        print("=" * 60)
        print(f"[DEBUG] Python version: {sys.version}")
        print(f"[DEBUG] Platform: {platform.system()} {platform.release()}")
        print(f"[DEBUG] Working directory: {os.getcwd()}")
        print(f"[DEBUG] Script location: {BASE_DIR}")
        print(f"[DEBUG] Config file: {CONFIG_FILE}")
        print("=" * 60)

    try:
        if len(sys.argv) > 1 and sys.argv[1] == '--cron':
            print("[DEBUG] CRON mode - running without GUI")
            load_config()
            run_process()
        else:
            if '--debug' not in sys.argv:
                # Normalny tryb - bez logów
                pass
            else:
                print("[DEBUG] GUI mode - starting interface")
            main_ui()
    except Exception as e:
        if '--debug' in sys.argv:
            print("\n" + "!" * 60)
            print("CRITICAL ERROR - Program cannot start!")
            print("!" * 60)
            print(f"\nError type: {type(e).__name__}")
            print(f"Message: {e}")
            print("\nFull traceback:")
            traceback.print_exc()
            print("\n" + "!" * 60)

        try:
            error_log = os.path.join(os.path.dirname(CONFIG_FILE), "rotup_error.log")
            with open(error_log, "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 60}\n")
                f.write(f"[{datetime.datetime.now()}] CRITICAL ERROR\n")
                f.write(f"Error: {e}\n")
                f.write(traceback.format_exc())
                f.write(f"{'=' * 60}\n")
        except:
            pass

        if '--debug' in sys.argv:
            input("\nPress Enter to exit...")
        sys.exit(1)

    if '--debug' in sys.argv:
        print("[DEBUG] Program finished normally")