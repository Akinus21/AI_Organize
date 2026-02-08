from pathlib import Path
import hashlib


def compute_directory_hash(directory: Path) -> str:
    h = hashlib.sha256()

    for p in sorted(directory.rglob("*")):
        if not p.is_file():
            continue

        stat = p.stat()
        h.update(p.name.encode())
        h.update(str(stat.st_size).encode())
        h.update(str(int(stat.st_mtime)).encode())

    return h.hexdigest()
