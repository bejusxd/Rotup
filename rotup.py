import platform
import json
import sys
import os
import subprocess
import datetime
import shutil

# --- KONFIGURACJA ŚCIEŻEK ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
CONFIG = {}
LOG_FILE = ""
BACKUP_FILENAME = ""


# --- FUNKCJE POMOCNICZE (LOGOWANIE) ---

def initialize_logging(log_dir, prefix):
    """Konfiguruje ścieżkę logowania."""
    global LOG_FILE
    global BACKUP_FILENAME

    current_date = datetime.datetime.now().strftime("%Y_%m_%d")

    try:
        # Tworzenie katalogu logów, jeśli nie istnieje
        os.makedirs(log_dir, exist_ok=True)
    except Exception as e:
        print(f"BŁĄD KRYTYCZNY: Nie można utworzyć katalogu logów {log_dir}: {e}")
        sys.exit(1)

    LOG_FILE = os.path.join(log_dir, f"{prefix}_{current_date}.log")
    BACKUP_FILENAME = f"{prefix}_{current_date}.zip"


def log_message(message, level="INFO"):
    """Zapisuje wiadomości do pliku logu i na standardowe wyjście."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {level}: {message}"

    # Zapis do stdout
    print(log_entry)

    # Zapis do pliku logu
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"BŁĄD ZAPISU LOGU: Nie można zapisać do {LOG_FILE}: {e}")


def run_command(command, error_message, log_output=True):
    """Wykonuje polecenie systemowe i obsługuje błędy."""
    try:
        log_message(f"Wykonuję komendę: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=True)

        if log_output and result.stdout.strip():
            log_message(f"STDOUT: {result.stdout.strip()}", level="DEBUG")

        return True

    except subprocess.CalledProcessError as e:
        log_message(f"{error_message} (Kod wyjścia: {e.returncode})", level="ERROR")
        log_message(f"STDERR: {e.stderr.strip()}", level="ERROR")
        return False
    except FileNotFoundError:
        log_message(f"BŁĄD: Nie znaleziono polecenia {' '.join(command)}. Sprawdź PATH.", level="FATAL")
        return False


# --- LOGIKA LINUX ---

def find_and_mount_linux():
    """Szuka dysku Linux po UUID i montuje z naprawą NTFS."""

    log_message("Detekcja Linux: Szukam podłączonego dysku USB po UUID...")

    try:
        # Wymaga uprawnień root, dlatego zakładamy uruchomienie jako root
        blkid_output = subprocess.check_output(['blkid'], text=True).strip()
    except subprocess.CalledProcessError:
        log_message("BŁĄD: Nie udało się uruchomić blkid. Upewnij się, że skrypt działa jako root.", level="FATAL")
        return None

    found_uuid = None

    for full_uuid_entry in CONFIG['disk_rotation']['linux']:
        # Wydobywamy czysty UUID z pełnego wpisu (UUID_DYSKU_A_1234-ABCD -> 1234-ABCD)
        uuid = full_uuid_entry.split('_')[-1]

        if uuid in blkid_output:
            found_uuid = uuid
            log_message(f"   -> ZNALEZIONO DYSK UUID: {found_uuid}")
            break

    if not found_uuid:
        log_message("BŁĄD: Żaden z rotacyjnych dysków USB nie został wykryty.", level="ERROR")
        return None

    # Montowanie z naprawą NTFS
    mount_point = CONFIG['target_mount_point_linux']
    uid = CONFIG['linux_user_uid']
    gid = CONFIG['linux_user_gid']

    log_message(f"2. Próba montażu dysku UUID={found_uuid} do {mount_point} (z remove_hiberfile)...")

    mount_cmd = [
        'mount', '-t', 'ntfs-3g',
        '-o', f'defaults,uid={uid},gid={gid},remove_hiberfile,rw,exec',
        f'UUID={found_uuid}', mount_point
    ]

    # Próba odmontowania, jeśli jest już zamontowany przez przypadek (np. z inną sesją)
    run_command(['umount', mount_point], "Ostrzeżenie: Nie udało się odmontować przed montażem, kontynuuję.")

    if not run_command(mount_cmd, f"BŁĄD MONTAŻU: Nie udało się zamontować dysku {found_uuid}."):
        return None

    log_message("   -> Dysk zamontowany pomyślnie.")
    return mount_point


def backup_and_unmount_linux(mount_path):
    """Kompresuje, weryfikuje i odmontowuje dysk na Linuxie."""
    source_dir = CONFIG['source_directory']
    target_path = os.path.join(mount_path, BACKUP_FILENAME)

    log_message(f"3. Rozpoczęcie tworzenia archiwum ZIP: {target_path}")

    # Komenda ZIP
    zip_cmd = ['zip', '-r', '-9', target_path, source_dir]
    backup_success = run_command(zip_cmd, "BŁĄD BACKUPU: Kompresja i kopiowanie nie powiodło się.")

    # Weryfikacja
    if backup_success:
        log_message("4. Weryfikacja integralności pliku ZIP...")
        verify_cmd = ['zip', '-T', target_path]
        verify_success = run_command(verify_cmd, "BŁĄD WERYFIKACJI: Plik ZIP jest uszkodzony lub niepoprawny.")
        if not verify_success:
            backup_success = False

    # Odmontowanie (UNMOUNT)
    log_message("5. Odmontowywanie dysku...")
    umount_cmd = ['umount', mount_path]
    umount_success = run_command(umount_cmd, "BŁĄD ODMONTOWANIA: Wymaga ręcznej interwencji!")

    return backup_success and umount_success


# --- FUNKCJA GŁÓWNA (ENTRY POINT) ---

def main():
    if not load_config():
        sys.exit(1)

    initialize_logging(CONFIG['logging_directory'], CONFIG['backup_filename_prefix'])
    log_message("--- START ROTUP BACKUP PROCESS ---")

    system_os = platform.system()
    success = False

    if system_os == "Linux":
        # Wymagamy roota do montowania
        if os.geteuid() != 0:
            log_message("BŁĄD: Skrypt Linux musi być uruchomiony z uprawnieniami roota (sudo)!", level="FATAL")
            sys.exit(1)

        mount_path = find_and_mount_linux()
        if mount_path:
            success = backup_and_unmount_linux(mount_path)

    elif system_os == "Windows":
        # Tutaj będzie implementacja logiki Windows
        log_message("System Windows jest jeszcze niezaimplementowany. Przerwanie.", level="FATAL")

    else:
        log_message(f"BŁĄD: System {system_os} nie jest obsługiwany przez rotup.", level="FATAL")

    if success:
        log_message("--- ZAKOŃCZENIE PRACY (SUKCES) ---")
        sys.exit(0)
    else:
        log_message("--- ZAKOŃCZENIE PRACY (BŁĄD KRYTYCZNY) ---", level="FATAL")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_message(f"Nieoczekiwany błąd w programie: {e}", level="FATAL")
        sys.exit(1)