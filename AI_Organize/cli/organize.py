import asyncio
import json
from pathlib import Path
from typing import Dict, Any

from AI_Organize.core.scanner import scan_directory_async, IgnoreRules
from AI_Organize.core.models import DirectoryContext, build_file_context
from AI_Organize.core.memory import MemoryStore
from AI_Organize.core.trash import move_to_trash, cleanup_trash
from AI_Organize.ai.organizer import suggest_folders

# ----------------------------
# Settings
# ----------------------------

DEFAULT_SETTINGS = {
    "ai": {
        "model": "gpt-oss:120b-cloud",
        "enable_directory_summaries": True,
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

    root = project_root

    if root is None:
        return {}  # safe default for tests

    settings_path = root / ".ai" / "settings.json"

    if not settings_path.exists():
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=2)

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

def status(msg: str):
    print("\r" + " " * 100, end="")   # clear line
    print(f"\r{msg}", end="", flush=True)

def clear_status():
    print("\r" + " " * 120 + "\r", end="", flush=True)


async def run(
    *,
    project_root=None,
    max_depth: int = -1,
    ignore_patterns=None,
    auto_move_override: bool = None,
):
    from akinus.utils.logger import log, LOG_FILE
    await log("INFO", "organize", "============================= RUN STARTED ============================")
     # -- Lazy imports from akinus modules --
    from akinus.utils.app_details import PROJECT_ROOT as DEFAULT_ROOT, APP_NAME
    from AI_Organize.cli.model_resolution import resolve_ollama_model
    from akinus.ai.ollama import embed_with_ollama
    from akinus.ai.ollama import ollama_query

    root = project_root or DEFAULT_ROOT

    if root is None:
        raise RuntimeError("Project root could not be determined")
    
    # Ensure .ai workspace exists
    ai_dir = root / ".ai"
    if not ai_dir.exists():
        ai_dir.mkdir(parents=True, exist_ok=True)
        await log("INFO", "organize", f"Created workspace directory: {ai_dir}")


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

    # await log(
    #     "DEBUG",
    #     "organize",
    #     f"Using folder root: {root}",
    # )

    model = None

    is_test = project_root == DEFAULT_ROOT

    async def ensure_model():
        nonlocal model
        if model is not None:
            return model

        # 🧪 TEST MODE: never prompt
        if is_test:
            await log(
                "DEBUG",
                "organize",
                "Test mode detected - using default model without resolution",
            )
            model = settings["ai"]["model"]
            return model

        model = await resolve_ollama_model(settings, root)
        return model
    # --------------------------------------


    if auto_move_override is not None:
        settings["behavior"]["auto_move_enabled"] = auto_move_override

    auto_enabled = settings["behavior"]["auto_move_enabled"]
    auto_threshold = settings["behavior"]["auto_move_threshold"]
    ask_global_threshold = settings["behavior"]["ask_global_threshold"]

    if auto_enabled:
        clear_status()
        print(
            f"⚡ Auto-move is ENABLED (confidence ≥ {auto_threshold})\n"
            "   Files may be moved without prompting.\n"
            "   Disable with: --no-auto or data/settings.json\n"
        )

    ignore = IgnoreRules(ignore_patterns or [])
    memory = MemoryStore(root / ".ai" / "project.db")

    cleanup_trash(
        retention_days=settings["trash"]["retention_days"],
        project_root=root,
    )

    # await log(
    #     "DEBUG",
    #     "organize",
    #     f"\n\tSettings: {json.dumps(settings, indent=2)}\n"
    # )

    use_directory_ai = bool(settings.get("ai", {}).get("enable_directory_summaries", True))

    directories = await scan_directory_async(
        root,
        ignore=ignore,
        max_depth=max_depth,
        ai_call=ollama_query if use_directory_ai else None,
        model=await ensure_model() if use_directory_ai else None,
    )

    for directory in directories:
        for filename in list(directory.files):
            file_path = directory.path / filename
            if not file_path.exists():
                continue

            if directory.path == root / ".ai":
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

            status(f"📁 Processing file: {file_ctx.name}")

            # await log(
            #     "DEBUG",
            #     "organize",
            #     f"\n\tDirectory Context: {[d for d in directories]}",
            # )

            valid_destinations = [
                DirectoryContext(
                    path=p,
                    name=p.name,
                    description=None,
                    files=[],
                    subdirectories=[],
                )
                for p in root.iterdir()
                if p.is_dir()
                and not p.name.startswith(".")
                and p.name != ".ai"
            ]

            # await log(
            #     "DEBUG",
            #     "organize",
            #     f"\n\tValid destinations for '{file_ctx.name}': {[d.path for d in valid_destinations]}",
            # )

            suggestions = await suggest_folders(
                file_ctx=file_ctx,
                directories=valid_destinations,
                memory=memory,
                settings=settings,
                model=await ensure_model(),
                root=root,
            )

            if not suggestions:
                await log(
                    "INFO",
                    "organize",
                    f"[NO SUGGESTIONS] file={file_ctx.name}",
                )
                clear_status()
                print(f"\nNo suggestions for '{file_ctx.name}'. Skipping.")
                continue

            best = suggestions[0]

            await log(
                "INFO",
                "organize",
                (
                    f"[AI ANALYSIS] "
                    f"file={file_ctx.name} | "
                    f"top_choice={best['folder']} | "
                    f"confidence={best['confidence']} | "
                    f"source={best['source']} | "
                    f"auto_move_eligible={best['auto_move_eligible']}"
                ),
            )

            # Build embedding once (used for memory)
            embedding_text = f"{file_ctx.name} {file_ctx.extension} {file_ctx.mime_type or ''}"
            embedding = embed_with_ollama(embedding_text)

            # ----------------------------
            # Auto-move path
            # ----------------------------
            if (
                auto_enabled
                and best["auto_move_eligible"]
                and (root / best["folder"]).exists()
            ):
                clear_status()
                print(
                    f"\nAuto-moving '{file_ctx.name}' to '{best['folder']}' "
                    f"(confidence: {best['confidence']})\n"
                )
                dest = root / best["folder"]
                dest.mkdir(parents=True, exist_ok=True)
                file_path.rename(dest / file_path.name)
                await log(
                    "INFO",
                    "organize",
                    f"[FILE-MOVED] {file_ctx.name} → {dest}",
                )

                memory.record_decision(
                    embedding=embedding,
                    extension=file_ctx.extension,
                    tokens=[],
                    target_folder=best["folder"],
                    directory_description=directory.description,
                    confidence=best["confidence"],
                )

                await log(
                    "INFO",
                    "organize",
                    (
                        f"[AUTO-MOVE] "
                        f"file={file_ctx.name} | "
                        f"destination={best['folder']} | "
                        f"confidence={best['confidence']} | "
                        f"threshold={auto_threshold}"
                    ),
                )
                continue
            
            if auto_enabled:
                if not best["auto_move_eligible"]:
                    await log(
                        "INFO",
                        "organize",
                        f"[AUTO-MOVE SKIPPED] file={file_ctx.name} reason=not_eligible",
                    )
                elif best["confidence"] < auto_threshold:
                    await log(
                        "INFO",
                        "organize",
                        (
                            f"[AUTO-MOVE SKIPPED] "
                            f"file={file_ctx.name} "
                            f"confidence={best['confidence']} < threshold={auto_threshold}"
                        ),
                    )

            # ----------------------------
            # Interactive path
            # ----------------------------
            clear_status()
            print(f"\nFile: {file_ctx.name}")
            print("Suggested destinations:")
            for i, s in enumerate(suggestions, 1):
                print(
                    f"  [{i}] {s['folder']} "
                    f"(confidence: {s['confidence']})"
                )

            print("\n[Enter] accept #1 | [1-3] choose | [o] Other Folder | [n] New Folder | [d] delete | [s] skip")
            choice = input("> ").strip().lower() or "1"

            if choice == "s":
                await log(
                    "INFO",
                    "organize",
                    f"[SKIP] file={file_ctx.name}",
                )
                continue

            if choice == "d":
                # Skip files outside project root data scope (tests + safety)
                if file_path.name.lower() in {"readme.md", "license", ".gitignore"}:
                    await log(
                        "WARNING",
                        "organize",
                        f"[DELETE] file={file_ctx.name}",
                    )
                    continue
                clear_status()
                print(
                    "Type DELETE to confirm moving to trash "
                    "(anything else cancels):"
                )
                if input("> ") == "DELETE":
                    move_to_trash(file_path, root)
                continue

            if choice == "n":
                clear_status()
                print("Enter new folder name:")
                raw = input("> ").strip()

                # Remove surrounding quotes if present
                if (
                    (raw.startswith('"') and raw.endswith('"')) or
                    (raw.startswith("'") and raw.endswith("'"))
                ):
                    new_folder = raw[1:-1].strip()
                else:
                    new_folder = raw

                if new_folder:
                    dest = root / new_folder
                    dest.mkdir(parents=True, exist_ok=True)

                    if file_path.parent.resolve() != dest.resolve():
                        file_path.rename(dest / file_path.name)
                        await log(
                            "INFO",
                            "organize",
                            f"[FILE-MOVED] {file_ctx.name} → {dest}",
                        )

                    memory.record_decision(
                        embedding=embedding,
                        extension=file_ctx.extension,
                        tokens=[],
                        target_folder=new_folder,
                        directory_description=directory.description,
                        confidence=0.5,
                    )

                await log(
                    "INFO",
                    "organize",
                    (
                        f"[NEW-FOLDER] "
                        f"file={file_ctx.name} | "
                        f"folder={new_folder} | "
                        f"confidence=0.5"
                    ),
                )

                continue

            if choice == "o":
                clear_status()
                print("Enter exact folder name (relative to current directory):")
                other_folder = input("> ").strip()
                if other_folder:
                    dest = root / other_folder
                    dest.mkdir(parents=True, exist_ok=True)
                    file_path.rename(dest / file_path.name)
                    await log(
                        "INFO",
                        "organize",
                        f"[FILE-MOVED] {file_ctx.name} → {dest}",
                    )

                    memory.record_decision(
                        embedding=embedding,
                        extension=file_ctx.extension,
                        tokens=[],
                        target_folder=other_folder,
                        directory_description=directory.description,
                        confidence=0.5,  # Medium confidence for user-created folders
                    )

                await log(
                    "INFO",
                    "organize",
                    (
                        f"[MANUAL-MOVE] "
                        f"file={file_ctx.name} | "
                        f"destination={other_folder} | "
                        f"confidence=0.5"
                    ),
                )

                continue

            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(suggestions):
                    sel = suggestions[idx]
                    target = sel["folder"]

                    dest = root / target
                    dest.mkdir(parents=True, exist_ok=True)
                    file_path.rename(dest / file_path.name)
                    await log(
                        "INFO",
                        "organize",
                        f"[FILE-MOVED] {file_ctx.name} → {dest}",
                    )

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

                await log(
                    "INFO",
                    "organize",
                    (
                        f"[USER-SELECT] "
                        f"file={file_ctx.name} | "
                        f"destination={target} | "
                        f"final_confidence={sel_conf}"
                    ),
                )

    await asyncio.sleep(0.05)

    clear_status()
    print("✅ Organization complete.")
    print()
    print("📜 Detailed log for this run is available at:")
    print(f"   {LOG_FILE}")
    print()
    print("View it with:")
    print(f"   less {LOG_FILE}")
    print(f"   tail -f {LOG_FILE}")