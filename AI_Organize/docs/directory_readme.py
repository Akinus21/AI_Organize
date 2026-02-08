from pathlib import Path
from typing import Optional
import re


SECTION_HEADER = "# Directory Description"


def _split_sections(text: str):
    """
    Split markdown into a list of (header, body) tuples.
    Header includes leading '# '.
    """
    pattern = re.compile(r"(^# .*$)", re.MULTILINE)
    parts = pattern.split(text)

    sections = []
    if not parts[0].strip():
        parts = parts[1:]

    for i in range(0, len(parts), 2):
        header = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((header, body))

    return sections


def _rebuild_markdown(sections):
    out = []
    for header, body in sections:
        out.append(f"{header}\n{body.strip()}\n")
    return "\n".join(out).rstrip() + "\n"


def update_directory_description(
    directory: Path,
    description: str,
) -> None:
    """
    Create or update the '# Directory Description' section
    in a directory's README.md without touching other content.
    """
    readme = directory / "README.md"
    description = description.strip()

    # --------------------------------
    # README does not exist → create
    # --------------------------------
    if not readme.exists():
        readme.write_text(
            f"{SECTION_HEADER}\n{description}\n",
            encoding="utf-8",
        )
        return

    text = readme.read_text(encoding="utf-8")

    # --------------------------------
    # README exists → update section
    # --------------------------------
    sections = _split_sections(text)

    updated = False
    new_sections = []

    for header, body in sections:
        if header == SECTION_HEADER:
            new_sections.append((header, f"\n{description}\n"))
            updated = True
        else:
            new_sections.append((header, body))

    # --------------------------------
    # Section missing → insert at top
    # --------------------------------
    if not updated:
        new_sections.insert(
            0,
            (SECTION_HEADER, f"\n{description}\n"),
        )

    readme.write_text(
        _rebuild_markdown(new_sections),
        encoding="utf-8",
    )
