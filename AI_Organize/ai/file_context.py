from pathlib import Path
import re

MAX_CHARS = 4000  # hard safety cap

# Read a snippet of the file content for AI context (only for text-like files)
def read_file_snippet(path: Path) -> str | None:
    try:
        # Only text-like files
        if path.suffix.lower() not in {
            ".txt", ".md", ".rst", ".log",
            ".py", ".js", ".ts", ".json",
            ".yaml", ".yml", ".csv",
        }:
            return None

        text = path.read_text(errors="ignore")
        return text[:MAX_CHARS].strip()
    except Exception:
        return None

# Summarize file content using AI (returns bullet points or None)
async def summarize_file_content(
    *,
    filename: str,
    content: str,
    model: str,
) -> str:
    from akinus.ai.ollama import ollama_query

    prompt = f"""
Summarize the file below.

STRICT RULES:
- Do NOT include reasoning, thinking, analysis, or explanations
- Do NOT include phrases like "thinking", "analysis", or "done"
- Output ONLY bullet points
- Maximum 3 bullet points
- Each bullet must be 1 sentence

File name:
{filename}

File content:
{content}

Bullet-point summary:
"""
    raw = await ollama_query(prompt, model=model)
    return _clean_bullets(raw)


# Clean AI output to ensure it follows the bullet-point format and removes any unwanted text
def _clean_bullets(text: str) -> str:
    lines = text.splitlines()

    clean = []
    for line in lines:
        line = line.strip()

        # Drop empty lines
        if not line:
            continue

        # Drop obvious chain-of-thought junk
        if re.search(r"thinking|analysis|done thinking", line, re.I):
            continue

        # Keep bullets only
        if line.startswith(("-", "*", "•")):
            clean.append(line)

    # Safety fallback
    if not clean:
        return "- General file with minimal or unclear content."

    return "\n".join(clean[:3])