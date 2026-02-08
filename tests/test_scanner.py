from pathlib import Path
from AI_Organize.core.scanner import scan_directory, IgnoreRules
from AI_Organize.core.models import build_file_context


def test_scan_directory_basic(tmp_path: Path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.pdf").write_text("b")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.txt").write_text("c")

    ignore = IgnoreRules([])
    results = scan_directory(tmp_path, ignore, max_depth=1)

    root = results[0]
    assert "a.txt" in root.files
    assert "b.pdf" in root.files
    assert "sub" in root.subdirectories


def test_ignore_glob(tmp_path: Path):
    (tmp_path / "keep.txt").write_text("ok")
    (tmp_path / "skip.pdf").write_text("no")

    ignore = IgnoreRules(["*.pdf"])
    results = scan_directory(tmp_path, ignore)

    root = results[0]
    assert "keep.txt" in root.files
    assert "skip.pdf" not in root.files


def test_build_file_context(tmp_path: Path):
    f = tmp_path / "doc.md"
    f.write_text("hello")

    ctx = build_file_context(f)

    assert ctx.name == "doc.md"
    assert ctx.extension == ".md"
    assert ctx.size_bytes > 0
