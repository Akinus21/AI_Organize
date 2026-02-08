import re


SECTION_RE = re.compile(
    r"(# Directory Description\s*\n)(.*?)(?=\n# |\Z)",
    re.DOTALL,
)


def update_directory_description(
    content: str,
    new_text: str,
) -> str:
    block = f"# Directory Description\n{new_text.strip()}\n"

    if SECTION_RE.search(content):
        return SECTION_RE.sub(block, content)

    return content.rstrip() + "\n\n" + block
