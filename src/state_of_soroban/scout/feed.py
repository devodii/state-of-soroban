from datetime import datetime

from pydantic import BaseModel


class Activity(BaseModel):
    repo: str
    url: str
    family: str
    family_members: int
    commits: int
    authors: int
    active_weeks: int
    top_author_share: float
    stars: int
    last_commit: datetime


class Missing(Activity):
    spread: bool


class Stale(Activity):
    scout_last_commit: datetime
    days_behind: int
    scout_activity_state: str | None


class ScoutFeed(BaseModel):
    generated_at: datetime
    scout: str
    window_days: int
    min_commits: int
    min_authors: int
    min_active_weeks: int
    max_top_author_share: float
    repos_checked: int
    in_scout: int
    not_in_scout: int
    errors: int
    missing: list[Missing]
    stale: list[Stale]
