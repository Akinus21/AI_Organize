import json
from pathlib import Path
from typing import Dict, Any



from AI_Organize.core.scanner import scan_directory_async, IgnoreRules
from AI_Organize.core.models import build_file_context
from AI_Organize.core.memory import MemoryStore
from AI_Organize.core.trash import move_to_trash, cleanup_trash
from AI_Organize.ai.organizer import suggest_folders


# ----------------------------
# Settings
# ----------------------------

DEFAULT_SETTINGS = {
    "ai": {
        "model": "gpt-oss:120b-cloud",
        "enable_directory_summaries": False,  # 👈 IMPORTANT
    },
    "behavior": {
        "auto_move_enabled": True,
        "auto_move_threshold": 0.95,
        "ask_global_threshold": 0.60,
    },
    "trash": {"retention_days": 14},
}


def load_settings(project_root=None) -> Dict[str, Any]:
    from akinus.utils.app_details import PROJECT_ROOT, APP_NAME

    root = project_root or PROJECT_ROOT
    if root is None:
        return {}  # safe default for tests

    settings_path = root / "data" / "settings.json"

    if not settings_path.exists():
        return json.loads(json.dumps(DEFAULT_SETTINGS))

    with open(settings_path, "r", encoding="utf-8") as f:
        user_settings = json.load(f)

    merged = json.loads(json.dumps(DEFAULT_SETTINGS))
    for k, v in user_settings.items():
        if isinstance(v, dict) and k in merged:
            merged[k].update(v)
        else:
            merged[k] = v

    if project_root is not None:
        merged["_test_mode"] = True

    return merged


# ----------------------------
# CLI Orchestrator
# ----------------------------

async def run(
    *,
    project_root=None,
    max_depth: int = -1,
    ignore_patterns=None,
    auto_move_override: bool = None,
):
    settings = load_settings(project_root)

    # --- Apply defaults safely ---
    settings.setdefault("behavior", {})
    settings["behavior"].setdefault("auto_move_enabled", True)
    settings["behavior"].setdefault("auto_move_threshold", 0.95)
    settings["behavior"].setdefault("ask_global_threshold", 0.75)
    settings.setdefault("trash", {})
    settings["trash"].setdefault("retention_days", 30)
    settings.setdefault("ai", {})
    # --------------------------------

    use_ai = True

    # -- Lazy imports from akinus modules --
    from akinus.utils.app_details import PROJECT_ROOT as DEFAULT_ROOT, APP_NAME
    from AI_Organize.cli.model_resolution import resolve_ollama_model

    root = project_root or DEFAULT_ROOT
    if root is None:
        raise RuntimeError("Project root could not be determined")

    model = None

    is_test = project_root is not None

    def ensure_model():
        nonlocal model
        if model is not None:
            return model

        # 🧪 TEST MODE: never prompt
        if is_test:
            model = settings["ai"]["model"]
            return model

        model = resolve_ollama_model(settings, root)
        return model



    from akinus.utils.logger import log
    from akinus.ai.ollama import embed_with_ollama
    from akinus.ai.ollama import ollama_query
    # --------------------------------------


    if auto_move_override is not None:
        settings["behavior"]["auto_move_enabled"] = auto_move_override

    auto_enabled = settings["behavior"]["auto_move_enabled"]
    auto_threshold = settings["behavior"]["auto_move_threshold"]
    ask_global_threshold = settings["behavior"]["ask_global_threshold"]

    if auto_enabled:
        print(
            f"⚡ Auto-move is ENABLED (confidence ≥ {auto_threshold})\n"
            "   Files may be moved without prompting.\n"
            "   Disable with: --no-auto or data/settings.json\n"
        )

    ignore = IgnoreRules(ignore_patterns or [])
    memory = MemoryStore(root / "data" / "project.db")

    cleanup_trash(
        retention_days=settings["trash"]["retention_days"],
        project_root=root,
    )

    use_directory_ai = bool(settings.get("ai", {}).get("enable_directory_summaries", True))

    directories = await scan_directory_async(
        root,
        ignore=ignore,
        max_depth=max_depth,
        ai_call=ollama_query if use_directory_ai else None,
        model=ensure_model() if use_directory_ai else None,
    )

    for directory in directories:
        for filename in list(directory.files):
            file_path = directory.path / filename
            if not file_path.exists():
                continue

            if directory.path == root / "data":
                continue

            if filename == "project.db":
                continue

            # Skip internal files
            if file_path.name in {
                "project.db",
                ".ai_directory_summary.json",
                "README.md",
            }:
                continue

            file_ctx = build_file_context(file_path)

            suggestions = await suggest_folders(
                file_ctx=file_ctx,
                directories=directories,
                memory=memory,
                settings=settings,
                model=ensure_model(),
            )

            if not suggestions:
                continue

            best = suggestions[0]

            # Build embedding once (used for memory)
            embedding_text = f"{file_ctx.name} {file_ctx.extension} {file_ctx.mime_type or ''}"
            embedding = embed_with_ollama(embedding_text)

            # ----------------------------
            # Auto-move path
            # ----------------------------
            if (
                auto_enabled
                and best["auto_move_eligible"]
                and (directory.path / best["folder"]).exists()
            ):
                dest = directory.path / best["folder"]
                dest.mkdir(parents=True, exist_ok=True)
                file_path.rename(dest / file_path.name)

                memory.record_decision(
                    embedding=embedding,
                    extension=file_ctx.extension,
                    tokens=[],
                    target_folder=best["folder"],
                    directory_description=directory.description,
                    confidence=best["confidence"],
                )

                log(
                    "INFO",
                    "organize",
                    (
                        "[AUTO-MOVE]\n"
                        f"File: {file_ctx.name}\n"
                        f"Destination: {best['folder']}\n"
                        f"Confidence: {best['confidence']}\n"
                        f"Source: {best['source']}"
                    ),
                )
                continue

            # ----------------------------
            # Interactive path
            # ----------------------------
            print(f"\nFile: {file_ctx.name}")
            print("Suggested destinations:")
            for i, s in enumerate(suggestions, 1):
                print(
                    f"  [{i}] {s['folder']} "
                    f"(confidence: {s['confidence']})"
                )

            print("\n[Enter] accept #1 | [1-3] choose | [d] delete | [s] skip")
            choice = input("> ").strip().lower() or "1"

            if choice == "s":
                continue

            if choice == "d":
                # Skip files outside project root data scope (tests + safety)
                if file_path.name.lower() in {"readme.md", "license", ".gitignore"}:
                    continue

                print(
                    "Type DELETE to confirm moving to trash "
                    "(anything else cancels):"
                )
                if input("> ") == "DELETE":
                    move_to_trash(file_path, root)
                continue

            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(suggestions):
                    sel = suggestions[idx]
                    target = sel["folder"]

                    dest = directory.path / target
                    dest.mkdir(parents=True, exist_ok=True)
                    file_path.rename(dest / file_path.name)

                    # Medium-confidence global memory prompt
                    if (
                        ask_global_threshold
                        <= sel["confidence"]
                        < auto_threshold
                    ):
                        resp = input(
                            "This looks like general knowledge about you.\n"
                            "Save globally? [y/N]: "
                        ).strip().lower()
                        if resp != "y":
                            sel_conf = sel["confidence"] * 0.99
                        else:
                            sel_conf = sel["confidence"]
                    else:
                        sel_conf = sel["confidence"]

                    memory.record_decision(
                        embedding=embedding,
                        extension=file_ctx.extension,
                        tokens=[],
                        target_folder=target,
                        directory_description=directory.description,
                        confidence=sel_conf,
                    )

    print("✅ Organization complete.")
