from pathlib import Path
import json

from .directory_hash import compute_directory_hash
from .readme_sections import update_directory_description
from .directory_summary import generate_directory_summary


HASH_MARKER = "<!-- DIR_HASH:"


def extract_hash(readme: str) -> str | None:
    for line in readme.splitlines():
        if line.startswith(HASH_MARKER):
            return line.removeprefix(HASH_MARKER).rstrip(" -->")
    return None


def inject_hash(text: str, hash_: str) -> str:
    return f"{HASH_MARKER}{hash_} -->\n{text}"


async def get_or_update_directory_summary(
    directory: Path,
    *,
    model: str,
    ai_call,
) -> str:
    readme = directory / "README.md"
    current_hash = compute_directory_hash(directory)

    if readme.exists():
        content = readme.read_text()
        cached = extract_hash(content)

        if cached == current_hash:
            # reuse existing summary
            return content.split("# Directory Description", 1)[1].strip()

    summary = await generate_directory_summary(
        directory,
        model=model,
        ai_call=ai_call,
    )

    new_body = update_directory_description(
        readme.read_text() if readme.exists() else "",
        summary,
    )

    readme.write_text(inject_hash(new_body, current_hash))
    return summary
