import pytest
from pathlib import Path

from AI_Organize.docs.directory_summary import (
    _collect_directory_context,
    generate_directory_summary,
    MAX_FILES_PER_DIR,
)


# ----------------------------
# Helpers
# ----------------------------

def create_text_file(path: Path, content: str):
    path.write_text(content, encoding="utf-8")


def create_binary_file(path: Path):
    path.write_bytes(b"\x00\x01\x02\x03\x04")


# ----------------------------
# Tests
# ----------------------------

def test_collects_directory_name(tmp_path: Path):
    ctx = _collect_directory_context(tmp_path)
    assert tmp_path.name in ctx


def test_collects_subdirectories(tmp_path: Path):
    (tmp_path / "sub1").mkdir()
    (tmp_path / "sub2").mkdir()

    ctx = _collect_directory_context(tmp_path)
    assert "sub1" in ctx
    assert "sub2" in ctx


def test_collects_filenames(tmp_path: Path):
    create_text_file(tmp_path / "a.txt", "hello")
    create_text_file(tmp_path / "b.md", "world")

    ctx = _collect_directory_context(tmp_path)
    assert "a.txt" in ctx
    assert "b.md" in ctx


def test_samples_text_file_contents(tmp_path: Path):
    create_text_file(tmp_path / "notes.txt", "important content")

    ctx = _collect_directory_context(tmp_path)
    assert "important content" in ctx
    assert "--- notes.txt ---" in ctx


def test_ignores_binary_files(tmp_path: Path):
    create_binary_file(tmp_path / "image.png")

    ctx = _collect_directory_context(tmp_path)
    assert "image.png" in ctx  # filename listed
    assert "--- image.png ---" not in ctx  # no content sampled


def test_limits_number_of_sampled_files(tmp_path: Path):
    for i in range(MAX_FILES_PER_DIR + 5):
        create_text_file(
            tmp_path / f"file{i}.txt",
            f"content {i}",
        )

    ctx = _collect_directory_context(tmp_path)

    sampled = ctx.count("--- file")
    assert sampled == MAX_FILES_PER_DIR


@pytest.mark.asyncio
async def test_generate_directory_summary_calls_ai(tmp_path: Path):
    create_text_file(tmp_path / "readme.txt", "example")

    async def fake_ollama(prompt: str, model: str):
        assert "Directory purpose" in prompt
        assert "readme.txt" in prompt
        return "This directory contains documentation files."

    summary = await generate_directory_summary(
        tmp_path,
        model="dummy-model",
        ai_call=fake_ollama,
    )

    assert summary == "This directory contains documentation files."
