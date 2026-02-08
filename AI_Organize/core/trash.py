from pathlib import Path
from datetime import datetime, timedelta
import shutil
from typing import Optional

TRASH_DIR_NAME = ".ai_organize_trash"
DATE_FORMAT = "%Y-%m-%d"


def get_trash_root(project_root: Optional[Path] = None) -> Path:
    from akinus.utils.app_details import PROJECT_ROOT
    root = project_root or PROJECT_ROOT
    trash_root = root / TRASH_DIR_NAME
    trash_root.mkdir(parents=True, exist_ok=True)

    readme = trash_root / "README.md"
    if not readme.exists():
        readme.write_text(
            "# AI Organize Trash\n\n"
            "Files moved here were deleted by AI_Organize.\n"
            "Subfolders are date-based.\n\n"
            "This folder is auto-cleaned based on retention policy.\n",
            encoding="utf-8",
        )

    return trash_root


def move_to_trash(
    file_path: Path,
    project_root: Optional[Path] = None,
) -> Path:
    """
    Move a file to the project trash folder.
    Returns the new file path.
    """
    from akinus.utils.logger import log
    trash_root = get_trash_root(project_root)
    today = datetime.now().strftime(DATE_FORMAT)

    dest_dir = trash_root / today
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dest_dir / file_path.name

    # Handle name collisions
    counter = 1
    while dest_path.exists():
        dest_path = dest_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
        counter += 1

    shutil.move(str(file_path), str(dest_path))

    log(
        "INFO",
        "trash",
        f"Moved file to trash: {file_path} -> {dest_path}",
    )

    return dest_path


def cleanup_trash(
    retention_days: int,
    project_root: Optional[Path] = None,
):
    """
    Permanently delete trash subfolders older than retention_days.
    """
    from akinus.utils.logger import log
    trash_root = get_trash_root(project_root)
    cutoff = datetime.now() - timedelta(days=retention_days)

    for entry in trash_root.iterdir():
        if not entry.is_dir():
            continue

        try:
            folder_date = datetime.strptime(entry.name, DATE_FORMAT)
        except ValueError:
            continue  # ignore non-date folders

        if folder_date < cutoff:
            shutil.rmtree(entry, ignore_errors=True)
            log(
                "INFO",
                "trash",
                f"Cleaned trash folder: {entry.name}",
            )
