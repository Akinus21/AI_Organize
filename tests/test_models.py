from pathlib import Path
from AI_Organize.core.models import FileContext, DirectoryContext


def test_file_context_normalization(tmp_path: Path):
    f = tmp_path / "example.TXT"
    f.write_text("hello")

    ctx = FileContext(
        path=f,
        name=f.name,
        extension="txt",
        size_bytes=5,
        mime_type="text/plain",
    )

    assert ctx.extension == ".txt"
    assert ctx.stem == "example"
    assert ctx.name == "example.TXT"


def test_directory_context_defaults(tmp_path: Path):
    d = DirectoryContext(
        path=tmp_path,
        name="root",
    )

    assert d.files == []
    assert d.subdirectories == []
    assert d.description is None
