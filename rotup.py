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

    print(f"[DEBUG] psutil loaded successfully (version: {psutil.__version__})")
except ImportError as e:
    print(f"FATAL ERROR: Missing 'psutil' library. Install via: pip install psutil")
    print(f"[DEBUG] Import error details: {e}")
    input("Press Enter to exit...")
    sys.exit(1)


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
                        cmd = f"(Get-Volume -DriveLetter '{drive_letter}').FileSystemLabel"
                        print(f"[DEBUG] Executing PowerShell: {cmd}")
                        result = subprocess.check_output(['powershell', '-Command', cmd],
                                                         text=True,
                                                         stderr=subprocess.PIPE,
                                                         timeout=5)
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
        subprocess.run(['powershell', '-Command', command], capture_output=True, text=True, check=True)
        return True
    except Exception as e:
        log_message(f"{error_message}: {e}", "ERROR")
        return False


# --- LOGIC: LINUX ---

def find_and_mount_linux():
    """Finds and mounts rotation disk on Linux"""
    log_message("Linux: Searching for rotation disk...")
    try:
        blkid_output = subprocess.check_output(['blkid'], text=True).strip()
    except Exception as e:
        log_message(f"Missing permissions or 'blkid' tool: {e}", "FATAL")
        return None

    found_uuid = None
    linux_disks = CONFIG.get('disk_rotation', {}).get('linux', [])
    for full_uuid_entry in linux_disks:
        uuid = full_uuid_entry.split('_')[-1]
        if uuid in blkid_output:
            found_uuid = uuid
            log_message(f"-> Found disk from list: {full_uuid_entry}")
            break

    if not found_uuid:
        log_message("No defined disk found.", "ERROR")
        return None

    mount_point = CONFIG.get('target_mount_point_linux', '/mnt/rotup_usb')
    mount_cmd = [
        'mount', '-t', 'ntfs-3g',
        '-o',
        f"defaults,uid={CONFIG.get('linux_user_uid', 1000)},gid={CONFIG.get('linux_user_gid', 1000)},remove_hiberfile,rw,exec",
        f'UUID={found_uuid}', mount_point
    ]
    subprocess.run(['umount', mount_point], stderr=subprocess.DEVNULL)
    if not run_command(mount_cmd, f"Mount error UUID={found_uuid}"):
        return None
    return mount_point


def backup_logic_linux(mount_path):
    """Performs backup on Linux system"""
    source_dirs = CONFIG.get('source_directories', [])
    if not source_dirs:
        log_message("No source directories configured!", "ERROR")
        return False

    target = os.path.join(mount_path, BACKUP_FILENAME)

    # Build zip command with multiple sources
    zip_cmd = ['zip', '-r', '-9', target] + source_dirs

    if not run_command(zip_cmd, "ZIP Error"):
        return False
    if not run_command(['zip', '-T', target], "ZIP Verification Error"):
        return False
    run_command(['umount', mount_path], "Unmount Error")
    return True


# --- LOGIC: WINDOWS ---

def backup_logic_windows():
    """Performs backup on Windows system"""
    found_letter = None
    windows_labels = CONFIG.get('disk_rotation', {}).get('windows', [])

    if not windows_labels:
        log_message("No Windows disks configured in rotation list!", "ERROR")
        return False

    print(f"[DEBUG] Looking for disks with labels: {windows_labels}")

    for part in psutil.disk_partitions():
        try:
            drive_letter = part.device.rstrip('\\').rstrip(':')
            cmd = f"(Get-Volume -DriveLetter '{drive_letter}').FileSystemLabel"
            label = subprocess.check_output(['powershell', '-Command', cmd],
                                            text=True,
                                            stderr=subprocess.PIPE,
                                            timeout=5).strip()
            print(f"[DEBUG] Checking disk {drive_letter}: label='{label}'")
            if label in windows_labels:
                found_letter = drive_letter
                log_message(f"-> Found Windows disk: {label} ({found_letter}:)")
                break
        except Exception as e:
            print(f"[DEBUG] Error checking {part.device}: {e}")
            continue

    if not found_letter:
        log_message("No disk from the list found.", "ERROR")
        return False

    source_dirs = CONFIG.get('source_directories', [])
    if not source_dirs:
        log_message("No source directories configured!", "ERROR")
        return False

    target = os.path.join(f"{found_letter}:\\", BACKUP_FILENAME)

    # Convert paths to Windows format
    sources_win = [s.replace('/', '\\') for s in source_dirs]
    sources_str = "', '".join(sources_win)

    cmd = f"Compress-Archive -Path '{sources_str}' -DestinationPath '{target}' -Force"
    return run_powershell_command(cmd, "PowerShell Compression Error")


# --- UI ---

def open_settings_window(root):
    """Opens settings window"""
    print("[DEBUG] Opening settings window...")
    settings_win = tk.Toplevel(root)
    settings_win.title("ROTUP Configuration")
    settings_win.geometry("750x700")
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
    content = tk.Frame(settings_win, bg=COLOR_BG)
    content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

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
        text="💾 Select Rotating Disks:",
        font=("Arial", 11, "bold"),
        bg=COLOR_CARD,
        fg="#333",
        anchor="w"
    ).pack(fill=tk.X, padx=15, pady=(15, 10))

    # Frame with canvas and scrollbar for disks
    disks_outer_frame = tk.Frame(disks_card, relief=tk.FLAT, bg="white", borderwidth=1)
    disks_outer_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

    disks_canvas = tk.Canvas(disks_outer_frame, height=150)
    disks_scrollbar = ttk.Scrollbar(disks_outer_frame, orient="vertical", command=disks_canvas.yview)
    disks_scrollable_frame = ttk.Frame(disks_canvas)

    # FIXED: Set maximum scrollregion height
    def configure_scroll_region(event=None):
        disks_canvas.configure(scrollregion=disks_canvas.bbox("all"))

    disks_scrollable_frame.bind("<Configure>", configure_scroll_region)

    canvas_window = disks_canvas.create_window((0, 0), window=disks_scrollable_frame, anchor="nw")

    # FIXED: Stretch inner frame to canvas width
    def configure_canvas_width(event):
        disks_canvas.itemconfig(canvas_window, width=event.width)

    disks_canvas.bind("<Configure>", configure_canvas_width)
    disks_canvas.configure(yscrollcommand=disks_scrollbar.set)

    disks_canvas.pack(side="left", fill="both", expand=True)
    disks_scrollbar.pack(side="right", fill="y")

    system_os = platform.system()
    print(f"[DEBUG] System: {system_os}")
    detected_disks = []
    if system_os == "Linux":
        detected_disks = get_available_disks_linux()
        current_selected = CONFIG.get('disk_rotation', {}).get('linux', [])
    else:
        detected_disks = get_available_disks_windows()
        current_selected = CONFIG.get('disk_rotation', {}).get('windows', [])

    check_vars = {}
    if not detected_disks:
        tk.Label(disks_scrollable_frame, text="No external disks detected!", fg="red").pack()

    for disk in detected_disks:
        var = tk.BooleanVar()
        if disk['value'] in current_selected:
            var.set(True)
        chk = tk.Checkbutton(disks_scrollable_frame, text=disk['display'], variable=var, anchor='w')
        chk.pack(fill=tk.X, padx=5, pady=2)
        check_vars[disk['value']] = var

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

        # Get selected disks
        selected_disks = [val for val, var in check_vars.items() if var.get()]

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

        # Save config first
        if not save_config(new_conf):
            return

        # Handle automatic backup scheduling
        auto_enabled = auto_enabled_var.get()

        if system_os == "Linux":
            try:
                rotup_path = os.path.abspath(__file__)
                cron_line = f"0 2 * * * /usr/bin/python3 {rotup_path} --cron"

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
                    print(f"[DEBUG] Automatic backup {status}")
                else:
                    messagebox.showwarning("Cron Error", "Could not update crontab. You may need sudo privileges.")
            except Exception as e:
                messagebox.showwarning("Cron Error",
                                       f"Could not configure automatic backup: {e}\nTry running with sudo.")

        else:  # Windows
            try:
                task_name = "ROTUP_AutoBackup"

                if auto_enabled:
                    # Create/enable task
                    rotup_path = os.path.abspath(__file__)
                    python_exe = sys.executable

                    # Try using pythonw.exe for background execution
                    pythonw_exe = python_exe.replace('python.exe', 'pythonw.exe')
                    if os.path.exists(pythonw_exe):
                        python_exe = pythonw_exe

                    cmd = [
                        'schtasks', '/Create', '/F',
                        '/TN', task_name,
                        '/TR', f'"{python_exe}" "{rotup_path}" --cron',
                        '/SC', 'DAILY',
                        '/ST', '02:00',
                        '/RL', 'HIGHEST',
                        '/RU', 'SYSTEM'
                    ]

                    result = subprocess.run(cmd, capture_output=True, text=True)

                    if result.returncode != 0:
                        messagebox.showwarning("Task Scheduler Error",
                                               "Could not create scheduled task.\nRun as Administrator or create manually in Task Scheduler.")
                    else:
                        print("[DEBUG] Automatic backup enabled")
                else:
                    # Disable task
                    subprocess.run(['schtasks', '/Delete', '/TN', task_name, '/F'],
                                   capture_output=True)
                    print("[DEBUG] Automatic backup disabled")

            except Exception as e:
                messagebox.showwarning("Task Scheduler Error",
                                       f"Could not configure automatic backup: {e}\nRun as Administrator.")

        messagebox.showinfo("Success", "Configuration saved successfully!")
        settings_win.destroy()

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
    log_message("--- STARTING BACKUP ---")
    sys_os = platform.system()
    ok = False

    try:
        if sys_os == "Linux":
            mp = find_and_mount_linux()
            if mp:
                ok = backup_logic_linux(mp)
        elif sys_os == "Windows":
            ok = backup_logic_windows()
        else:
            log_message(f"Unsupported OS: {sys_os}", "ERROR")
    except Exception as e:
        log_message(f"Critical error during backup: {e}", "ERROR")
        traceback.print_exc()

    log_message("--- SUCCESS ---" if ok else "--- FAILED ---")
    if TEXT_WIDGET and ok:
        messagebox.showinfo("Info", "Backup Completed Successfully!")


def start_thread():
    """Starts backup process in separate thread"""
    print("[DEBUG] Starting backup thread...")
    if TEXT_WIDGET:
        TEXT_WIDGET.delete('1.0', tk.END)
    threading.Thread(target=run_process, daemon=True).start()


def main_ui():
    """Creates and runs main GUI window"""
    global TEXT_WIDGET
    print("[DEBUG] Initializing GUI...")

    try:
        root = tk.Tk()
        root.title("ROTUP v2.0 - Rotation Backup Tool")
        root.geometry("800x600")
        root.configure(bg="#f0f0f0")

        # Modern color scheme
        COLOR_PRIMARY = "#2196F3"  # Blue
        COLOR_SUCCESS = "#4CAF50"  # Green
        COLOR_WARNING = "#FF9800"  # Orange
        COLOR_BG = "#f0f0f0"  # Light gray
        COLOR_CARD = "#ffffff"  # White

        # Header frame with gradient effect
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
            text="Rotation Backup Tool v2.0",
            font=("Arial", 10),
            bg=COLOR_PRIMARY,
            fg="white"
        )
        subtitle_label.place(x=20, y=50)

        # Button container
        button_container = tk.Frame(root, bg=COLOR_BG)
        button_container.pack(fill=tk.X, padx=20, pady=15)

        # Styled buttons with hover effect
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

            # Hover effects
            def on_enter(e):
                btn['bg'] = darken_color(bg_color)

            def on_leave(e):
                btn['bg'] = bg_color

            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)

            return btn

        def darken_color(hex_color):
            """Darken hex color by 20%"""
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

        # Log area container with card style
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

        # Log area with modern styling
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
    print("=" * 60)
    print("ROTUP v2.0 - Rotation Backup Tool")
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
            run_process()
        else:
            print("[DEBUG] GUI mode - starting interface")
            main_ui()
    except Exception as e:
        print("\n" + "!" * 60)
        print("CRITICAL ERROR - Program cannot start!")
        print("!" * 60)
        print(f"\nError type: {type(e).__name__}")
        print(f"Message: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        print("\n" + "!" * 60)
        input("\nPress Enter to exit...")
        sys.exit(1)

    print("[DEBUG] Program finished normally")