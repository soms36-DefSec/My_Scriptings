import os
import shutil
import stat
from pathlib import Path

# --- Configuration ---
DOWNLOADS_DIR = Path(r"C:\Users\SOMS\Downloads")

# Category mappings (easily extendable)
CATEGORIES = {
    "Images": {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.svg', '.heic', '.ico', '.raw'},
    "Documents": {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf', '.csv', '.odt', '.ods', '.odp', '.md'},
    "Softwares": {'.exe', '.msi', '.bat', '.cmd', '.ps1', '.apk', '.jar', '.com'}
}

# ZFolder special rules
ZFOLDER_ARCHIVES = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.iso'}
ZFOLDER_EXEC_FALLBACK = {'.exe', '.msi'} # Captures installers if they are ever removed from the Softwares category above

def is_hidden(filepath: Path) -> bool:
    """Checks if a file is hidden in Windows using file attributes."""
    try:
        return bool(os.stat(filepath).st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
    except OSError:
        return False

def get_unique_path(destination_path: Path) -> Path:
    """Safely handles duplicate filenames by appending a counter (e.g., file (1).ext)."""
    if not destination_path.exists():
        return destination_path

    base_name = destination_path.stem
    extension = destination_path.suffix
    directory = destination_path.parent
    counter = 1

    while True:
        new_name = f"{base_name} ({counter}){extension}"
        new_path = directory / new_name
        if not new_path.exists():
            return new_path
        counter += 1

def move_file(file_path: Path, base_dest_dir: Path, is_zfolder: bool = False):
    """Handles directory creation, safe path resolution, and file moving."""
    try:
        if is_zfolder:
            # Create a subfolder inside ZFolders named after the file (without extension)
            target_dir = base_dest_dir / file_path.stem
        else:
            target_dir = base_dest_dir

        # Ensure the destination directory exists
        target_dir.mkdir(parents=True, exist_ok=True)

        # Get unique path to prevent overwriting
        target_path = get_unique_path(target_dir / file_path.name)

        # Execute the move
        shutil.move(str(file_path), str(target_path))
        print(f"[SUCCESS] Moved: '{file_path.name}' -> '{target_path.relative_to(DOWNLOADS_DIR)}'")

    except PermissionError:
        print(f"[ERROR] Permission Denied (File may be locked or open): '{file_path.name}'")
    except Exception as e:
        print(f"[ERROR] Failed to move '{file_path.name}': {e}")

def organize_downloads():
    """Main scanning and categorization logic."""
    if not DOWNLOADS_DIR.exists() or not DOWNLOADS_DIR.is_dir():
        print(f"[CRITICAL ERROR] Directory not found: {DOWNLOADS_DIR}")
        return

    print(f"--- Starting File Organization in: {DOWNLOADS_DIR} ---\n")

    # Non-recursive scan of the root directory
    for file_path in DOWNLOADS_DIR.iterdir():

        # 1. Ignore directories
        if file_path.is_dir():
            continue

        # 2. Ignore hidden files
        if is_hidden(file_path):
            continue

        # 3. Ignore files without extensions
        ext = file_path.suffix.lower()
        if not ext:
            continue

        categorized = False

        # 4. Standard Categories check
        for category, extensions in CATEGORIES.items():
            if ext in extensions:
                move_file(file_path, DOWNLOADS_DIR / category)
                categorized = True
                break

        if categorized:
            continue

        # 5. ZFolders Rules check
        if ext in ZFOLDER_ARCHIVES or ext in ZFOLDER_EXEC_FALLBACK:
            move_file(file_path, DOWNLOADS_DIR / "ZFolders", is_zfolder=True)
            categorized = True

        # 6. Fallback
        if not categorized:
            pass # Explicitly doing nothing. Unknown/unsupported files remain untouched.

    print("\n--- Organization Complete ---")

if __name__ == "__main__":
    organize_downloads()
