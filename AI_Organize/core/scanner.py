import asyncio
import json
import hashlib
from pathlib import Path
from typing import List

from AI_Organize.core.models import DirectoryContext
from AI_Organize.docs.directory_fingerprint import directory_fingerprint
from AI_Organize.docs.directory_summary import (
    get_or_update_directory_summary,
)


# ============================================================
# Ignore rules
# ============================================================

class IgnoreRules:
    def __init__(self, patterns: List[str]):
        self.patterns = patterns or []

    def should_ignore(self, path: Path) -> bool:
        name = path.name
        for pat in self.patterns:
            if path.match(pat) or name == pat:
                return True
        return False


# ============================================================
# ASYNC IMPLEMENTATION (single source of truth)
# ============================================================

async def scan_directory_async(
    root: Path,
    *,
    ignore: IgnoreRules | None = None,
    max_depth: int = -1,
    ai_call: str | None = None,
    model: str | None = None,
) -> List[DirectoryContext]:
    """
    Scan a directory tree and return DirectoryContext objects.

    - Attaches cached AI-generated directory summaries
    - Preserves README.md content except # Directory Description
    - Avoids AI calls when directory contents haven't changed
    - NEVER fails if AI fails
    """

    use_ai = bool(ai_call and model)

    root = root.resolve()
    contexts: List[DirectoryContext] = []

    INTERNAL_FILES = {
        ".ai_directory_summary.json",
        "README.md",
    }

    if not root.exists():
        return contexts

    def depth_ok(path: Path) -> bool:
        if max_depth < 0:
            return True
        return len(path.relative_to(root).parts) <= max_depth

    # 🔑 IMPORTANT: include root itself
    directories = [root] + sorted(p for p in root.rglob("*") if p.is_dir())

    for path in directories:
        if not depth_ok(path):
            continue

        if path != root and ignore and ignore.should_ignore(path):
            continue

        summary = None

        if use_ai and path != root:
            try:
                summary = await get_or_update_directory_summary(
                    path,
                    model=model,
                    ai_call=ai_call,
                )
            except Exception:
                summary = None

        from AI_Organize.docs.directory_readme import update_directory_description

        if summary:
            update_directory_description(path, summary)

        files = []
        subdirs = []

        for child in path.iterdir():
            if ignore and ignore.should_ignore(child):
                continue
            if child.name in INTERNAL_FILES:
                continue
            if child.is_file():
                files.append(child.name)
            elif child.is_dir():
                subdirs.append(child.name)

        ctx = DirectoryContext(
            path=path,
            name=path.name,
            description=summary,
            files=files,
            subdirectories=subdirs,
        )
        contexts.append(ctx)

    # Ensure root directory is first
    contexts.sort(key=lambda c: len(c.path.parts))

    return contexts


# ============================================================
# SYNC WRAPPER (for legacy tests + simple use)
# ============================================================

def scan_directory(
    root: Path,
    ignore=None,
    max_depth: int = -1,
    *,
    ai_call: str | None = None,
    model: str | None = None,
):
    """
    Sync wrapper for scan_directory_async.
    Safe under pytest-asyncio.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop → safe to create one
        return asyncio.run(
            scan_directory_async(
                root,
                ignore=ignore,
                max_depth=max_depth,
                ai_call=ai_call,
                model=model,
            )
        )
    else:
        # Running loop → must create a task
        return loop.create_task(
            scan_directory_async(
                root,
                ignore=ignore,
                max_depth=max_depth,
                ai_call=ai_call,
                model=model,
            )
        )


