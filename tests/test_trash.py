from pathlib import Path
from AI_Organize.core.trash import move_to_trash, cleanup_trash


def test_move_to_trash(tmp_path: Path):
    project_root = tmp_path
    test_file = project_root / "example.txt"
    test_file.write_text("hello")

    trashed = move_to_trash(test_file, project_root)

    assert not test_file.exists()
    assert trashed.exists()
    assert trashed.read_text() == "hello"


def test_cleanup_trash(tmp_path: Path):
    trash_dir = tmp_path / ".ai_organize_trash" / "2000-01-01"
    trash_dir.mkdir(parents=True)
    (trash_dir / "old.txt").write_text("old")

    cleanup_trash(retention_days=0, project_root=tmp_path)

    assert not trash_dir.exists()
