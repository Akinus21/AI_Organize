from pathlib import Path
import hashlib


# ============================================================
# Fingerprint utilities
# ============================================================

def directory_fingerprint(path: Path) -> str:
    """
    Create a stable fingerprint based on file names + mtimes.
    """
    h = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if p.is_file():
            stat = p.stat()
            h.update(p.name.encode())
            h.update(str(stat.st_mtime_ns).encode())
    return h.hexdigest()