from datetime import datetime

from pydantic import BaseModel


class Entry(BaseModel):
    symbol: str
    repos: int
    repos_defining_same_name: int
    docs_pages: int
    docs_urls: list[str]
    deprecated: str | None
    gaps: list[str]
    example_repos: list[str]


class Feed(BaseModel):
    generated_at: datetime
    crate: str
    version: str
    docs_source: str
    docs_pages_read: int
    repos_scanned: int
    entries: list[Entry]
