from dataclasses import dataclass, field
import mimetypes
import os
from pathlib import Path
from typing import Optional, List, Dict


@dataclass
class FileContext:
    """
    Normalized representation of a file for classification and organization.

    This object intentionally contains NO file content. All AI decisions
    should be made from metadata and learned context.
    """
    path: Path
    name: str
    extension: str
    size_bytes: int
    mime_type: Optional[str] = None

    # Optional, derived or enriched data
    stem: Optional[str] = None
    keywords: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.stem is None:
            self.stem = self.path.stem
        if self.extension and not self.extension.startswith("."):
            self.extension = f".{self.extension}"


@dataclass
class DirectoryContext:
    """
    Representation of a directory and its semantic meaning.

    Used for:
    - README generation
    - AI folder purpose understanding
    - File placement context
    """
    path: Path
    name: str

    # README-related
    description: Optional[str] = None

    # Contents (names only; no recursion here)
    files: List[str] = field(default_factory=list)
    subdirectories: List[str] = field(default_factory=list)

    # Optional metadata
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None




def build_file_context(path: Path) -> FileContext:
    """
    Build a FileContext from a filesystem path.

    This is intentionally lightweight:
    - NO file content is read
    - Metadata only
    """
    stat = path.stat()

    mime_type, _ = mimetypes.guess_type(path.name)

    return FileContext(
        path=path,
        name=path.name,
        extension=path.suffix,
        size_bytes=stat.st_size,
        mime_type=mime_type,
    )