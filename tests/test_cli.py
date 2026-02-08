from AI_Organize.cli import organize
import pytest


@pytest.mark.asyncio
async def test_cli_delete_to_trash(tmp_path, monkeypatch):
    project_root = tmp_path
    (project_root / "data").mkdir()

    test_file = project_root / "delete_me.txt"
    test_file.write_text("bye")


    async def fake_suggest_folders(**kwargs):
        return [
            {
                "folder": "Docs",
                "confidence": 0.5,
                "source": "ai",
                "auto_move_eligible": False,
            }
        ]

    monkeypatch.setattr(
        organize,
        "suggest_folders",
        fake_suggest_folders,
    )

    # First input = 'd', second = 'DELETE'
    inputs = iter(["d", "DELETE"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    await organize.run(project_root=project_root)

    trash_root = project_root / ".ai_organize_trash"
    assert trash_root.exists()
    assert any(trash_root.rglob("delete_me.txt"))

@pytest.mark.asyncio
async def test_cli_auto_move(tmp_path, monkeypatch):
    project_root = tmp_path
    (project_root / "data").mkdir()

    test_file = project_root / "auto.pdf"
    test_file.write_text("auto")

    target_dir = project_root / "Auto"
    target_dir.mkdir()


    async def fake_suggest_folders(**kwargs):
        return [
            {
                "folder": "Auto",
                "confidence": 0.99,
                "source": "project",
                "auto_move_eligible": True,
            }
        ]

    monkeypatch.setattr(
        organize,
        "suggest_folders",
        fake_suggest_folders,
    )

    # No input should be called
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("input() called"))

    await organize.run(project_root=project_root)

    assert not test_file.exists()
    assert (target_dir / "auto.pdf").exists()
