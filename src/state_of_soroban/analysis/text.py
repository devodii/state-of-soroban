import re

URL = re.compile(r"https?://\S+")
HASH = re.compile(r"\b[0-9a-f]{7,40}\b")
HEADING = re.compile(r"(?m)^\s*#{1,6}\s*")
SPACES = re.compile(r"\s+")
CONVENTIONAL = re.compile(r"^(\w+)(\([^)]*\))?!?:\s*")


def clean_text(title: str, body: str | None, limit: int) -> str:
    head = CONVENTIONAL.sub("", title.strip())
    text = f"{head}. {body or ''}"
    text = URL.sub(" ", text)
    text = HASH.sub(" ", text)
    text = HEADING.sub("", text)
    text = text.replace("`", " ")
    return SPACES.sub(" ", text).strip()[:limit]
