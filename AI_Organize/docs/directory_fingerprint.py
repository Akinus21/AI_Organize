from pathlib import Path
import hashlib


# ============================================================
# Fingerprint utilities
# ============================================================

EXCLUDED = {"README.md", ".ai_directory_summary.json"}

def directory_fingerprint(path: Path) -> str:
    h = hashlib.sha256()

    for p in sorted(path.iterdir()):
        if p.name in EXCLUDED:
            continue
        if p.is_file():
            h.update(p.name.encode())
            h.update(str(p.stat().st_mtime_ns).encode())

    return h.hexdigest()
