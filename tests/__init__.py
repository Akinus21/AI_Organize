# Auto-generated __init__.py

from . import test_cli
from .test_cli import test_cli_auto_move
from .test_cli import test_cli_delete_to_trash
from . import test_memory
from .test_memory import test_memory_store_roundtrip
from . import test_models
from .test_models import test_directory_context_defaults
from .test_models import test_file_context_normalization
from . import test_organizer
from .test_organizer import test_organizer_ranking
from . import test_scanner
from .test_scanner import test_build_file_context
from .test_scanner import test_ignore_glob
from .test_scanner import test_scan_directory_basic
from . import test_trash
from .test_trash import test_cleanup_trash
from .test_trash import test_move_to_trash

__all__ = [
    "test_cli",
    "test_memory",
    "test_models",
    "test_organizer",
    "test_scanner",
    "test_trash",
    "test_build_file_context",
    "test_cleanup_trash",
    "test_cli_auto_move",
    "test_cli_delete_to_trash",
    "test_directory_context_defaults",
    "test_file_context_normalization",
    "test_ignore_glob",
    "test_memory_store_roundtrip",
    "test_move_to_trash",
    "test_organizer_ranking",
    "test_scan_directory_basic",
]
