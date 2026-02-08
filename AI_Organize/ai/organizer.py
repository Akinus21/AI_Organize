from typing import List, Dict, Any
from pathlib import Path
import re
import numpy as np

from AI_Organize.core.models import FileContext, DirectoryContext
from AI_Organize.core.memory import MemoryStore

# ----------------------------
# Helpers
# ----------------------------

def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in re.findall(r"[a-zA-Z0-9]{3,}", text)]


def _build_embedding_text(
    file_ctx: FileContext,
    dir_descriptions: List[str],
) -> str:
    parts = [
        file_ctx.name,
        file_ctx.extension or "",
        file_ctx.mime_type or "",
    ]
    parts.extend(dir_descriptions)
    return " ".join(parts)


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
    model_name = settings.get("ai", {}).get("model", "llama3.2")
    auto_threshold = settings.get("behavior", {}).get("auto_move_threshold", 0.95)

    # ----------------------------
    # Build embedding
    # ----------------------------

    dir_descriptions = [
        d.description for d in directories if d.description
    ]

    embedding_text = _build_embedding_text(file_ctx, dir_descriptions)
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

Known folders:
{chr(10).join(known_folders)}

File:
Name: {file_ctx.name}
Type: {file_ctx.mime_type or "unknown"}
Tokens: {", ".join(tokens)}

Suggest up to {max_suggestions} folder names.
Respond with one folder per line.
"""

    raw_ai = await ollama_query(ai_prompt, model=model_name)
    known_folder_names = {
        _sanitize_folder(d.name)
        for d in directories
        if d.name
    }

    ai_lines = [
        _sanitize_folder(l)
        for l in raw_ai.splitlines()
        if l.strip() and _sanitize_folder(l) in known_folder_names
    ]

    known_folder_set = {
        _sanitize_folder(d.name)
        for d in directories
        if d.name
    }

    for idx, folder in enumerate(ai_lines[:max_suggestions]):
        # 🚫 Do not allow AI to invent folders when memory is empty
        if folder not in known_folder_set:
            continue

        if folder not in suggestions:
            suggestions[folder] = {
                "folder": folder,
                "memory_score": 0.0,
                "sources": {"ai"},
            }

    # ----------------------------
    # Rank + score
    # ----------------------------

    ranked = []

    for entry in suggestions.values():
        mem_score = entry["memory_score"]
        ai_score = 0.7 if "ai" in entry["sources"] else 0.9

        confidence = _confidence_from_similarity(mem_score, ai_score)

        ranked.append(
            {
                "folder": entry["folder"],
                "confidence": round(confidence, 3),
                "source": "+".join(sorted(entry["sources"])),
                "auto_move_eligible": confidence >= auto_threshold
                and ("project" in entry["sources"] or "global" in entry["sources"]),
            }
        )

    ranked.sort(key=lambda x: x["confidence"], reverse=True)

    return ranked[:max_suggestions]
