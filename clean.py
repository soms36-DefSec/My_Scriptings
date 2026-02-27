import os
import shutil
import hashlib
import logging
import ctypes
from pathlib import Path
from typing import List, Dict, Tuple

# --- Configuration & Setup ---
logging.basicConfig(
    filename='system_cleanup.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Critical directories that should NEVER be scanned for duplicates or swept
PROTECTED_DIRS = {
    Path(os.environ.get('WINDIR', 'C:\\Windows')).resolve(),
    Path(os.environ.get('PROGRAMFILES', 'C:\\Program Files')).resolve(),
    Path(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')).resolve(),
}

def is_admin() -> bool:
    """Safely check if the script is running with Administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except AttributeError:
        return False

def is_path_safe(target_path: Path) -> bool:
    """Ensure the target path is not inside a protected system directory."""
    target_resolved = target_path.resolve()
    for protected in PROTECTED_DIRS:
        if protected in target_resolved.parents or target_resolved == protected:
            return False
    return True

# --- Module 1: Temp File Cleaner ---
class TempCleaner:
    def __init__(self):
        self.temp_dirs = [
            Path(os.environ.get('WINDIR', 'C:\\Windows')) / 'Temp',
            Path(os.environ.get('LOCALAPPDATA', 'C:\\Users\\Default\\AppData\\Local')) / 'Temp'
        ]

    def clean(self):
        print("\n--- Starting Temp File Cleanup ---")
        if not is_admin():
            print("[!] Note: Running without Admin privileges. Some Windows temp files will be skipped.")
            logging.warning("Temp cleanup initiated without admin privileges.")

        total_freed = 0
        deleted_count = 0

        for temp_dir in self.temp_dirs:
            if not temp_dir.exists():
                continue

            for item in temp_dir.rglob('*'):
                if not item.exists(): # Might have been deleted by a previous directory removal
                    continue

                try:
                    size = item.stat().st_size if item.is_file() else 0
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        item.rmdir() # Only removes if empty; shutil.rmtree is too aggressive here

                    total_freed += size
                    deleted_count += 1
                    logging.info(f"Deleted temp item: {item}")
                except (PermissionError, OSError):
                    # Silently skip files in use or locked by system
                    pass

        mb_freed = total_freed / (1024 * 1024)
        print(f"Cleanup Complete: Removed {deleted_count} items. Freed {mb_freed:.2f} MB.")

# --- Module 2: Duplicate File Finder ---
class DuplicateFinder:
    def __init__(self, target_dir: Path):
        self.target_dir = target_dir
        self.review_dir = self.target_dir / "Duplicate_Review"

    def _get_file_hash(self, filepath: Path, chunk_size: int = 8192) -> str:
        """Calculate SHA-256 hash using memory-efficient chunking."""
        hasher = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(chunk_size):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (PermissionError, OSError) as e:
            logging.error(f"Failed to read file for hashing {filepath}: {e}")
            return ""

    def find_and_move(self):
        print(f"\n--- Scanning for Duplicates in {self.target_dir} ---")
        if not is_path_safe(self.target_dir):
            print("[!] Security Violation: Cannot scan protected system directories.")
            return

        # Optimization: Group by file size first to avoid hashing unique files
        size_dict: Dict[int, List[Path]] = {}
        for filepath in self.target_dir.rglob('*'):
            if filepath.is_file() and not self.review_dir in filepath.parents:
                try:
                    size = filepath.stat().st_size
                    size_dict.setdefault(size, []).append(filepath)
                except OSError:
                    continue

        # Filter out unique sizes
        potential_dupes = {size: paths for size, paths in size_dict.items() if len(paths) > 1}

        hash_dict: Dict[str, List[Path]] = {}
        for size, paths in potential_dupes.items():
            for filepath in paths:
                file_hash = self._get_file_hash(filepath)
                if file_hash:
                    hash_dict.setdefault(file_hash, []).append(filepath)

        # Process true duplicates
        duplicates = {h: paths for h, paths in hash_dict.items() if len(paths) > 1}

        if not duplicates:
            print("No duplicates found.")
            return

        self.review_dir.mkdir(exist_ok=True)
        total_dupes = 0
        space_saved = 0

        for file_hash, paths in duplicates.items():
            # Keep the first file, move the rest
            original = paths[0]
            for dupe in paths[1:]:
                try:
                    space_saved += dupe.stat().st_size
                    dest_path = self.review_dir / dupe.name
                    # Handle name collisions in review folder
                    counter = 1
                    while dest_path.exists():
                        dest_path = self.review_dir / f"{dupe.stem}_{counter}{dupe.suffix}"
                        counter += 1

                    shutil.move(str(dupe), str(dest_path))
                    logging.info(f"Moved duplicate: {dupe} -> {dest_path}")
                    total_dupes += 1
                except Exception as e:
                    logging.error(f"Failed to move duplicate {dupe}: {e}")

        mb_saved = space_saved / (1024 * 1024)
        print(f"Found and moved {total_dupes} duplicates to '{self.review_dir.name}'.")
        print(f"Total space of moved duplicates: {mb_saved:.2f} MB.")

# --- Module 3: Empty Folder Sweeper ---
class EmptyFolderSweeper:
    def __init__(self, target_dir: Path):
        self.target_dir = target_dir

    def sweep(self, dry_run: bool = True):
        print(f"\n--- Empty Folder Sweeper ({'DRY RUN' if dry_run else 'LIVE RUN'}) ---")
        if not is_path_safe(self.target_dir):
            print("[!] Security Violation: Cannot sweep protected system directories.")
            return

        deleted_count = 0
        # Bottom-up traversal ensures child folders are evaluated before parents
        for dirpath, dirnames, filenames in os.walk(self.target_dir, topdown=False):
            current_dir = Path(dirpath)

            # Don't delete the target root directory itself
            if current_dir == self.target_dir:
                continue

            try:
                # Check if truly empty
                if not any(current_dir.iterdir()):
                    if dry_run:
                        print(f"[Dry Run] Would delete: {current_dir}")
                    else:
                        current_dir.rmdir()
                        logging.info(f"Deleted empty folder: {current_dir}")
                    deleted_count += 1
            except (PermissionError, OSError) as e:
                logging.error(f"Could not access/delete {current_dir}: {e}")

        action = "Would delete" if dry_run else "Deleted"
        print(f"Sweeper Complete: {action} {deleted_count} empty folders.")

# --- CLI Interface ---
def main():
    while True:
        print("\n=== System Cleanup & Organization Tool ===")
        print("1. Clean Temp Files")
        print("2. Find & Move Duplicate Files")
        print("3. Sweep Empty Folders")
        print("4. Exit")

        choice = input("Select an option (1-4): ").strip()

        if choice == '1':
            TempCleaner().clean()

        elif choice == '2':
            target = input("Enter directory path to scan for duplicates: ").strip()
            path = Path(target)
            if path.is_dir():
                DuplicateFinder(path).find_and_move()
            else:
                print("Invalid directory path.")

        elif choice == '3':
            target = input("Enter directory path to sweep: ").strip()
            path = Path(target)
            if path.is_dir():
                dry = input("Run in Dry-Run mode? (Y/n): ").strip().lower() != 'n'
                if not dry:
                    confirm = input("WARNING: This will delete folders. Are you sure? (y/N): ").strip().lower()
                    if confirm != 'y':
                        print("Aborting live run.")
                        continue
                EmptyFolderSweeper(path).sweep(dry_run=dry)
            else:
                print("Invalid directory path.")

        elif choice == '4':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please select 1-4.")

if __name__ == "__main__":
    main()
