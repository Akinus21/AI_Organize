import numpy as np
import pytest
from pathlib import Path
from AI_Organize.core.memory import MemoryStore


def test_memory_store_roundtrip(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "project.db"
    memory = MemoryStore(db_path)

    embedding = np.ones(10)

    memory.record_decision(
        embedding=embedding,
        extension=".pdf",
        tokens=["military"],
        target_folder="Career",
        directory_description="Military docs",
        confidence=0.9,
    )

    hits = memory.get_similar(embedding, scope="project")
    assert hits

