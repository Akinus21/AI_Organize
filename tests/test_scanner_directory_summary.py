import pytest
from pathlib import Path

from AI_Organize.core.scanner import scan_directory


# ----------------------------
# Helpers
# ----------------------------

async def fake_ai_call(prompt: str, model: str):
    return "This directory contains test files."


def write_file(path: Path, content: str):
    path.write_text(content, encoding="utf-8")


# ----------------------------
# Tests
# ----------------------------

@pytest.mark.asyncio
async def test_scanner_generates_directory_summary(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    write_file(tmp_path / "docs" / "a.txt", "hello")

    results = await scan_directory(
        tmp_path,
        ai_call=fake_ai_call,
        model="dummy",
    )

    docs = next(d for d in results if d.name == "docs")
    assert docs.description == "This directory contains test files."


@pytest.mark.asyncio
async def test_scanner_writes_readme_with_description(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    write_file(docs / "a.txt", "hello")

    await scan_directory(
        tmp_path,
        ai_call=fake_ai_call,
        model="dummy",
    )

    readme = docs / "README.md"
    assert readme.exists()

    content = readme.read_text()
    assert "# Directory Description" in content
    assert "This directory contains test files." in content


@pytest.mark.asyncio
async def test_scanner_preserves_existing_readme_sections(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()

    write_file(
        docs / "README.md",
        """# Directory Description
Old description

# Notes
Do not remove this.
"""
    )

    write_file(docs / "a.txt", "hello")

    await scan_directory(
        tmp_path,
        ai_call=fake_ai_call,
        model="dummy",
    )

    content = (docs / "README.md").read_text()

    assert "# Notes" in content
    assert "Do not remove this." in content
    assert "This directory contains test files." in content
    assert "Old description" not in content


@pytest.mark.asyncio
async def test_scanner_uses_cache_when_directory_unchanged(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    write_file(docs / "a.txt", "hello")

    call_count = 0

    async def counting_ai(prompt: str, model: str):
        nonlocal call_count
        call_count += 1
        return "Cached summary"

    # First scan → AI called
    await scan_directory(
        tmp_path,
        ai_call=counting_ai,
        model="dummy",
    )

    # Second scan → should hit cache
    await scan_directory(
        tmp_path,
        ai_call=counting_ai,
        model="dummy",
    )

    assert call_count == 1


@pytest.mark.asyncio
async def test_scanner_refreshes_summary_when_files_change(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    write_file(docs / "a.txt", "hello")

    summaries = []

    async def changing_ai(prompt: str, model: str):
        summaries.append(prompt)
        return f"Summary {len(summaries)}"

    await scan_directory(
        tmp_path,
        ai_call=changing_ai,
        model="dummy",
    )

    write_file(docs / "b.txt", "new file")

    await scan_directory(
        tmp_path,
        ai_call=changing_ai,
        model="dummy",
    )

    assert len(summaries) == 2


@pytest.mark.asyncio
async def test_scanner_never_fails_if_ai_errors(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    write_file(docs / "a.txt", "hello")

    async def failing_ai(prompt: str, model: str):
        raise RuntimeError("AI down")

    results = await scan_directory(
        tmp_path,
        ai_call=failing_ai,
        model="dummy",
    )

    docs_ctx = next(d for d in results if d.name == "docs")
    assert docs_ctx.description is None
