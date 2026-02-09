from typing import List, Dict, Any
from pathlib import Path
import re
import numpy as np

from AI_Organize.core.models import FileContext, DirectoryContext
from AI_Organize.core.memory import MemoryStore
from AI_Organize.ai.file_context import read_file_snippet, summarize_file_content


# ----------------------------
# Helpers
# ----------------------------

def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in re.findall(r"[a-zA-Z0-9]{3,}", text)]


def _build_embedding_text(
    file_ctx: FileContext,
    dir_descriptions: list[str],
    extra_context: str | None = None,
) -> str:
    parts = [
        file_ctx.name,
        file_ctx.extension,
        file_ctx.mime_type or "",
        " ".join(dir_descriptions),
    ]
    if extra_context:
        parts.append(extra_context)

    return "\n".join(p for p in parts if p)


def _confidence_from_similarity(
    memory_score: float,
    ai_score: float,
) -> float:
    """
    Conservative confidence composition.
    Memory dominates, AI nudges.
    """
    if memory_score <= 0:
        return min(ai_score, 0.6)

    return min(1.0, (memory_score * 0.75) + (ai_score * 0.25))


def _sanitize_folder(name: str) -> str:
    name = name.strip().strip("\"'`")
    name = re.sub(r"[^\w\-\/ ]+", "", name)
    return name.replace(" ", "-")


# ----------------------------
# Core API
# ----------------------------

async def suggest_folders(
    *,
    file_ctx: FileContext,
    directories: List[DirectoryContext],
    memory: MemoryStore,
    settings: Dict[str, Any],
    max_suggestions: int = 3,
    model: str = None,
    root: Path = None,
) -> List[Dict[str, Any]]:
    """
    Return ranked folder suggestions for a file.

    Output format:
    [
        {
            "folder": "Career/Army",
            "confidence": 0.97,
            "source": "project+global",
            "auto_move_eligible": True,
        },
        ...
    ]
    """
    from akinus.ai.ollama import ollama_query, embed_with_ollama
    from akinus.utils.logger import log
    auto_threshold = settings.get("behavior", {}).get("auto_move_threshold", 0.95)

    # ----------------------------
    # Build embedding
    # ----------------------------

    dir_descriptions = [
        d.description for d in directories if d.description
    ]

    file_summary = None
    content = read_file_snippet(file_ctx.path)

    if content:
        file_summary = await summarize_file_content(
            filename=file_ctx.name,
            content=content,
            model=model,
        )

    embedding_text = _build_embedding_text(
        file_ctx,
        dir_descriptions,
        extra_context=file_summary,
    )
    embedding = embed_with_ollama(embedding_text)

    tokens = _tokenize(file_ctx.name)

    # ----------------------------
    # Query memory
    # ----------------------------

    project_hits = memory.get_similar(embedding, scope="project", limit=5)

    # 🔒 Only consult global memory if project memory has signal
    if project_hits:
        global_hits = memory.get_similar(embedding, scope="global", limit=5)
    else:
        global_hits = []

    suggestions: Dict[str, Dict[str, Any]] = {}

    def _accumulate(hit, source):
        score, meta = hit
        folder = meta["target_folder"]

        if folder not in suggestions:
            suggestions[folder] = {
                "folder": folder,
                "memory_score": score,
                "sources": {source},
            }
        else:
            suggestions[folder]["memory_score"] = max(
                suggestions[folder]["memory_score"], score
            )
            suggestions[folder]["sources"].add(source)

    for hit in project_hits:
        _accumulate(hit, "project")

    for hit in global_hits:
        _accumulate(hit, "global")

    # ----------------------------
    # AI fallback / enrichment
    # ----------------------------

    known_folders = sorted(
        {
            _sanitize_folder(d.name)
            for d in directories
            if d.name
        }
    )

    ai_prompt = f"""
You are organizing files on a Linux system.

STRICT RULES:
- Respond ONLY with folder names
- One folder name per line
- NO explanations
- NO reasoning
- NO extra text

You may suggest folders that don't exist yet but you must strictly adhere to the following rules:

Folder creation rules:
- Prefer existing folders when they make sense
- You may suggest creating ONE new folder ONLY IF:
  - No existing folder fits the file well, AND
  - The file content clearly indicates a category
- If the file is generic, ambiguous, or trivial, DO NOT invent a folder. In this case, suggest "Miscellaneous" if the folder does not already exist. 

Some questions that might help you decide on folder suggestions:
- Does the file name indicate a specific category or topic?
- Do the file extension and type suggest a particular use or category?
- If the file content is readable, what is it about? Does it indicate a clear category?
- Are there existing folders that match the file's name, type, or content? If so, prefer those.

Example good response:
Documents
Photos/Vacation
Music/Rock

Example Decisions:
- If the file is "report.docx" and there is an existing folder "Work", then since "report.docx" is a common work-related file, you should suggest "Work".
- If the file is "summer.jpg" and there is an existing folder "Photos/Vacation", then you should suggest "Photos/Vacation" because the file name indicates it's a photo and the name "summer" suggests it could be a vacation photo.
- If the file is "notes.txt" and there are no existing folders, but the content of "notes.txt" is about a project on machine learning, then you may suggest creating a new folder "Projects/Machine-Learning" because the content indicates a clear category and there are no existing folders that fit.
- If the file is "randomfile.bin" and there are existing folders "Documents", "Photos", and "Music", but the file name and content are generic and do not clearly fit any category, then you should suggest "Miscellaneous" if it doesn't already exist because the file is ambiguous and does not indicate a clear category.
- If the file is "budget.xlsx" and there is an existing folder "Finance", then you should suggest "Finance" because the file name and type indicate it's related to financial documents, and there is an existing folder that fits well.
- If the file is "project_plan.docx" and there are existing folders "Work" and "Projects", then you should suggest "Projects" because the file name indicates it's a project-related document, and "Projects" is a more specific match than "Work".
- If the file is "vacation_video.mp4" and there is an existing folder "Videos", then you should suggest "Videos" because the file type indicates it's a video, and there is an existing folder that fits well, even though the file name suggests it could be a vacation video.
- If the file is "todo.txt" and there are no existing folders, but the content of "todo.txt" is a list of tasks for home improvement, then you may suggest creating a new folder "Home-Improvement" because the content indicates a clear category and there are no existing folders that fit.
- If the file is "todo.txt" and there is an existing folder named ToDo, but the content of "todo.txt" is a list of tasks for home improvement, then you should suggest "ToDo" because the existing folder name is more specific than creating a new one.
- If the file is 123.txt and there is a folder named Text_Files, but the content of 123.txt is just a random assortment of numbers with no clear theme, then you should suggest "Text_Files" because the file is generic and does not indicate a clear category, and there is an existing folder that fits reasonably well.

This is a list of known folders that exist in the file's current directory:
{chr(10).join(known_folders)}

This is the file metadata:
- Name: {file_ctx.name}
- Type: {file_ctx.mime_type or "unknown"}

This is the summary of the file content:
{file_summary or "- No readable content available."}

Respond now:
"""
    await log(
        "DEBUG",
        "organizer",
        f"\n\t----[AI PROMPT]---- \
            \n\tfile={file_ctx.name}\n\tprompt={ai_prompt.replace(chr(10), ' | ')} \
            \n\tmodel={model or 'default'} \
        ",
    )
    raw_ai = await ollama_query(ai_prompt, model=model)
    await log(
        "DEBUG",
        "organizer",
        f"\n\t----[AI RESPONSE]---- \
            \n\tfile={file_ctx.name}\n\tresponse={raw_ai.replace(chr(10), ' | ')} \
            \n\tmodel={model or 'default'} \
        ",
    )

    known_folder_names = {
        _sanitize_folder(d.name)
        for d in directories
        if d.name
    }

    raw_lines = extract_folder_lines(raw_ai)
    ai_lines = [_sanitize_folder(l) for l in raw_lines]

    known_folder_set = {
        _sanitize_folder(d.name)
        for d in directories
        if d.name and d.path.parent == root
    }

    no_existing_folders = not known_folder_set

    for idx, folder in enumerate(ai_lines[:max_suggestions]):
        # Prompt is AI suggested a folder that doesn't exist.
        if folder in known_folder_set:
            source = "ai"
        else:
            source = "ai-new"

        suggestions[folder] = {
            "folder": folder,
            "memory_score": 0.0,
            "sources": {source},
        }

    # ----------------------------
    # Rank + score
    # ----------------------------

    ranked = []

    for entry in suggestions.values():
        mem_score = entry["memory_score"]
        ai_score = 0.7 if "ai" in entry["sources"] else 0.4

        confidence = _confidence_from_similarity(mem_score, ai_score)

        if "ai-new" in entry["sources"]:
            confidence *= 0.6  # hard cap invented folders

        ranked.append(
            {
                "folder": entry["folder"],
                "confidence": round(confidence, 3),
                "source": "+".join(sorted(entry["sources"])),
                "auto_move_eligible": confidence >= auto_threshold
                and ("project" in entry["sources"] or "global" in entry["sources"]),
            }
        )
    BEST_KNOWN_CONFIDENCE_CUTOFF = 0.35  # tune this

    best_known_conf = max(
        (s["confidence"] for s in ranked if s["source"] != "ai"),
        default=0.0,
    )

    allow_new_folders = (
        no_existing_folders
        or best_known_conf < BEST_KNOWN_CONFIDENCE_CUTOFF
    )

    for entry in ranked[:]:
        if "ai-new" in entry["source"] and not allow_new_folders:
            await log(
                "INFO",
                "organizer",
                f"[AI NEW FOLDER REJECTED] file={file_ctx.name} folder={entry['folder']}",
            )
            ranked.remove(entry)
            continue


    ranked.sort(key=lambda x: x["confidence"], reverse=True)

    await log(
        "INFO",
        "organizer",
        (
            f"[FOLDER DECISION CONTEXT] "
            f"file={file_ctx.name} "
            f"known_folders={len(known_folder_set)} "
            f"best_known_conf={best_known_conf:.2f} "
            f"allow_new_folders={allow_new_folders}"
        ),
    )

    return ranked[:max_suggestions]


# Extract plausible folder names from AI response, ignoring junk
def extract_folder_lines(raw: str) -> list[str]:
    """
    Extract plausible folder names from an LLM response.
    Ignores reasoning, explanations, and junk.
    """
    lines = []
    for line in raw.splitlines():
        line = line.strip()

        if not line:
            continue

        # Kill chain-of-thought and meta text
        if re.search(r"thinking|analysis|done thinking|reasoning", line, re.I):
            continue

        # Kill sentences
        if " " in line and not "/" in line:
            continue

        lines.append(line)

    return lines
