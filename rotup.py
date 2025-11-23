import platform
import json
import sys
import os
import subprocess
import datetime
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk

# --- ZMIENNE GLOBALNE ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
CONFIG = {}
LOG_FILE = ""
BACKUP_FILENAME = ""
TEXT_WIDGET = None

try:
    import psutil
except ImportError:
    print("BŁĄD KRYTYCZNY: Brak biblioteki psutil. Zainstaluj: pip install psutil")
    sys.exit(1)


# --- OBSŁUGA KONFIGURACJI ---

def load_config():
    global CONFIG
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                CONFIG = json.load(f)
            return True
        except:
            return False
    return False


def save_config(new_config):
    global CONFIG
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(new_config, f, indent=4)
        CONFIG = new_config
        return True
    except Exception as e:
        messagebox.showerror("Błąd zapisu", f"Nie udało się zapisać config.json: {e}")
        return False


# --- DETEKCJA DYSKÓW (NOWOŚĆ) ---

def get_available_disks_linux():
    """Zwraca listę słowników {device, label, uuid, fstype}."""
    disks = []
    try:
        # Używamy lsblk do pobrania par label/uuid
        # -P produkuje wyjście par klucz="wartość"
        cmd = ['lsblk', '-o', 'NAME,LABEL,UUID,FSTYPE,MOUNTPOINT', '-P']
        output = subprocess.check_output(cmd, text=True)

        for line in output.splitlines():
            # Parsowanie linii typu: NAME="sdb1" LABEL="MojeDane" UUID="1234-5678" ...
            props = {}
            for part in line.split():
                if '=' in part:
                    key, value = part.split('=', 1)
                    props[key] = value.strip('"')

            # Interesują nas tylko partycje z UUID (zwykle sda1, sdb1 itp.)
            if props.get('UUID'):
                name = f"{props.get('LABEL', 'NO_LABEL')} ({props.get('UUID')})"
                disks.append({
                    'display': name,
                    'value': f"{props.get('LABEL', 'DISK')}_{props.get('UUID')}",  # Format do configa
                    'raw_uuid': props.get('UUID')
                })
    except Exception as e:
        print(f"Błąd detekcji dysków Linux: {e}")
    return disks


def get_available_disks_windows():
    """Zwraca listę dysków Windows."""
    disks = []
    for part in psutil.disk_partitions():
        if 'removable' in part.opts or 'cdrom' not in part.opts:  # Prosta heurystyka
            try:
                usage = psutil.disk_usage(part.mountpoint)
                label = ""
                try:
                    # Próba pobrania etykiety PowerShell
                    cmd = f"(Get-Volume -DriveLetter '{part.device[0]}').FileSystemLabel"
                    label = subprocess.check_output(['powershell', '-Command', cmd], text=True).strip()
                except:
                    pass

                name = f"Dysk {part.device} - {label} [{part.fstype}]"
                # W Windows używamy Etykiety (Label) jako identyfikatora rotacji
                value = label if label else part.device

                disks.append({
                    'display': name,
                    'value': value
                })
            except:
                continue
    return disks


# --- LOGOWANIE I KOMENDY (BEZ ZMIAN) ---

def initialize_logging():
    global LOG_FILE, BACKUP_FILENAME
    log_dir = CONFIG.get('logging_directory', './logs')
    prefix = CONFIG.get('backup_filename_prefix', 'backup')
    current_date = datetime.datetime.now().strftime("%Y_%m_%d")
    try:
        os.makedirs(log_dir, exist_ok=True)
    except:
        pass
    LOG_FILE = os.path.join(log_dir, f"{prefix}_{current_date}.log")
    BACKUP_FILENAME = f"{prefix}_{current_date}.zip"


def log_message(message, level="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {level}: {message}\n"
    print(log_entry.strip())
    if LOG_FILE:
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except:
            pass
    if TEXT_WIDGET:
        try:
            TEXT_WIDGET.insert(tk.END, log_entry)
            TEXT_WIDGET.see(tk.END)
        except:
            pass


def run_command(command, error_message):
    try:
        log_message(f"CMD: {' '.join(command)}")
        subprocess.run(command, capture_output=True, text=True, check=True)
        return True
    except Exception as e:
        log_message(f"{error_message}: {e}", "ERROR")
        return False


def run_powershell_command(command, error_message):
    try:
        log_message(f"PS: {command}")
        subprocess.run(['powershell', '-Command', command], capture_output=True, text=True, check=True)
        return True
    except Exception as e:
        log_message(f"{error_message}: {e}", "ERROR")
        return False


# --- LOGIKA LINUX (MONTAŻ I BACKUP) ---

def find_and_mount_linux():
    log_message("Linux: Szukam dysku rotacyjnego...")
    try:
        blkid_output = subprocess.check_output(['blkid'], text=True).strip()
    except:
        log_message("Brak uprawnień lub narzędzia blkid.", "FATAL")
        return None

    found_uuid = None
    # Sprawdzamy listę zdefiniowaną w configu
    for full_uuid_entry in CONFIG['disk_rotation']['linux']:
        uuid = full_uuid_entry.split('_')[-1]  # Pobieramy sam UUID po ostatnim podkreślniku
        if uuid in blkid_output:
            found_uuid = uuid
            log_message(f"-> Znaleziono dysk z listy: {full_uuid_entry}")
            break

    if not found_uuid:
        log_message("Nie znaleziono żadnego zdefiniowanego dysku.", "ERROR")
        return None

    mount_point = CONFIG['target_mount_point_linux']
    mount_cmd = [
        'mount', '-t', 'ntfs-3g',
        '-o',
        f"defaults,uid={CONFIG.get('linux_user_uid', 1000)},gid={CONFIG.get('linux_user_gid', 1000)},remove_hiberfile,rw,exec",
        f'UUID={found_uuid}', mount_point
    ]

    subprocess.run(['umount', mount_point], stderr=subprocess.DEVNULL)  # Cleanup

    if not run_command(mount_cmd, f"Błąd montowania UUID={found_uuid}"):
        return None

    return mount_point


def backup_logic_linux(mount_path):
    source = CONFIG['source_directory']
    target = os.path.join(mount_path, BACKUP_FILENAME)
    if not run_command(['zip', '-r', '-9', target, source], "Błąd ZIP"):
        return False
    # Weryfikacja
    if not run_command(['zip', '-T', target], "Błąd weryfikacji ZIP"):
        return False
    # Odmontowanie
    run_command(['umount', mount_path], "Błąd odmontowania")
    return True


# --- LOGIKA WINDOWS ---

def backup_logic_windows():
    import psutil
    found_letter = None
    for part in psutil.disk_partitions():
        try:
            cmd = f"(Get-Volume -DriveLetter '{part.device[0]}').FileSystemLabel"
            label = subprocess.check_output(['powershell', '-Command', cmd], text=True).strip()
            if label in CONFIG['disk_rotation']['windows']:
                found_letter = part.device[0]
                log_message(f"-> Znaleziono dysk Windows: {label} ({found_letter}:)")
                break
        except:
            continue

    if not found_letter:
        log_message("Nie znaleziono dysku z listy.", "ERROR")
        return False

    target = os.path.join(f"{found_letter}:\\", BACKUP_FILENAME)
    source = CONFIG['source_directory'].replace('/', '\\')
    cmd = f"Compress-Archive -Path '{source}' -DestinationPath '{target}' -Force"
    return run_powershell_command(cmd, "Błąd kompresji PowerShell")


# --- OKNO KONFIGURACJI (UI) ---

def open_settings_window(root):
    settings_win = tk.Toplevel(root)
    settings_win.title("Konfiguracja ROTUP")
    settings_win.geometry("600x500")

    # 1. Wybór źródła
    tk.Label(settings_win, text="Folder Źródłowy (do zgrania):", font="bold").pack(pady=(10, 0))
    frame_src = tk.Frame(settings_win)
    frame_src.pack(fill=tk.X, padx=10)

    entry_src = tk.Entry(frame_src)
    entry_src.pack(side=tk.LEFT, fill=tk.X, expand=True)
    entry_src.insert(0, CONFIG.get('source_directory', ''))

    def browse_src():
        path = filedialog.askdirectory()
        if path:
            entry_src.delete(0, tk.END)
            entry_src.insert(0, path)

    tk.Button(frame_src, text="Wybierz...", command=browse_src).pack(side=tk.RIGHT)

    # 2. Lista dysków
    tk.Label(settings_win, text="Wybierz dyski rotacyjne (Backup):", font="bold").pack(pady=(20, 0))

    list_frame = tk.Frame(settings_win)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=10)

    canvas = tk.Canvas(list_frame)
    scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Detekcja zależna od systemu
    system_os = platform.system()
    detected_disks = []
    if system_os == "Linux":
        detected_disks = get_available_disks_linux()
        current_selected = CONFIG.get('disk_rotation', {}).get('linux', [])
    else:
        detected_disks = get_available_disks_windows()
        current_selected = CONFIG.get('disk_rotation', {}).get('windows', [])

    check_vars = {}

    if not detected_disks:
        tk.Label(scrollable_frame, text="Nie wykryto dysków zewnętrznych/USB!", fg="red").pack()

    for disk in detected_disks:
        var = tk.BooleanVar()
        # Sprawdź czy ten dysk był już w configu
        if disk['value'] in current_selected:
            var.set(True)

        chk = tk.Checkbutton(scrollable_frame, text=disk['display'], variable=var, anchor='w')
        chk.pack(fill=tk.X)
        check_vars[disk['value']] = var

    # 3. Zapisz
    def save_settings():
        new_conf = CONFIG.copy()
        new_conf['source_directory'] = entry_src.get()

        selected_disks = [val for val, var in check_vars.items() if var.get()]

        if 'disk_rotation' not in new_conf: new_conf['disk_rotation'] = {}

        if system_os == "Linux":
            new_conf['disk_rotation']['linux'] = selected_disks
            # Defaulty
            if 'target_mount_point_linux' not in new_conf: new_conf['target_mount_point_linux'] = "/mnt/rotup_usb"
            if 'logging_directory' not in new_conf: new_conf['logging_directory'] = "/var/log/rotup"
        else:
            new_conf['disk_rotation']['windows'] = selected_disks
            if 'logging_directory' not in new_conf: new_conf['logging_directory'] = "C:\\ProgramData\\ROTUP\\Logs"

        if save_config(new_conf):
            messagebox.showinfo("Sukces", "Konfiguracja zapisana! Uruchom backup ponownie.")
            settings_win.destroy()

    tk.Button(settings_win, text="ZAPISZ KONFIGURACJĘ", command=save_settings, bg="lightblue", height=2).pack(fill=tk.X,
                                                                                                              padx=10,
                                                                                                              pady=10)


# --- GŁÓWNA PĘTLA ---

def run_process():
    if not load_config():
        log_message("Brak konfiguracji! Kliknij USTAWIENIA.", "WARN")
        return

    initialize_logging()
    log_message("--- START ---")

    sys_os = platform.system()
    ok = False

    if sys_os == "Linux":
        mp = find_and_mount_linux()
        if mp: ok = backup_logic_linux(mp)
    elif sys_os == "Windows":
        ok = backup_logic_windows()

    log_message("--- SUKCES ---" if ok else "--- BŁĄD ---")
    if TEXT_WIDGET and ok: messagebox.showinfo("Info", "Backup zakończony!")


def start_thread():
    if TEXT_WIDGET: TEXT_WIDGET.delete('1.0', tk.END)
    threading.Thread(target=run_process, daemon=True).start()


def main_ui():
    global TEXT_WIDGET
    root = tk.Tk()
    root.title("ROTUP v2.0 - Auto Config")
    root.geometry("700x550")

    frame_top = tk.Frame(root)
    frame_top.pack(fill=tk.X, padx=10, pady=10)

    tk.Button(frame_top, text="USTAWIENIA / KONFIGURACJA DYSKÓW", command=lambda: open_settings_window(root),
              bg="orange").pack(side=tk.LEFT, fill=tk.X, expand=True)

    tk.Button(root, text="URUCHOM BACKUP TERAZ", command=start_thread, bg="lightgreen", font=("Arial", 12, "bold"),
              pady=10).pack(fill=tk.X, padx=10)

    log_area = scrolledtext.ScrolledText(root)
    log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    TEXT_WIDGET = log_area

    # Próba wczytania configu na starcie
    load_config()

    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--cron':
        run_process()
    else:
        main_ui()