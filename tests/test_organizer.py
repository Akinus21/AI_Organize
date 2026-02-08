import numpy as np
import pytest
from AI_Organize.ai.organizer import suggest_folders
from AI_Organize.core.models import FileContext, DirectoryContext
from AI_Organize.core.memory import MemoryStore
from pathlib import Path


@pytest.mark.asyncio
async def test_organizer_ranking(tmp_path: Path, monkeypatch):
    file_ctx = FileContext(
        path=tmp_path / "test.pdf",
        name="test.pdf",
        extension=".pdf",
        size_bytes=100,
        mime_type="application/pdf",
    )

    directories = [
        DirectoryContext(path=tmp_path, name="Docs"),
        DirectoryContext(path=tmp_path, name="Archive"),
    ]

    memory = MemoryStore(tmp_path / "project.db")
    memory.clear("project")

    settings = {
        "ai": {"model": "dummy"},
        "behavior": {"auto_move_threshold": 0.95},
    }

    suggestions = await suggest_folders(
        file_ctx=file_ctx,
        directories=directories,
        memory=memory,
        settings=settings,
    )

    assert suggestions
    assert suggestions[0]["folder"] in {"Docs", "Archive"}
