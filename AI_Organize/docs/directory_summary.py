import json
from pathlib import Path
import re
from typing import List, Optional, Callable
import mimetypes

from AI_Organize.docs.directory_fingerprint import directory_fingerprint

THINKING_BLOCK_RE = re.compile(
    r"(thinking\.{0,3}|analysis:).*?(done thinking\.{0,3})",
    re.IGNORECASE | re.DOTALL,
)


MAX_FILE_BYTES = 20_000       # hard cap per file
MAX_FILES_PER_DIR = 10        # avoid token explosions
MAX_CHARS_PER_FILE = 3_000    # safety after decode


TEXT_MIME_PREFIXES = (
    "text/",
    "application/json",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
    "application/toml",
)

def strip_reasoning(text: str) -> str:
    # Remove thinking blocks
    cleaned = THINKING_BLOCK_RE.sub("", text)

    # Also remove standalone markers if present
    cleaned = re.sub(
        r"^(thinking\.{0,3}|analysis:|done thinking\.{0,3})$",
        "",
        cleaned,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    return cleaned.strip()

async def get_or_update_directory_summary(
    directory: Path,
    *,
    model: str,
    ai_call: Callable[[str, str], str],
) -> Optional[str]:
    """
    Return a cached directory summary if unchanged,
    otherwise regenerate it using AI and update cache.
    """

    cache_path = directory / ".ai" / ".ai_directory_summary.json"
    fingerprint = directory_fingerprint(directory)

    # --- Cache hit ---
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            if cached.get("fingerprint") == fingerprint:
                return cached.get("summary")
        except Exception:
            pass  # corrupt cache → regenerate

    # --- Cache miss / changed ---
    try:
        summary = await generate_directory_summary(
            directory,
            model=model,
            ai_call=ai_call,
        )
    except Exception:
        return None  # AI failure must never break scan

    # --- Write cache ---
    try:
        cache_path.write_text(
            json.dumps(
                {
                    "fingerprint": fingerprint,
                    "summary": summary,
                },
                indent=2,
            )
        )
    except Exception:
        pass  # cache write failure is non-fatal

    return summary

def _is_text_file(path: Path) -> bool:
    mime, _ = mimetypes.guess_type(path.name)
    if not mime:
        return False
    return any(mime.startswith(p) for p in TEXT_MIME_PREFIXES)


def _read_file_snippet(path: Path) -> str:
    try:
        data = path.read_bytes()[:MAX_FILE_BYTES]
        text = data.decode("utf-8", errors="ignore")
        return text[:MAX_CHARS_PER_FILE].strip()
    except Exception:
        return ""


def _collect_directory_context(directory: Path) -> str:
    """
    Build a text corpus representing the directory.
    """
    parts: List[str] = []

    # ----------------------------
    # Structural context
    # ----------------------------
    parts.append("Directory name:")
    parts.append(directory.name)

    subdirs = [
        p.name for p in directory.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ]

    if subdirs:
        parts.append("\nSubdirectories:")
        parts.extend(subdirs)

    # ----------------------------
    # File-level context
    # ----------------------------
    files = [
        p for p in directory.iterdir()
        if p.is_file() and not p.name.startswith(".")
    ]

    if files:
        parts.append("\nFiles:")
        parts.extend(p.name for p in files)

    # ----------------------------
    # File content sampling
    # ----------------------------
    sampled = 0
    for file in files:
        if sampled >= MAX_FILES_PER_DIR:
            break

        if not _is_text_file(file):
            continue

        snippet = _read_file_snippet(file)
        if not snippet:
            continue

        parts.append(f"\n--- {file.name} ---")
        parts.append(snippet)
        sampled += 1

    return "\n".join(parts)

from pathlib import Path
from typing import Callable, Awaitable

async def generate_directory_summary(
    directory: Path,
    *,
    model: str,
    ai_call: Callable[[str, str], Awaitable[str]] | None = None,
) -> str:
    """
    Generate a natural-language description of a directory
    based on filenames and file contents.
    """

    if not model:
        raise ValueError("AI model must be provided for directory summary generation")
    
    # 🔹 Lazy, controlled import (ONLY if needed)
    if ai_call is None:
        from akinus.ai.ollama import ollama_query
        ai_call = ollama_query

    context = _collect_directory_context(directory)

    prompt = f"""
You are summarizing the purpose of a directory on a Linux system.

Based on the following information, write a short paragraph
describing what this directory is for.

Focus on intent, not listing files.

{context}

Directory purpose:
""".strip()

    response = await ai_call(prompt, model)
    response = strip_reasoning(response)

    return response.strip()

